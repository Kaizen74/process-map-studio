"""CC_match (PRD §3.19; DECISIONS 98): Claude's pass over the steps of two countries' published maps
of the same process that the deterministic pass left unpaired.

One call sees those steps (key, label, kind, lane role, phase, order), names already hidden by the
caller with each engagement's own list; never a quote, a source or a figure. Claude suggests
pairs; `comparisons.check_suggestions` keeps only pairs of existing, unpaired keys, and nothing is
applied until Eric confirms.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.db import session_scope
from app.domain import ai_schemas
from app.domain.models import AiCallRecord
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline.context import AiContext, ai_failure, calls_in, record_calls
from app.services import ai_service, prompts
from app.services.country_compare import Step

Sessions = sessionmaker[Session]

STAGE_ID = "CC_match"
STAGE_NAME = "Suggesting step pairs between the two maps"
FORMAT_FAILED = (
    "Claude's answer for 'Suggesting step pairs between the two maps' didn't match the expected "
    "format twice. Nothing was saved. Try again, or use Copy details to report it."
)


@dataclass(frozen=True, slots=True)
class Suggestion:
    reference_key: str
    other_key: str
    reason: str


def _tagged(tag: str, value: object) -> str:
    return f"<{tag}>\n{prompts.escape(json.dumps(value, ensure_ascii=False, indent=1))}\n</{tag}>"


def _rows(steps: list[Step]) -> list[dict[str, object]]:
    return [
        {
            "key": s.key,
            "label": s.label,
            "kind": s.kind,
            "lane_role": s.lane,
            "phase": s.phase,
            "order": s.order,
        }
        for s in steps
    ]


def blocks_for(reference: list[Step], other: list[Step]) -> list[dict[str, object]]:
    text = "\n".join([_tagged("reference", _rows(reference)), _tagged("other", _rows(other))])
    return [{"type": "text", "text": text}]


def suggest(
    sessions: Sessions, ctx: AiContext, reference: list[Step], other: list[Step], job_id: str
) -> Result[list[Suggestion]]:
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
        blocks=blocks_for(reference, other),
        output_model=ai_schemas.CCOutput,
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
    output = ai_schemas.CCOutput.model_validate(answer.data)
    return Ok([Suggestion(p.reference_key, p.other_key, p.reason) for p in output.pairs])
