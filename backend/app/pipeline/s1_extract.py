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
from app.domain.enums import InterviewType, SourceKind
from app.domain.interview import BankQuestion, Turn
from app.domain.models import (
    AiCallRecord,
    CheckOutcome,
    ClaimRecord,
    NameReplacement,
    PromptSegment,
    SourceReadInfo,
    StoredSegment,
    UnknownRecord,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline.context import AiContext, ai_failure, calls_in, record_calls, role_groups
from app.repositories import claims as claims_repo
from app.repositories import sources as sources_repo
from app.services import (
    ai_service,
    chunking,
    grounding,
    interview_templates,
    parsing,
    prompts,
    question_matching,
    sensemaking,
)

Sessions = sessionmaker[Session]

STAGE = "S1"
# Interview fields kept in their own column or checked before they go into the payload.
INTERVIEW = {
    "account_type",
    "account_cue",
    "stated_reason",
    "variation_condition",
    "markers",
}
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


def blocks_for(
    kind: str, chunk: list[PromptSegment], questions: dict[str, BankQuestion] | None = None
) -> list[dict[str, object]]:
    """One chunk as sent. For an interview, the guide questions its answer blocks answer come
    first, with their targets (§3.12.10 step A)."""
    text = prompts.render_source(SOURCE_REF, kind, chunk)
    asked = list(dict.fromkeys(s.question_id for s in chunk if s.question_id))
    if questions and asked:
        text = (
            prompts.render_questions([questions[q] for q in asked if q in questions]) + "\n" + text
        )
    return [{"type": "text", "text": text}]


# Until tailored guides exist (P4c), interviews are matched against the standard Practice
# template's questions (PRD Appendix A.9: "the default Practice guide … without tailoring").
DEFAULT_GUIDE = InterviewType.PRACTICE


@dataclass(frozen=True, slots=True)
class Prepared:
    """One source ready for S1: its passages as sent, and for an interview the guide questions
    its answer blocks answer."""

    info: SourceReadInfo
    terms: list[NameReplacement]
    groups: list[list[str]]
    segments: list[PromptSegment]
    questions: dict[str, BankQuestion]


def prepare(session: Session, source_id: str) -> Result[Prepared]:
    """Passages as sent (names hidden, speakers as roles). For an interview transcript, step A
    (each turn's guide question, stored on the passage) and step B (marker hints on the SME's
    turns) are applied first (§3.12.10)."""
    info = sources_repo.reading_info(session, source_id)
    if info is None:
        return Err(ErrorKind.NOT_FOUND, "That source doesn't exist. It may have been deleted.")
    terms = redaction.name_replacements(session, info.engagement_id)
    groups = role_groups(session, info.engagement_id)
    stored = sources_repo.stored_segments(session, source_id)
    segments = prompt_segments(stored, info.format, terms)
    if info.kind != SourceKind.INTERVIEW_TRANSCRIPT.value:
        return Ok(Prepared(info, terms, groups, segments, {}))
    match interview_templates.load_bank():
        case Err() as err:
            return err
        case Ok(value=bank):
            pass
    match sensemaking.load_lexicon():
        case Err() as err:
            return err
        case Ok(value=lexicon):
            pass
    guide = [bank.question(q) for q in bank.template_ids(DEFAULT_GUIDE)]
    turns = [Turn(seq=s.seq, is_interviewer=s.is_interviewer, text=s.text) for s in stored]
    by_seq = {
        a.seq: a.question_id for a in question_matching.answer_blocks(turns, guide, bank.questions)
    }
    sources_repo.set_question_ids(session, source_id, by_seq)
    interviewer = {s.seq for s in stored if s.is_interviewer}
    annotated = [
        s.model_copy(
            update={
                "question_id": by_seq.get(s.seq) or "",
                "markers": []
                if s.seq in interviewer
                else [f"{t.pretag}: {t.phrase}" for t in sensemaking.pretag(s.text, lexicon)],
            }
        )
        for s in segments
    ]
    asked = {q for q in by_seq.values() if q}
    return Ok(
        Prepared(info, terms, groups, annotated, {q: bank.question(q) for q in sorted(asked)})
    )


FIXED_FIELDS = {"claim_type", "mechanism", "provenance", "account_type"}


def _scrub[ClaimT: ai_schemas.S1Claim](
    claim: ClaimT, terms: list[NameReplacement]
) -> tuple[ClaimT, int]:
    """G10: any hidden name in the answer is replaced by its role; the hits are counted."""
    hits = 0
    fields: dict[str, object] = {}
    for name, value in claim.model_dump().items():
        if isinstance(value, str) and name not in FIXED_FIELDS:
            result = grounding.redact_text(value, terms)
            hits += result.hits
            fields[name] = result.text
        else:
            fields[name] = value
    return type(claim).model_validate(fields), hits


def check_interview_fields(
    claim: ai_schemas.S1InterviewClaim, cited: str
) -> tuple[str, dict[str, object]]:
    """The account tag, stated reason, variation condition and marker reviews of a verified
    interview claim pass the quote check (G4) like every other output (§3.12.9 rule 7). A cue that
    isn't in the cited text makes the account `unclear`; a reason, condition or marker review
    whose words aren't there is dropped. Returns the account type and the payload fields."""

    def found(words: str) -> bool:
        return bool(words) and grounding.verify_quote(words, cited).passed

    account = claim.account_type
    if account != "unclear" and not found(claim.account_cue):
        account = "unclear"
    markers = [m.model_dump() for m in claim.markers if found(m.quote)]
    return account, {
        "account_cue": claim.account_cue if account != "unclear" else "",
        "account_cue_dropped": claim.account_type != account,
        "stated_reason": claim.stated_reason if found(claim.stated_reason) else "",
        "variation_condition": (
            claim.variation_condition if found(claim.variation_condition) else ""
        ),
        "markers": markers,
        "markers_dropped": len(claim.markers) - len(markers),
    }


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
    answer: ai_schemas.S1Output | ai_schemas.S1InterviewOutput,
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
            if k not in {"claim_type", "segment_ids", "quote", "provenance", "basis"} | INTERVIEW
        }
        payload["scrubbed"] = scrubbed
        payload["segment_refs"] = list(claim.segment_ids)
        account: str | None = None
        if isinstance(claim, ai_schemas.S1InterviewClaim):
            account = "unclear"
            if outcome.passed:
                cited = prompts.cited_text([by_ref[ref] for ref in claim.segment_ids])
                account, fields = check_interview_fields(claim, cited)
                payload.update(fields)
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
                account_type=account,
            )
        )
    if isinstance(answer, ai_schemas.S1InterviewOutput):
        items: list[SenseItem] = [
            *answer.stories, *answer.know_how, *answer.terms, *answer.decision_info,
            *answer.capability_notes,
        ]  # fmt: skip
        for item in items:
            record, hits = check_sense(item, chunk, terms, source_id)
            records.append(record)
            scrubbed_total += hits
    unknowns = [
        UnknownRecord(
            source_id=source_id,
            question=redaction.hide(u.question, terms),
            segment_ids=[by_ref[r].segment_id for r in u.segment_ids if r in by_ref],
        )
        for u in answer.unknowns
    ]
    return records, unknowns, scrubbed_total


