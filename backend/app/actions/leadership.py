"""The leadership view (PRD §4 Views, §5.4 Leadership; API_CONTRACT.md → Leadership view).

Worked out from a published version's graph on every request (`services/leadership.py`); only
Eric's "Decision needed" lines are stored. A draft is refused: the view shows a validated map.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import reality
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.leadership import DecisionNeeded, LeadershipView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import leadership as repo
from app.repositories import versions as versions_repo
from app.services import leadership

Sessions = sessionmaker[Session]

VERSION_MISSING = "That version doesn't exist."
NOT_PUBLISHED = (
    "The leadership view shows a published map. Publish this draft first, then open Leadership."
)
ONLY_SYSTEMIC = "Decisions are recorded for systemic causes only."
TOO_LONG = "Keep each decision under 500 characters."
MAX_TEXT = 500
SHOWN = ("published", "superseded")


def _view(session: Session, version_id: str) -> Result[LeadershipView]:
    version = versions_repo.get(session, version_id)
    if version is None:
        return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
    if version.state not in SHOWN:
        return Err(ErrorKind.CONFLICT, NOT_PUBLISHED)
    graph = versions_action.build_graph(session, version_id)
    if graph is None:
        return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
    return Ok(leadership.leadership_view(graph, repo.decisions(session, version_id)))


def get_view(config: AppConfig, sessions: Sessions, version_id: str) -> Result[LeadershipView]:
    """The view, with the figures it shares with the Reality views read from the version's
    frozen Reality snapshot while that switch is on (G17)."""
    with session_scope(sessions) as session:
        match _view(session, version_id):
            case Err() as err:
                return err
            case Ok(value=view):
                pass
        if reality.enabled(config):
            version = versions_repo.get(session, version_id)
            assert version is not None
            view.reality = reality.leadership_figures(session, version)
        return Ok(view)


def save_decisions(
    config: AppConfig, sessions: Sessions, version_id: str, lines: list[DecisionNeeded]
) -> Result[list[DecisionNeeded]]:
    with session_scope(sessions) as session:
        match _view(session, version_id):
            case Err() as err:
                return err
            case Ok(value=view):
                pass
        systemic = {c.cause_type for c in view.interpretation.causes if c.systemic}
        if any(line.cause_type not in systemic for line in lines):
            return Err(ErrorKind.VALIDATION, ONLY_SYSTEMIC, {"field": "cause_type"})
        if any(len(line.text.strip()) > MAX_TEXT for line in lines):
            return Err(ErrorKind.VALIDATION, TOO_LONG, {"field": "text"})
        before = repo.decisions(session, version_id)
        after = {line.cause_type: line.text.strip() for line in lines}
        repo.replace(session, version_id, after)
        version = versions_repo.get(session, version_id)
        audit.record(
            session,
            actor=actor_name(config),
            action="Saved leadership decisions",
            target_type="version",
            target_id=version_id,
            engagement_id=version.engagement_id if version else None,
            version_id=version_id,
            before=before,
            after={k: v for k, v in after.items() if v},
        )
        saved = repo.decisions(session, version_id)
        return Ok(
            [
                DecisionNeeded(cause_type=c, text=saved.get(c, ""))
                for c in (d.cause_type for d in view.recommendation.decisions_needed)
            ]
        )
