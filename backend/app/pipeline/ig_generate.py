"""IG_generate (PRD §3.12.8, Appendix F.4 role modules, F.8 rule 3; C5b): Claude drafts the role
module of a Landscape guide.

One call sees the scope card, the interviewee's stakeholder group, the engagement's roles, the
latest map's handoffs that involve the group's lane and the bank's L3 to L5 questions; names on the
hidden-names list are replaced before anything is sent. Claude proposes three to five questions;
`interview_templates.check_role_questions` decides which are kept. Nothing here touches the guide.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session, sessionmaker

from app.db import session_scope
from app.domain import ai_schemas
from app.domain.interview import QuestionBank, RoleQuestion
from app.domain.models import AiCallRecord
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline.context import AiContext, ai_failure, calls_in, record_calls
from app.services import ai_service, prompts

Sessions = sessionmaker[Session]

STAGE_ID = "IG_generate"
STAGE_NAME = "Drafting role-module questions"
FORMAT_FAILED = (
    "Claude's answer for 'Drafting role-module questions' didn't match the expected format twice."
)


@dataclass(frozen=True, slots=True)
class RoleModuleInput:
    """What the role module is drafted from, names already hidden by the caller."""

    group: str
    process: str = ""
    trigger: str = ""
    end_point: str = ""
    roles: list[str] = field(default_factory=list)
    handoffs: list[dict[str, str]] = field(default_factory=list)  # from_role, step, to_role


def _tagged(tag: str, value: object) -> str:
    return f"<{tag}>\n{prompts.escape(json.dumps(value, ensure_ascii=False, indent=1))}\n</{tag}>"


def blocks_for(bank: QuestionBank, data: RoleModuleInput) -> list[dict[str, object]]:
    bases = [bank.question(qid) for qid in ("L3", "L4", "L5")]
    text = "\n".join([
        _tagged("scope", {"process": data.process, "trigger": data.trigger,
                          "end_point": data.end_point}),
        _tagged("group", data.group),
        _tagged("roles", data.roles),
        _tagged("handoffs", data.handoffs),
        _tagged("bank", [{"id": q.id, "wording": q.wording, "probes": q.probes,
                          "targets": q.targets} for q in bases]),
    ])  # fmt: skip
    return [{"type": "text", "text": text}]


def draft_role_module(
    sessions: Sessions, ctx: AiContext, bank: QuestionBank, data: RoleModuleInput, job_id: str
) -> Result[list[RoleQuestion]]:
    """Claude's proposed questions (unchecked), or the failure in plain words. Every call made is
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
        blocks=blocks_for(bank, data),
        output_model=ai_schemas.IGOutput,
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
    output = ai_schemas.IGOutput.model_validate(answer.data)
    return Ok([
        RoleQuestion(based_on=q.based_on, wording=q.wording, probes=list(q.probes))
        for q in output.questions
    ])  # fmt: skip
