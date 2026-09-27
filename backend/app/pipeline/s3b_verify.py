"""S3b Verify (PRD §3.7, §3.8 G6): an independent check of every step's claims.

One call per step sees only the step, its claims and the passages each claim cites (names hidden),
nothing else. Verdicts: `supported`; `partial` → the step needs a check (`needs_check`, and S5
asks a validation question); `not_supported` → the claim is rejected with guardrail G6 and taken
off the step. A step left with no claim is removed: nothing unverified reaches the map.
A claim the verifier gives no verdict for is treated as `partial` (checked by Eric, never assumed
fine). With the verifier switched off in Settings, every claim is `not_run` and no call is made.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.config import AppConfig
from app.db import session_scope
from app.domain import ai_schemas
from app.domain.enums import VerifierVerdict
from app.domain.models import AiCallRecord, NameReplacement, PromptSegment
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline import s1_extract
from app.pipeline.context import AiContext, ai_failure, calls_in, record_calls
from app.pipeline.s3_calibrate import StepRef, step_refs
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import ai_service, prompts

Sessions = sessionmaker[Session]

STAGE_ID = "S3b_verify"
NO_VERDICT = "the verifier gave no verdict for this claim"
FORMAT_FAILED = (
    "Claude's answer for 'Independent verification' didn't match the expected format twice. "
    "Nothing was saved. Try again, or use Copy details to report it."
)


@dataclass(slots=True)
class S3bTally:
    supported: int = 0
    partial: int = 0
    rejected: int = 0
    not_run: int = 0
    removed_steps: int = 0


def cited_passages(
    session: Session, steps: list[StepRef], terms: list[NameReplacement]
) -> dict[str, tuple[str, PromptSegment]]:
    """Segment ID → (source kind, the passage as sent: names hidden, speaker by role)."""
    wanted = {s for step in steps for c in step.claims for s in c.record.segment_ids}
    out: dict[str, tuple[str, PromptSegment]] = {}
    for source_id in {c.record.source_id for step in steps for c in step.claims}:
        info = sources_repo.reading_info(session, source_id)
        if info is None:
            continue
        stored = sources_repo.stored_segments(session, source_id)
        for segment in s1_extract.prompt_segments(stored, info.format, terms):
            if segment.segment_id in wanted:
                out[segment.segment_id] = (info.kind, segment)
    return out


def render(step: StepRef, passages: dict[str, tuple[str, PromptSegment]]) -> str:
    esc = prompts.escape
    lines = [
        f'<step kind="{esc(step.element.kind)}" lane="{esc(step.lane)}" '
        f'label="{esc(step.element.label)}"/>'
    ]
    for n, claim in enumerate(step.claims, start=1):
        ref = f"k{n}"
        lines.append(f'<claim id="{ref}">{esc(str(claim.record.payload.get("text", "")))}</claim>')
        cited = [passages[s] for s in claim.record.segment_ids if s in passages]
        kind = cited[0][0] if cited else claim.source_kind
        lines.append(prompts.render_source(ref, kind, [segment for _, segment in cited]))
    return "\n".join(lines)


def blocks_for(
    step: StepRef, passages: dict[str, tuple[str, PromptSegment]]
) -> list[dict[str, object]]:
    return [{"type": "text", "text": render(step, passages)}]


def verify(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    *,
    version_id: str,
    job_id: str | None = None,
) -> Result[S3bTally]:
    tally = S3bTally()
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, "That version doesn't exist.")
        steps = [s for s in step_refs(session, version_id) if s.claims]
        terms = redaction.name_replacements(session, version.engagement_id)
        passages = cited_passages(session, steps, terms)
    if not ctx.verifier_enabled:
        with session_scope(sessions) as session:
            for step in steps:
                for claim in step.claims:
                    claims_repo.set_verdict(
                        session, claim.claim_id, VerifierVerdict.NOT_RUN.value, "", reject=False
                    )
                    tally.not_run += 1
        return Ok(tally)
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

    decided: list[tuple[StepRef, dict[str, ai_schemas.S3bVerdict]]] = []
    for step in steps:
        call = ai_service.StageCall(
            stage_id=STAGE_ID,
            prompt_version=prompt.version,
            system=prompt.text,
            blocks=blocks_for(step, passages),
            output_model=ai_schemas.S3bOutput,
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
        answered = ai_schemas.S3bOutput.model_validate(answer.data).verdicts
        decided.append((step, {v.claim_ref: v for v in answered}))

    with session_scope(sessions) as session:
        for step, verdicts in decided:
            kept = 0
            needs_check = False
            for n, claim in enumerate(step.claims, start=1):
                found = verdicts.get(f"k{n}")
                verdict = found.verdict if found else VerifierVerdict.PARTIAL.value
                reason = redaction.hide(found.reason, terms) if found else NO_VERDICT
                rejected = verdict == VerifierVerdict.NOT_SUPPORTED.value
                claims_repo.set_verdict(session, claim.claim_id, verdict, reason, reject=rejected)
                if rejected:
                    map_repo.unlink_claims(session, [claim.claim_id])
                    tally.rejected += 1
                    continue
                kept += 1
                if verdict == VerifierVerdict.PARTIAL.value:
                    needs_check = True
                    tally.partial += 1
                else:
                    tally.supported += 1
            if kept == 0:
                map_repo.delete_elements(session, [step.element.id])
                tally.removed_steps += 1
            elif needs_check:
                map_repo.update_element(session, step.element.id, {"needs_check": True})
    return Ok(tally)
