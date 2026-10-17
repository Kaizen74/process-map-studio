"""SR_align (PRD §3.13.4; R5a): Claude's pass over the log activities the deterministic pass
could not match.

One call sees those activity names (with volumes and their usual role), the current map's steps
and the glossary terms, names on the hidden-names list already replaced by the caller; never an
event, a case ID or a figure per person. Claude proposes matches; `log_alignment.check_suggestions`
decides which are kept, and nothing is applied until Eric confirms.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session, sessionmaker

from app.db import session_scope
from app.domain import ai_schemas
from app.domain.models import AiCallRecord
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline.context import AiContext, ai_failure, calls_in, record_calls
from app.services import ai_service, prompts
from app.services.log_alignment import ActivityInfo, StepInfo, Suggestion

Sessions = sessionmaker[Session]

STAGE_ID = "SR_align"
STAGE_NAME = "Suggesting matches for system activities"
FORMAT_FAILED = (
    "Claude's answer for 'Suggesting matches for system activities' didn't match the expected "
    "format twice. Nothing was saved. Try again, or use Copy details to report it."
)


@dataclass(frozen=True, slots=True)
class AlignInput:
    """What Claude sees, names already hidden by the caller."""

    activities: list[ActivityInfo]
    steps: list[StepInfo]
    glossary: list[dict[str, str]] = field(default_factory=list)  # term, plain_meaning


def _tagged(tag: str, value: object) -> str:
    return f"<{tag}>\n{prompts.escape(json.dumps(value, ensure_ascii=False, indent=1))}\n</{tag}>"


def blocks_for(data: AlignInput) -> list[dict[str, object]]:
    text = "\n".join([
        _tagged("activities", [{"name": a.name, "events": a.events, "cases": a.cases,
                                "usual_role": a.role or ""} for a in data.activities]),
        _tagged("steps", [{"key": s.key, "label": s.label, "kind": s.kind,
                           "lane_role": s.lane_role or ""} for s in data.steps]),
        _tagged("glossary", data.glossary),
    ])  # fmt: skip
    return [{"type": "text", "text": text}]


def suggest(sessions: Sessions, ctx: AiContext, data: AlignInput,
            job_id: str) -> Result[list[Suggestion]]:  # fmt: skip
    """Claude's suggestions (unchecked), or the failure in plain words. Every call made is
    recorded against the job, successful or not."""
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
        blocks=blocks_for(data),
        output_model=ai_schemas.SROutput,
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
    output = ai_schemas.SROutput.model_validate(answer.data)
    return Ok([Suggestion(m.activity, m.step_key, m.reason) for m in output.matches])
