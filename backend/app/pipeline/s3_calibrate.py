"""S3 Calibrate (PRD §3.7): what every source says about every step, then the source states.

For each source the draft was made from, chunk by chunk (as in S1), Claude sees the steps (with
the claims they were built from) and that part of the source, and returns a stance for each step
the source addresses: `supports` or `contradicts`, with segment IDs and a quote. A step the
source doesn't mention is silent: nothing is stored and it never counts as contradiction
(constraint 4). Every stance goes through the grounding gate again (G3, G4, G5 on the divergence
note, G10); a failing stance is stored as a rejected claim of stage S3.

Then, deterministically: each element's source state (`calibration.assign_source_state`), its
divergence types, and the JD accountability test for decisions and approvals (a disagreement adds
divergence `ownership`).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.config import AppConfig
from app.db import session_scope
from app.domain import ai_schemas
from app.domain.enums import DivergenceType, ElementKind, Stance
from app.domain.graph import ElementRecord, EvidenceRecord
from app.domain.models import (
    AccountableFact,
    AiCallRecord,
    CheckOutcome,
    ClaimRecord,
    NameReplacement,
    PromptSegment,
    StanceFact,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline import s1_extract
from app.pipeline.context import AiContext, ai_failure, calls_in, record_calls
from app.pipeline.s2_canonicalise import ClaimRef, claim_refs, claims_text
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import ai_service, calibration, grounding, prompts

Sessions = sessionmaker[Session]

STAGE = "S3"
STAGE_ID = "S3_calibrate"
SOURCE_REF = "s1"
NO_DIVERGENCE = "none"
SILENT = Stance.SILENT.value
FORMAT_FAILED = (
    "Claude's answer for 'Comparing sources' didn't match the expected format twice. Nothing was "
    "saved. Try again, or use Copy details to report it."
)


@dataclass(slots=True)
class S3Tally:
    stances: int = 0
    rejected: int = 0
    scrubbed: int = 0


@dataclass(frozen=True, slots=True)
class StepRef:
    ref: str
    element: ElementRecord
    lane: str
    claims: tuple[ClaimRef, ...]


def step_refs(session: Session, version_id: str) -> list[StepRef]:
    """The elements as the call names them (`e1…` in element order), with their claims."""
    version = versions_repo.get(session, version_id)
    if version is None:
        return []
    roles = {r.id: r.name for r in engagements_repo.list_roles(session, version.engagement_id)}
    by_claim = {c.claim_id: c for c in claim_refs(session, version_id)}
    linked = map_repo.element_claims(session, version_id)
    return [
        StepRef(
            ref=f"e{n}",
            element=e,
            lane=roles.get(e.lane_role_id or "", ""),
            claims=tuple(by_claim[c] for c in linked.get(e.id, []) if c in by_claim),
        )
        for n, e in enumerate(map_repo.elements(session, version_id), start=1)
        if e.kind in {ElementKind.ACTIVITY, ElementKind.DECISION, ElementKind.APPROVAL}
    ]


def render_steps(steps: list[StepRef]) -> str:
    esc = prompts.escape
    lines = ["<steps>"]
    for s in steps:
        lines.append(
            f'<step id="{s.ref}" kind="{esc(s.element.kind)}" lane="{esc(s.lane)}" '
            f'label="{esc(s.element.label)}">'
        )
        lines += [f"<claim>{esc(str(c.record.payload.get('text', '')))}</claim>" for c in s.claims]
        lines.append("</step>")
    lines.append("</steps>")
    return "\n".join(lines)


def blocks_for(
    steps: list[StepRef], kind: str, chunk: list[PromptSegment]
) -> list[dict[str, object]]:
    return [
        {"type": "text", "text": render_steps(steps)},
        {"type": "text", "text": prompts.render_source(SOURCE_REF, kind, chunk)},
    ]


def source_chunks(
    session: Session, source_id: str, terms: list[NameReplacement]
) -> tuple[str, list[list[PromptSegment]]]:
    """The source's kind and its chunks, exactly as S1 cut them."""
    info = sources_repo.reading_info(session, source_id)
    if info is None:
        return "", []
    stored = sources_repo.stored_segments(session, source_id)
    segments = s1_extract.prompt_segments(stored, info.format, terms)
    return info.kind, s1_extract.chunks_for(info.kind, segments)


