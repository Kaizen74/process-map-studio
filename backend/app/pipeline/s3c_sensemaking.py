"""S3c Sensemaking (PRD §3.7, §3.12.4-3.12.6; C2): work types, and what the interview's stories,
know-how, terms and decision information are about.

One call sees the steps (with their claims), the items S1 took from the interviews and the
passages both cite. Claude proposes a work type per step with quoted cues, and links each item to
the steps it is about. Deterministic checks follow: a cue must cite passages sent in this call
(G3) and be found in them (G4); a proposal without one valid cue is `not_classified`
(`sensemaking.validate_work_type_cues`); the constraint type follows from the work type. Links to
unknown items or steps are dropped; a link is stored on the item as the steps' stable keys, so it
survives a refresh and a reopen. Steps Eric has reviewed keep their work type (constraint 8).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.config import AppConfig
from app.db import session_scope
from app.domain import ai_schemas
from app.domain.enums import ElementKind, ReviewStatus
from app.domain.graph import ConstraintRecord, QuestionRecord
from app.domain.models import AiCallRecord, ClaimRecord, NameReplacement, PromptSegment
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import SENSE_CLAIM_TYPES
from app.pipeline import s1_extract
from app.pipeline.context import AiContext, ai_failure, calls_in, record_calls
from app.pipeline.s3_calibrate import StepRef, render_steps, step_refs
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import ai_service, prompts, sensemaking

Sessions = sessionmaker[Session]

STAGE_ID = "S3c_worktype"
FORMAT_FAILED = (
    "Claude's answer for 'Classifying the kind of work' didn't match the expected format twice. "
    "Nothing was saved. Try again, or use Copy details to report it."
)
REVIEWED = {
    ReviewStatus.CONFIRMED.value,
    ReviewStatus.EDITED.value,
    ReviewStatus.ADDED.value,
    ReviewStatus.REJECTED.value,
}
DECIDING = {ElementKind.DECISION.value, ElementKind.APPROVAL.value}
NOT_CLASSIFIED_QUESTION = (
    'What kind of work is "{label}"? Is it done by following a fixed rule, worked out by someone '
    "experienced, a judgment call that depends on the situation, or firefighting?"
)


@dataclass(slots=True)
class S3cTally:
    classified: int = 0
    not_classified: int = 0
    dropped_cues: int = 0
    links: int = 0
    dropped_links: int = 0
    constraints: int = 0


@dataclass(frozen=True, slots=True)
class Item:
    ref: str
    claim_id: str
    record: ClaimRecord


def items_for(session: Session, version_id: str) -> list[Item]:
    """The verified stories, know-how, terms and the like, as the call names them (`i1…`)."""
    rows = [
        (claim_id, record)
        for claim_id, record in claims_repo.verified_rows(session, version_id)
        if record.claim_type in SENSE_CLAIM_TYPES
    ]
    return [Item(f"i{n}", cid, r) for n, (cid, r) in enumerate(rows, start=1)]


def passages_for(
    session: Session, steps: list[StepRef], items: list[Item], terms: list[NameReplacement]
) -> list[tuple[str, str, list[PromptSegment]]]:
    """The passages the steps' claims and the items cite, per source: (source ref, kind, passages
    with call-wide IDs `s<n>.p<seq>`)."""
    records = [c.record for s in steps for c in s.claims] + [i.record for i in items]
    wanted = {seg for r in records for seg in r.segment_ids}
    out = []
    for n, source_id in enumerate(dict.fromkeys(r.source_id for r in records), start=1):
        info = sources_repo.reading_info(session, source_id)
        if info is None:
            continue
        stored = sources_repo.stored_segments(session, source_id)
        sref = f"s{n}"
        segments = [
            s.model_copy(update={"ref": f"{sref}.{s.ref}"})
            for s in s1_extract.prompt_segments(stored, info.format, terms)
            if s.segment_id in wanted
        ]
        if segments:
            out.append((sref, info.kind, segments))
    return out


def render_items(items: list[Item]) -> str:
    esc = prompts.escape
    lines = ["<items>"]
    for i in items:
        p = i.record.payload
        detail = str(p.get("category") or p.get("fragment_type") or "")
        lines.append(
            f'<item id="{i.ref}" kind="{esc(i.record.claim_type)}" category="{esc(detail)}" '
            f'about="{esc(str(p.get("about", "")))}">{esc(str(p.get("text", "")))}</item>'
        )
    lines.append("</items>")
    return "\n".join(lines)


def blocks_for(
    steps: list[StepRef], items: list[Item], sources: list[tuple[str, str, list[PromptSegment]]]
) -> list[dict[str, object]]:
    text = "\n".join([render_steps(steps), render_items(items)] + [
        prompts.render_source(sref, kind, segments) for sref, kind, segments in sources
    ])  # fmt: skip
    return [{"type": "text", "text": text}]


def sense(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    *,
    version_id: str,
    job_id: str | None = None,
) -> Result[S3cTally]:
    tally = S3cTally()
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, "That version doesn't exist.")
        steps = step_refs(session, version_id)
        items = items_for(session, version_id)
        terms = redaction.name_replacements(session, version.engagement_id)
        sources = passages_for(session, steps, items, terms)
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
    call = ai_service.StageCall(
        stage_id=STAGE_ID,
        prompt_version=prompt.version,
        system=prompt.text,
        blocks=blocks_for(steps, items, sources),
        output_model=ai_schemas.S3cOutput,
        model=ctx.model,
        repair_prompt=repair.text,
        effort=ctx.effort,
        structured_outputs=ctx.structured_outputs,
    )
    result = ai_service.call_claude(ctx.conn, call)
    used: list[AiCallRecord] = result.value.calls if isinstance(result, Ok) else calls_in(result)
    with session_scope(sessions) as session:
        record_calls(session, job_id, used)
    match result:
        case Err(kind=ErrorKind.AI_FORMAT) as err:
            return Err(ErrorKind.AI_FORMAT, FORMAT_FAILED, err.details)
        case Err() as err:
            return ai_failure(err)
        case Ok(value=answer):
            pass
    output = ai_schemas.S3cOutput.model_validate(answer.data)
    by_ref = {s.ref: s for s in steps}
    passages = {seg.ref: seg for _, _, segs in sources for seg in segs}
    proposals: dict[str, ai_schemas.S3cWorkType] = {}
    for wt in output.work_types:
        if wt.step_ref in by_ref and wt.step_ref not in proposals:
            proposals[wt.step_ref] = wt
    with session_scope(sessions) as session:
        for step in steps:
            if step.element.review_status in REVIEWED:
                continue
            proposal = proposals.get(step.ref)
            checked = sensemaking.validate_work_type_cues(
                [(c.segment_ids, c.quote) for c in proposal.cues] if proposal else [], passages
            )
            tally.dropped_cues += checked.dropped
            if proposal is not None and checked.cues:
                tally.classified += 1
                fields = sensemaking.work_type_fields(proposal.work_type, checked.cues)
            else:
                tally.not_classified += 1
                fields = sensemaking.work_type_fields(None, [])
            map_repo.update_element(session, step.element.id, fields)
        keys = {s.ref: s.element.stable_key for s in steps}
        known = {i.ref: i for i in items}
        for link in output.links:
            item = known.get(link.item_ref)
            refs = [r for r in link.step_refs if r in keys]
            if item is None or not refs:
                tally.dropped_links += 1
                continue
            payload = dict(item.record.payload) | {"about_steps": [keys[r] for r in refs]}
            claims_repo.set_payload(session, item.claim_id, payload)
            tally.links += 1
            # Rule 10: a weakness the SME names is also a constraint on the steps it is about.
            if item.record.claim_type == "capability" and payload.get("kind") == "weakness":
                cause = str(payload.get("cause_type", "none"))
                map_repo.add_constraints(session, [
                    ConstraintRecord(element_id=by_ref[r].element.id,
                                     text=redaction.hide(str(payload.get("text", "")), terms),
                                     provenance=item.record.provenance,
                                     cause_type=None if cause == "none" else cause)
                    for r in refs
                    if by_ref[r].element.review_status not in REVIEWED
                ])  # fmt: skip
                tally.constraints += len(refs)
    return Ok(tally)


def ask(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    *,
    version_id: str,
    job_id: str | None = None,
) -> Result[int]:
    """A validation question for each decision or approval whose work type isn't classified
    (§3.12.4), after the step questions; never twice."""
    with session_scope(sessions) as session:
        if versions_repo.get(session, version_id) is None:
            return Err(ErrorKind.NOT_FOUND, "That version doesn't exist.")
        asked = {(q.reason, q.question) for q in map_repo.questions(session, version_id)}
        new = []
        for e in map_repo.elements(session, version_id):
            if e.kind not in DECIDING or e.work_type_status != sensemaking.NOT_CLASSIFIED:
                continue
            question = NOT_CLASSIFIED_QUESTION.format(label=e.label)
            if ("work_type", question) not in asked:
                new.append(QuestionRecord(element_id=e.id, phase_id=e.phase_id,
                                          question=question, reason="work_type"))  # fmt: skip
        map_repo.add_questions(session, version_id, new)
    return Ok(len(new))
