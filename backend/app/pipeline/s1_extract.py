"""S1 Extract per source, then the grounding gate G3-G5 and G10 (PRD §3.7, §3.8).

For one source: build its passages as Claude sees them (names hidden, speakers as roles), split them
into chunks, ask Claude for claims chunk by chunk with the prompt for the source's kind, then check
every claim deterministically. A claim that fails a check is stored as `rejected` with its reason,
guardrail and stage, and never reaches the map; the others are stored as `verified` (the
independent verifier, G6, arrives in phase P4). Unknowns become questions later (G8).

Nothing is stored for a source unless every chunk was answered in the right format.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.config import AppConfig
from app.db import session_scope
from app.domain import ai_schemas
from app.domain.enums import SourceKind
from app.domain.models import (
    AiCallRecord,
    CheckOutcome,
    ClaimRecord,
    NameReplacement,
    PromptSegment,
    StoredSegment,
    UnknownRecord,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline.context import AiContext, ai_failure, calls_in, record_calls, role_groups
from app.repositories import claims as claims_repo
from app.repositories import sources as sources_repo
from app.services import ai_service, chunking, grounding, parsing, prompts

Sessions = sessionmaker[Session]

STAGE = "S1"
SOURCE_REF = "s1"
PROMPT_BY_KIND = {
    SourceKind.INTERVIEW_TRANSCRIPT.value: "S1_extract_interview",
    SourceKind.JOB_DESCRIPTION.value: "S1_extract_jd",
}
DOCUMENT_PROMPT = "S1_extract_document"
UNMAPPED_SPEAKER = "Speaker"
FORMAT_FAILED = (
    "Claude's answer for 'Extracting steps from each source' didn't match the expected format "
    "twice. Nothing was saved. Try again, or use Copy details to report it."
)


@dataclass(slots=True)
class S1Tally:
    verified: int = 0
    rejected: int = 0
    unknowns: int = 0
    scrubbed: int = 0


def prompt_segments(
    stored: list[StoredSegment], fmt: str, terms: list[NameReplacement]
) -> list[PromptSegment]:
    """Passages as sent: call-local IDs, names hidden (G10), speakers shown by role only."""
    out = []
    for s in stored:
        role = s.speaker_role or ("Interviewer" if s.is_interviewer else "")
        if s.speaker_label and not role:
            role = UNMAPPED_SPEAKER
        out.append(
            PromptSegment(
                ref=f"p{s.seq}",
                segment_id=s.id,
                seq=s.seq,
                anchor=parsing.segment_anchor(
                    fmt=fmt,
                    seq=s.seq,
                    page=s.page,
                    section=s.section,
                    text=s.text,
                    start_ms=s.start_ms,
                ),
                text=redaction.hide(s.text, terms),
                speaker_role=role,
                page=s.page,
                start_ms=s.start_ms,
            )
        )
    return out


def chunks_for(kind: str, segments: list[PromptSegment]) -> list[list[PromptSegment]]:
    if kind == SourceKind.INTERVIEW_TRANSCRIPT.value:
        return chunking.chunk_transcript(segments)
    return chunking.chunk_document(segments)


def blocks_for(kind: str, chunk: list[PromptSegment]) -> list[dict[str, object]]:
    return [{"type": "text", "text": prompts.render_source(SOURCE_REF, kind, chunk)}]


def _scrub(
    claim: ai_schemas.S1Claim, terms: list[NameReplacement]
) -> tuple[ai_schemas.S1Claim, int]:
    """G10: any hidden name in the answer is replaced by its role; the hits are counted."""
    hits = 0
    fields: dict[str, object] = {}
    for name, value in claim.model_dump().items():
        if isinstance(value, str) and name not in {"claim_type", "mechanism", "provenance"}:
            result = grounding.redact_text(value, terms)
            hits += result.hits
            fields[name] = result.text
        else:
            fields[name] = value
    return ai_schemas.S1Claim.model_validate(fields), hits


def check_claim(
    claim: ai_schemas.S1Claim, chunk: list[PromptSegment], groups: list[list[str]]
) -> CheckOutcome:
    """G3 → G4 → G5 (numbers, then roles); the first failure decides."""
    by_ref = {s.ref: s for s in chunk}
    outcome = grounding.verify_segments(claim.segment_ids, by_ref)
    if not outcome.passed:
        return outcome
    cited = prompts.cited_text([by_ref[ref] for ref in claim.segment_ids])
    outcome = grounding.verify_quote(claim.quote, cited)
    if not outcome.passed:
        return outcome
    stated = " ".join((claim.text, claim.duration_text, claim.threshold))
    basis = claim.basis if claim.provenance == "I" else ""
    outcome = grounding.verify_numbers(stated, cited, basis)
    if not outcome.passed:
        return outcome
    roles = [claim.responsible_role, claim.accountable_role, claim.decider_role]
    return grounding.verify_roles(roles, cited, groups)


def gate(
    answer: ai_schemas.S1Output,
    chunk: list[PromptSegment],
    *,
    source_id: str,
    terms: list[NameReplacement],
    groups: list[list[str]],
) -> tuple[list[ClaimRecord], list[UnknownRecord], int]:
    """Check every claim of one answer; return stored records, unknowns and the scrub count."""
    by_ref = {s.ref: s for s in chunk}
    records: list[ClaimRecord] = []
    scrubbed_total = 0
    for raw in answer.claims:
        claim, scrubbed = _scrub(raw, terms)
        scrubbed_total += scrubbed
        outcome = check_claim(claim, chunk, groups)
        payload: dict[str, object] = {
            k: v
            for k, v in claim.model_dump().items()
            if k not in {"claim_type", "segment_ids", "quote", "provenance", "basis"}
        }
        payload["scrubbed"] = scrubbed
        payload["segment_refs"] = list(claim.segment_ids)
        records.append(
            ClaimRecord(
                source_id=source_id,
                stage=STAGE,
                claim_type=claim.claim_type,
                payload=payload,
                segment_ids=[by_ref[r].segment_id for r in claim.segment_ids if r in by_ref],
                quote=claim.quote,
                provenance=claim.provenance,
                basis=claim.basis,
                verification_status="verified" if outcome.passed else "rejected",
                rejection_reason=outcome.reason,
                rejection_guardrail=outcome.guardrail,
            )
        )
    unknowns = [
        UnknownRecord(
            source_id=source_id,
            question=redaction.hide(u.question, terms),
            segment_ids=[by_ref[r].segment_id for r in u.segment_ids if r in by_ref],
        )
        for u in answer.unknowns
    ]
    return records, unknowns, scrubbed_total


def _dedupe(records: list[ClaimRecord]) -> list[ClaimRecord]:
    """Overlapping chunks can return the same claim twice; keep the first."""
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    kept = []
    for r in records:
        key = (
            r.claim_type,
            grounding.normalise_text(str(r.payload.get("text", ""))),
            tuple(sorted(r.segment_ids)),
        )
        if key not in seen:
            seen.add(key)
            kept.append(r)
    return kept


def extract_source(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    *,
    version_id: str,
    source_id: str,
    job_id: str | None = None,
) -> Result[S1Tally]:
    """Run S1 on one source and store its checked claims and unknowns in the version."""
    with session_scope(sessions) as session:
        info = sources_repo.reading_info(session, source_id)
        if info is None:
            return Err(ErrorKind.NOT_FOUND, "That source doesn't exist. It may have been deleted.")
        terms = redaction.name_replacements(session, info.engagement_id)
        groups = role_groups(session, info.engagement_id)
        stored = sources_repo.stored_segments(session, source_id)
    prompt_name = PROMPT_BY_KIND.get(info.kind, DOCUMENT_PROMPT)
    match prompts.load_prompt(prompt_name):
        case Err() as err:
            return err
        case Ok(value=prompt):
            pass
    match prompts.load_prompt(ai_service.REPAIR_STAGE):
        case Err() as err:
            return err
        case Ok(value=repair):
            pass

    segments = prompt_segments(stored, info.format, terms)
    records: list[ClaimRecord] = []
    unknowns: list[UnknownRecord] = []
    tally = S1Tally()
    for chunk in chunks_for(info.kind, segments):
        call = ai_service.StageCall(
            stage_id=prompt_name,
            prompt_version=prompt.version,
            system=prompt.text,
            blocks=blocks_for(info.kind, chunk),
            output_model=ai_schemas.S1Output,
            model=ctx.model,
            repair_prompt=repair.text,
            effort=ctx.effort,
            structured_outputs=ctx.structured_outputs,
        )
        result = ai_service.call_claude(ctx.conn, call)
        used: list[AiCallRecord] = (
            result.value.calls if isinstance(result, Ok) else calls_in(result)
        )
        with session_scope(sessions) as session:
            record_calls(session, job_id, used)
        match result:
            case Err(kind=ErrorKind.AI_FORMAT) as err:
                return Err(ErrorKind.AI_FORMAT, FORMAT_FAILED, err.details)
            case Err() as err:
                return ai_failure(err)
            case Ok(value=answer):
                pass
        chunk_records, chunk_unknowns, scrubbed = gate(
            ai_schemas.S1Output.model_validate(answer.data),
            chunk,
            source_id=source_id,
            terms=terms,
            groups=groups,
        )
        records += chunk_records
        unknowns += chunk_unknowns
        tally.scrubbed += scrubbed

    records = _dedupe(records)
    with session_scope(sessions) as session:
        claims_repo.add_claims(session, version_id, records)
        claims_repo.add_unknowns(session, version_id, unknowns)
    tally.verified = sum(r.verification_status == "verified" for r in records)
    tally.rejected = sum(r.verification_status == "rejected" for r in records)
    tally.unknowns = len(unknowns)
    return Ok(tally)
