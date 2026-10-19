"""What drafting an engagement would probably cost, and the optional spending limit (deep review
item 5, 2026-10-19; API_CONTRACT.md → Draft → estimate, Settings → spending).

The sources are those a draft reads (ready, not a policy or charter); the ratio of tokens to
characters is measured from the last real drafts and refreshes on this computer, or assumed
until there is one (services/cost.py); the price comes from the dated price list Eric can edit.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import settings as settings_action
from app.config import MODEL_PRICES_FILE, AppConfig
from app.db import session_scope
from app.domain.enums import SourceKind
from app.domain.models import DraftEstimate
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import ai_calls
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import sources as sources_repo
from app.services import cost

Sessions = sessionmaker[Session]

MEASURED_JOBS = ("draft", "refresh")  # the job types whose real usage sets the ratio
ENGAGEMENT_MISSING = "That engagement doesn't exist."


def _history(session: Session) -> list[cost.Usage]:
    usage = []
    for version_id, tokens_in, tokens_out in ai_calls.real_usage_by_job(
        session, MEASURED_JOBS, cost.MEASURED_DRAFTS
    ):
        if version_id is None:
            continue
        read = map_repo.version_source_ids(session, version_id)
        usage.append(cost.Usage(sources_repo.text_characters(session, read), tokens_in, tokens_out))
    return usage


def estimate(config: AppConfig, sessions: Sessions, engagement_id: str) -> Result[DraftEstimate]:
    match settings_action.effective_settings(config):
        case Err() as err:
            return err
        case Ok(value=values):
            pass
    try:
        price_text = MODEL_PRICES_FILE.read_text(encoding="utf-8")
    except OSError:
        return Err(ErrorKind.IO, cost.BAD_PRICES)
    match cost.read_prices(price_text):
        case Err() as err:
            return err
        case Ok(value=prices):
            pass
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        charter = SourceKind.POLICY_OR_CHARTER.value
        read = [s.id for s in sources_repo.list_for_engagement(session, engagement_id)
                if s.text_status == "ready" and s.kind != charter]  # fmt: skip
        characters = sources_repo.text_characters(session, read)
        history = _history(session)
    model = values["ANTHROPIC_MODEL"]
    found = cost.estimate(characters, history, model, prices)
    limit = settings_action.draft_cost_limit(values)
    return Ok(DraftEstimate(
        sources=len(read), characters=characters, input_tokens=found.input_tokens,
        output_tokens=found.output_tokens, cost_usd=found.cost_usd, basis=found.basis,
        drafts_measured=found.drafts_measured, model=model, prices_checked_on=prices.checked_on,
        limit_usd=limit,
        over_limit=limit is not None and found.cost_usd is not None and found.cost_usd > limit,
    ))  # fmt: skip


def over_limit(config: AppConfig, sessions: Sessions, engagement_id: str) -> Err | None:
    """The refusal for a draft or refresh whose estimate is above the spending limit, if any. An
    estimate that can't be worked out (no price for the model) never blocks."""
    match estimate(config, sessions, engagement_id):
        case Ok(value=found) if found.over_limit:
            assert found.cost_usd is not None and found.limit_usd is not None
            return Err(
                ErrorKind.CONFLICT,
                f"This draft is estimated at about US${found.cost_usd:,.2f}, above your limit of "
                f"US${found.limit_usd:,.2f}. Raise the limit in Settings, or draft from fewer "
                "sources.",
                {"estimate_usd": found.cost_usd, "limit_usd": found.limit_usd},
                api_code="COST_LIMIT",
            )
        case _:
            return None