SenseItem = (
    ai_schemas.S1Story
    | ai_schemas.S1KnowHow
    | ai_schemas.S1Term
    | ai_schemas.S1DecisionInfo
    | ai_schemas.S1Capability
)
SENSE_KIND: dict[type, str] = {
    ai_schemas.S1Story: "story",
    ai_schemas.S1KnowHow: "know_how",
    ai_schemas.S1Term: "sme_term",
    ai_schemas.S1DecisionInfo: "decision_info",
    ai_schemas.S1Capability: "capability",
}
TERM_NOT_FOUND = "term not found in cited text"


def _hide_all(value: object, terms: list[NameReplacement]) -> tuple[object, int]:
    """G10 on every text of an item (strings and lists of strings); returns the hit count."""
    if isinstance(value, str):
        result = grounding.redact_text(value, terms)
        return result.text, result.hits
    if isinstance(value, list):
        out, hits = [], 0
        for v in value:
            text, n = _hide_all(v, terms)
            out.append(text)
            hits += n
        return out, hits
    return value, 0


def check_sense(
    item: SenseItem, chunk: list[PromptSegment], terms: list[NameReplacement], source_id: str
) -> tuple[ClaimRecord, int]:
    """One story, know-how item, term, decision-information item or capability note, checked like
    a claim (§3.12.9 rule 7): names hidden (G10), cited passages sent in this call (G3), the quote
    found in them (G4) and every number in its words found there too (G5). The SME's own words
    must be in the passages: a term that isn't is rejected; a signifier or frequency that isn't is
    dropped (they are recorded as observed, never inferred)."""
    by_ref = {s.ref: s for s in chunk}
    fields: dict[str, object] = {}
    hits = 0
    for name, value in item.model_dump().items():
        if name in {"segment_ids", "quote", "provenance", "basis", "fragment_type", "category",
                    "cadence", "kind", "dimension", "cause_type"}:  # fmt: skip
            fields[name] = value
            continue
        fields[name], n = _hide_all(value, terms)
        hits += n
    refs: list[str] = list(item.segment_ids)
    outcome = grounding.verify_segments(refs, by_ref)
    cited = prompts.cited_text([by_ref[r] for r in refs]) if outcome.passed else ""
    if outcome.passed:
        outcome = grounding.verify_quote(item.quote, cited)
    provenance = getattr(item, "provenance", "O")
    basis = getattr(item, "basis", "") if provenance == "I" else ""
    stated = " ".join(
        str(v) if isinstance(v, str) else " ".join(map(str, v))
        for k, v in fields.items()
        if k not in {"segment_ids", "quote", "basis"} and isinstance(v, str | list)
    )
    if outcome.passed:
        outcome = grounding.verify_numbers(stated, cited, basis)

    def found(words: str) -> bool:
        return bool(words) and grounding.verify_quote(words, cited).passed

    if outcome.passed and isinstance(item, ai_schemas.S1Term) and not found(str(fields["term"])):
        outcome = CheckOutcome(passed=False, guardrail="G4", reason=TERM_NOT_FOUND)
    if outcome.passed and isinstance(item, ai_schemas.S1Story):
        signifiers = [s for s in fields["signifiers"] if found(s)]  # type: ignore[attr-defined]
        fields["signifiers_dropped"] = len(item.signifiers) - len(signifiers)
        fields["signifiers"] = signifiers
        if not found(str(fields["frequency"])):
            fields["frequency"] = ""
    kind = SENSE_KIND[type(item)]
    text = {
        "story": fields.get("label", ""),
        "sme_term": f"{fields.get('term', '')}: {fields.get('plain_meaning', '')}",
        "decision_info": fields.get("about", ""),
    }.get(kind, fields.get("text", ""))
    payload = {k: v for k, v in fields.items() if k not in {"segment_ids", "quote", "provenance",
                                                           "basis"}}  # fmt: skip
    payload |= {"text": text, "scrubbed": hits, "segment_refs": refs}
    record = ClaimRecord(
        source_id=source_id,
        stage=STAGE,
        claim_type=kind,
        payload=payload,
        segment_ids=[by_ref[r].segment_id for r in refs if r in by_ref],
        quote=item.quote,
        provenance=provenance,
        basis=getattr(item, "basis", ""),
        verification_status="verified" if outcome.passed else "rejected",
        rejection_reason=outcome.reason,
        rejection_guardrail=outcome.guardrail,
    )
    return record, hits


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
        match prepare(session, source_id):
            case Err() as err:
                return err
            case Ok(value=prepared):
                pass
    info, terms, groups = prepared.info, prepared.terms, prepared.groups
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

    records: list[ClaimRecord] = []
    unknowns: list[UnknownRecord] = []
    tally = S1Tally()
    output_model: type[ai_schemas.S1Output] | type[ai_schemas.S1InterviewOutput] = (
        ai_schemas.S1InterviewOutput
        if info.kind == SourceKind.INTERVIEW_TRANSCRIPT.value
        else ai_schemas.S1Output
    )
    for chunk in chunks_for(info.kind, prepared.segments):
        call = ai_service.StageCall(
            stage_id=prompt_name,
            prompt_version=prompt.version,
            system=prompt.text,
            blocks=blocks_for(info.kind, chunk, prepared.questions),
            output_model=output_model,
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
            output_model.model_validate(answer.data),
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