def check_stance(
    stance: ai_schemas.S3Stance, chunk: list[PromptSegment], by_step: dict[str, StepRef]
) -> CheckOutcome:
    """Step supplied → G3 passages supplied → G4 quote → G5 numbers in the divergence note."""
    step = by_step.get(stance.step_ref)
    if step is None:
        return CheckOutcome(
            passed=False, guardrail="G3", reason="cites a step that wasn't provided"
        )
    by_ref = {s.ref: s for s in chunk}
    outcome = grounding.verify_segments(stance.segment_ids, by_ref)
    if not outcome.passed:
        return outcome
    cited = prompts.cited_text([by_ref[r] for r in stance.segment_ids])
    outcome = grounding.verify_quote(stance.quote, cited)
    if not outcome.passed:
        return outcome
    return grounding.verify_numbers(
        stance.divergence_note, cited + "\n" + claims_text(list(step.claims))
    )


def _aggregate(stances: list[str]) -> str:
    """A source's stance on an element: contradicts if any passage contradicts it."""
    if Stance.CONTRADICTS.value in stances:
        return Stance.CONTRADICTS.value
    return Stance.SUPPORTS.value if stances else Stance.SILENT.value


def accountable_facts(step: StepRef) -> list[AccountableFact]:
    """Each source's Accountable role for a decision or approval, from the step's claims."""
    facts = []
    for c in step.claims:
        payload = c.record.payload
        role = str(payload.get("accountable_role", "") or "")
        if not role and step.element.kind == ElementKind.DECISION.value:
            role = str(payload.get("decider_role", "") or "")
        facts.append(
            AccountableFact(source_id=c.record.source_id, source_kind=c.source_kind, role=role)
        )
    return facts


