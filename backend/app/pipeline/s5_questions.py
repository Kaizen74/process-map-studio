"""S5 Questions (PRD §3.7, §3.8 G7-G8): validation questions for the offline SME session.

Which steps need a question is decided here, deterministically, one question per step with its
most important reason: contested (or trace contradicted) → documented only → inferred → partial
support from the verifier (`needs_check`) → low confidence (below 0.50). At most six step
questions per phase. Every unknown Claude raised in S1 becomes a question with reason `gap` as it
was asked (G8), however many there are, except one about another flow (DECISIONS 83): on a map
whose drafting set claims about other flows aside, an unknown that points only at passages no
step of the map uses is set aside with them (`questions_aside`), listed, never dropped.

Claude only words the step questions. A question that names a number the step's claims and
divergence notes don't state is replaced by a plain template; names are scrubbed (G10). When no
step needs a question, no call is made.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.config import AppConfig
from app.db import session_scope
from app.domain import ai_schemas
from app.domain.enums import Provenance, ReviewStatus, SourceKind, SourceState
from app.domain.graph import QuestionRecord
from app.domain.models import AiCallRecord
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline.context import AiContext, ai_failure, calls_in, record_calls
from app.pipeline.s2_canonicalise import claims_text
from app.pipeline.s3_calibrate import StepRef, step_refs
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import versions as versions_repo
from app.services import ai_service, calibration, grounding, prompts

Sessions = sessionmaker[Session]

STAGE_ID = "S5_questions"
PER_PHASE = 6
TEMPLATES = {
    "contested": 'The sources disagree about "{label}". Which version is right in practice?',
    "documented_only": (
        'The documents describe "{label}", but the interview doesn\'t mention it. Is it done in '
        "practice?"
    ),
    "inferred": '"{label}" was inferred from the sources rather than stated. Is it right?',
    "partial_support": (
        'The independent check found only partial support for "{label}". Is it described correctly?'
    ),
    "low_confidence": 'The evidence for "{label}" is thin. How is this step done in practice?',
}
# A map drafted from documents alone (Eric, 2026-10-20) has no interview to be silent.
NO_INTERVIEW_TEMPLATES = TEMPLATES | {
    "documented_only": (
        'The documents describe "{label}"; no interview has described it yet. Is it done this way '
        "in practice?"
    ),
}
FORMAT_FAILED = (
    "Claude's answer for 'Writing validation questions' didn't match the expected format twice. "
    "Nothing was saved. Try again, or use Copy details to report it."
)


@dataclass(slots=True)
class S5Tally:
    questions: int = 0
    gaps: int = 0
    templated: int = 0


@dataclass(frozen=True, slots=True)
class Needed:
    ref: str
    step: StepRef
    reason: str
    notes: tuple[str, ...]


def reason_for(step: StepRef) -> str | None:
    """The most important reason to ask about a step, or None."""
    e = step.element
    if e.source_state in {SourceState.CONTESTED.value, SourceState.TRACE_CONTRADICTED.value}:
        return "contested"
    if e.source_state == SourceState.DOCUMENTED_ONLY.value:
        return "documented_only"
    if e.provenance == Provenance.INFERRED.value:
        return "inferred"
    if e.needs_check:
        return "partial_support"
    if e.confidence is not None and e.confidence < calibration.LOW_CONFIDENCE:
        return "low_confidence"
    return None


def needed(session: Session, version_id: str) -> list[Needed]:
    """The steps that need a question, at most `PER_PHASE` per phase, in priority order."""
    notes: dict[str, list[str]] = {}
    for p in map_repo.evidence(session, version_id):
        if p.evidence.element_id and p.evidence.note:
            notes.setdefault(p.evidence.element_id, []).append(p.evidence.note)
    order = list(TEMPLATES)
    candidates = []
    for step in step_refs(session, version_id):
        if step.element.review_status == ReviewStatus.REJECTED.value:
            continue
        reason = reason_for(step)
        if reason is not None:
            candidates.append((step, reason))
    candidates.sort(key=lambda c: order.index(c[1]))  # stable: process order within a reason
    per_phase: dict[str | None, int] = {}
    kept = []
    for step, reason in candidates:
        phase = step.element.phase_id
        if per_phase.get(phase, 0) >= PER_PHASE:
            continue
        per_phase[phase] = per_phase.get(phase, 0) + 1
        kept.append((step, reason))
    by_process = {s.element.id: n for n, s in enumerate(step_refs(session, version_id))}
    kept.sort(key=lambda c: by_process[c[0].element.id])
    return [
        Needed(ref=f"q{n}", step=step, reason=reason,
               notes=tuple(dict.fromkeys(notes.get(step.element.id, []))))
        for n, (step, reason) in enumerate(kept, start=1)
    ]  # fmt: skip


def render(items: list[Needed]) -> str:
    esc = prompts.escape
    lines = ["<needed>"]
    for item in items:
        e = item.step.element
        lines.append(
            f'<item id="{item.ref}" reason="{item.reason}" kind="{esc(e.kind)}" '
            f'lane="{esc(item.step.lane)}" step="{esc(e.label)}">'
        )
        lines += [
            f"<claim>{esc(str(c.record.payload.get('text', '')))}</claim>" for c in item.step.claims
        ]
        lines += [f"<divergence>{esc(note)}</divergence>" for note in item.notes]
        lines.append("</item>")
    lines.append("</needed>")
    return "\n".join(lines)


def blocks_for(items: list[Needed]) -> list[dict[str, object]]:
    return [{"type": "text", "text": render(items)}]


def questions_aside(asked: list[list[str]], used: set[str], *, claims_aside: bool) -> list[int]:
    """Which of the reading's open questions are about another flow (their indexes): only when
    drafting set claims about other flows aside (the documents describe more than this flow), and
    only a question whose passages are all ones no step of this map uses. A question with no
    passage stays: nothing says where it belongs."""
    if not claims_aside:
        return []
    return [n for n, segments in enumerate(asked) if segments and not set(segments) & used]


def ask(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    *,
    version_id: str,
    job_id: str | None = None,
) -> Result[S5Tally]:
    tally = S5Tally()
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, "That version doesn't exist.")
        items = needed(session, version_id)
        rows = claims_repo.unknown_rows(session, version_id)
        claims_aside = bool(claims_repo.outside_flow_rows(session, version_id))
        on_map = {p.evidence.segment_id for p in map_repo.evidence(session, version_id)}
        on_map |= {s for step in step_refs(session, version_id) for c in step.claims
                   for s in c.record.segment_ids}  # fmt: skip
        aside = questions_aside([r.segment_ids for _, r in rows], on_map, claims_aside=claims_aside)
        claims_repo.set_unknowns_outside_flow(session, [rows[i][0] for i in aside])
        unknowns = [r for i, (_, r) in enumerate(rows) if i not in set(aside)]
        terms = redaction.name_replacements(session, version.engagement_id)
        interviewed = SourceKind.INTERVIEW_TRANSCRIPT.value in versions_repo.source_kinds(
            session, version_id
        )
    templates = TEMPLATES if interviewed else NO_INTERVIEW_TEMPLATES

    worded: dict[str, str] = {}
    if items:
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
            blocks=blocks_for(items),
            output_model=ai_schemas.S5Output,
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
        worded = {
            q.ref: q.question for q in ai_schemas.S5Output.model_validate(answer.data).questions
        }

    questions = []
    for item in items:
        text = grounding.redact_text(worded.get(item.ref, "").strip(), terms).text
        allowed = claims_text(list(item.step.claims)) + "\n" + "\n".join(item.notes)
        if not text or not grounding.verify_numbers(text, allowed).passed:
            text = templates[item.reason].format(label=item.step.element.label)
            tally.templated += 1
        questions.append(
            QuestionRecord(element_id=item.step.element.id, phase_id=item.step.element.phase_id,
                           question=text, reason=item.reason)
        )  # fmt: skip
    # G8: every unknown becomes a question, as Claude asked it (names already hidden in S1).
    questions += [
        QuestionRecord(question=redaction.hide(u.question, terms), reason="gap") for u in unknowns
    ]
    with session_scope(sessions) as session:
        map_repo.add_questions(session, version_id, questions)
    tally.questions = len(questions)
    tally.gaps = len(unknowns)
    return Ok(tally)
