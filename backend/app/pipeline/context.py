"""What every AI stage needs (PRD §3.4, §3.7): the connection, the model and what it supports.

Gathered once per run from Settings and the Models API, so a draft uses one model throughout.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.actions.settings import effective_settings
from app.config import AppConfig
from app.domain.models import AiCallRecord
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import ai_calls
from app.repositories import engagements as engagements_repo
from app.services import ai_service

NO_KEY = "Add your Claude API key in Settings first."
KEY_REJECTED = "Your API key was rejected — check Settings."
BUSY = "Anthropic is busy at the moment. Nothing was saved. Try again in a few minutes."
UNREACHABLE = (
    "The app couldn't reach Anthropic. Check your internet connection, then try again. "
    "Nothing was saved."
)


@dataclass(frozen=True, slots=True)
class AiContext:
    conn: ai_service.AiConnection
    model: str
    effort: str | None
    structured_outputs: bool
    pdf_input: bool
    verifier_enabled: bool = True  # S3b, the independent verifier (Settings, on by default)


def _flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def ai_failure(err: Err) -> Err:
    """Plain words for failures that aren't about one answer's format (PRD §3.7)."""
    if err.kind is ErrorKind.AI_AUTH:
        return Err(ErrorKind.AI_AUTH, KEY_REJECTED, err.details)
    if err.kind is ErrorKind.AI_RATE_LIMIT:
        return Err(ErrorKind.AI_RATE_LIMIT, BUSY, err.details)
    if err.kind is ErrorKind.AI_FORMAT:
        return err
    return Err(ErrorKind.IO, UNREACHABLE, err.details)


def ai_context(config: AppConfig) -> Result[AiContext]:
    match effective_settings(config):
        case Err() as err:
            return err
        case Ok(value=values):
            pass
    key = values["ANTHROPIC_API_KEY"].strip()
    mock = _flag(values["MOCK_CLAUDE"])
    if not key and not mock:
        return Err(ErrorKind.VALIDATION, NO_KEY, {"field": "api_key"})
    conn = ai_service.AiConnection(api_key=key, mock=mock, fixtures_dir=config.mock_fixtures_dir)
    model = values["ANTHROPIC_MODEL"]
    match ai_service.get_model(conn, model):
        case Err(kind=ErrorKind.NOT_FOUND) as err:
            return Err(
                ErrorKind.VALIDATION,
                f"The model {model} isn't available to your API key. Choose another in Settings.",
                err.details,
            )
        case Err() as err:
            return ai_failure(err)
        case Ok(value=summary):
            pass
    effort = values["ANTHROPIC_EFFORT"]
    return Ok(
        AiContext(
            conn=conn,
            model=model,
            effort=effort if effort in summary.effort_levels else None,
            structured_outputs=summary.structured_outputs,
            pdf_input=summary.pdf_input,
            verifier_enabled=_flag(values["VERIFIER_ENABLED"]),
        )
    )


def role_groups(session: Session, engagement_id: str) -> list[list[str]]:
    """Each role's name followed by its aliases (for the G5 role check)."""
    return [[r.name, *r.aliases] for r in engagements_repo.list_roles(session, engagement_id)]


def record_calls(session: Session, job_id: str | None, calls: list[AiCallRecord]) -> None:
    ai_calls.add(session, job_id, calls)


def calls_in(err: Err) -> list[AiCallRecord]:
    """The usage records a failed call still carries (they cost tokens too)."""
    raw = err.details.get("calls", [])
    return [AiCallRecord.model_validate(c) for c in raw] if isinstance(raw, list) else []