def calibrate(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    *,
    version_id: str,
    job_id: str | None = None,
) -> Result[S3Tally]:
    tally = S3Tally()
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, "That version doesn't exist.")
        steps = step_refs(session, version_id)
        terms = redaction.name_replacements(session, version.engagement_id)
        source_ids = map_repo.version_source_ids(session, version_id)
        chunked = {sid: source_chunks(session, sid, terms) for sid in source_ids}
    if not steps:
        return Ok(tally)
    match prompts.load_prompt(STAGE_ID):
        case Err() as err:
            return err
        case Ok(value=prompt):
            pass
    match prompts.load_prompt(ai_service.REPAIR_STAGE):
        case Err() as err:
            return err
        case Ok(value=repair):
            pass

    by_step = {s.ref: s for s in steps}
    links: list[EvidenceRecord] = []
    rejected: list[ClaimRecord] = []
    stances: dict[str, dict[str, list[str]]] = {}  # element ID → source ID → stances
    for source_id, (kind, chunks) in chunked.items():
        for chunk in chunks:
            call = ai_service.StageCall(
                stage_id=STAGE_ID,
                prompt_version=prompt.version,
                system=prompt.text,
                blocks=blocks_for(steps, kind, chunk),
                output_model=ai_schemas.S3Output,
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
            by_ref = {s.ref: s for s in chunk}
            for raw in ai_schemas.S3Output.model_validate(answer.data).stances:
                note = grounding.redact_text(raw.divergence_note, terms)
                quote = grounding.redact_text(raw.quote, terms)
                tally.scrubbed += note.hits + quote.hits
                stance = raw.model_copy(update={"divergence_note": note.text, "quote": quote.text})
                outcome = check_stance(stance, chunk, by_step)
                step = by_step.get(stance.step_ref)
                if not outcome.passed or step is None:
                    label = step.element.label if step else stance.step_ref
                    rejected.append(
                        ClaimRecord(
                            source_id=source_id,
                            stage=STAGE,
                            claim_type="stance",
                            payload={
                                "text": f'{stance.stance.capitalize()} "{label}"'
                                + (f": {stance.divergence_note}" if stance.divergence_note else ""),
                                "scrubbed": note.hits + quote.hits,
                            },
                            segment_ids=[
                                by_ref[r].segment_id for r in stance.segment_ids if r in by_ref
                            ],
                            quote=stance.quote,
                            provenance="O",
                            basis="",
                            verification_status="rejected",
                            rejection_reason=outcome.reason,
                            rejection_guardrail=outcome.guardrail,
                        )
                    )
                    continue
                element_id = step.element.id
                stances.setdefault(element_id, {}).setdefault(source_id, []).append(stance.stance)
                note_text = (
                    stance.divergence_note if stance.divergence_type != NO_DIVERGENCE else ""
                )
                for ref in dict.fromkeys(stance.segment_ids):
                    link = EvidenceRecord(
                        element_id=element_id,
                        segment_id=by_ref[ref].segment_id,
                        source_kind=kind,
                        stance=stance.stance,
                        verified=True,
                        quote=stance.quote,
                        note=note_text,
                    )
                    if not any(
                        (x.element_id, x.segment_id, x.stance)
                        == (link.element_id, link.segment_id, link.stance)
                        for x in links
                    ):
                        links.append(link)
                if stance.divergence_type != NO_DIVERGENCE:
                    by_step[stance.step_ref] = _with_divergence(step, stance.divergence_type)

    kinds = {sid: kind for sid, (kind, _) in chunked.items()}
    with session_scope(sessions) as session:
        map_repo.add_evidence(session, links)
        claims_repo.add_claims(session, version_id, rejected)
        for step in by_step.values():
            facts = [
                StanceFact(source_id=sid, source_kind=kinds[sid], stance=_aggregate(found))
                for sid, found in stances.get(step.element.id, {}).items()
            ]
            divergences = list(step.element.divergence_types)
            decides = step.element.kind in {ElementKind.DECISION, ElementKind.APPROVAL}
            if decides and calibration.jd_accountability_test(accountable_facts(step)).contested:
                divergences.append(DivergenceType.OWNERSHIP.value)
            map_repo.update_element(
                session,
                step.element.id,
                {
                    "source_state": calibration.assign_source_state(facts, step.element.provenance),
                    "divergence_types": [d.value for d in DivergenceType if d.value in divergences],
                },
            )
    tally.stances = len(links)
    tally.rejected = len(rejected)
    return Ok(tally)


def _with_divergence(step: StepRef, divergence: str) -> StepRef:
    types = list(step.element.divergence_types)
    if divergence not in types:
        types.append(divergence)
    element = step.element.model_copy(update={"divergence_types": types})
    return StepRef(ref=step.ref, element=element, lane=step.lane, claims=step.claims)


def ground_in_claims(
    _config: AppConfig,
    sessions: Sessions,
    _ctx: AiContext,
    *,
    version_id: str,
    job_id: str | None = None,
) -> Result[int]:
    """After S3b: a source a step's own checked claims quote is never silent about it.

    The comparison call can leave a step out for a source (2026-10-28, Eric's cargo manual: two
    steps drafted from the manual came back with no passage, "not assessed" and drawn As done).
    The passages the step's remaining claims cite then support it, as the claims already passed
    G3-G5 and the verifier; the step's source state is worked out again. Deterministic, no call.
    Returns how many steps gained evidence.
    """
    with session_scope(sessions) as session:
        steps = step_refs(session, version_id)
        passages = map_repo.evidence(session, version_id)
        speaking: dict[str, set[str]] = {}
        for p in passages:
            if p.evidence.element_id and p.evidence.stance != SILENT:
                speaking.setdefault(p.evidence.element_id, set()).add(p.source_id)
        cited = [s for step in steps for c in step.claims for s in c.record.segment_ids]
        owners = sources_repo.segment_owners(session, cited)
        grounded = 0
        for step in steps:
            heard = speaking.get(step.element.id, set())
            links: dict[str, EvidenceRecord] = {}
            for claim in step.claims:
                for segment_id in claim.record.segment_ids:
                    owner = owners.get(segment_id)
                    if owner is None or owner[0] in heard or segment_id in links:
                        continue
                    links[segment_id] = EvidenceRecord(
                        element_id=step.element.id, segment_id=segment_id, source_kind=owner[2],
                        stance=Stance.SUPPORTS.value, verified=True, quote=claim.record.quote,
                    )  # fmt: skip
            if not links:
                continue
            map_repo.add_evidence(session, list(links.values()))
            facts: dict[str, StanceFact] = {}
            for p in map_repo.evidence(session, version_id):
                if p.evidence.element_id == step.element.id and p.evidence.stance != SILENT:
                    known = facts.get(p.source_id)
                    if known is None or p.evidence.stance == Stance.CONTRADICTS.value:
                        facts[p.source_id] = StanceFact(
                            source_id=p.source_id, source_kind=p.evidence.source_kind,
                            stance=p.evidence.stance,
                        )  # fmt: skip
            state = calibration.assign_source_state(facts.values(), step.element.provenance)
            map_repo.update_element(session, step.element.id, {"source_state": state})
            grounded += 1
    return Ok(grounded)
