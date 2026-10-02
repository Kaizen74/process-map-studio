"""S4b Translate (PRD §3.12.10 step C rules 1-7, §3.12.11): the two views of the assembled map.

Deterministic, no AI call (the work is in `actions/view_translation.py`, which also brings the
views up to date after every edit). `translate` runs in the "build" stage after S4: every step
and line gets its view membership and every line its sequence basis; where one view leaves out
the other view's steps, the line that view needs is added (provenance I): in As documented a plain
line; in As done a line only when the lived account states the order, otherwise a "not described"
connector (kind `gap`), never an invented step. `ask` runs after S5: lines resting only on the
order of mentioning, and "not described" connectors, become validation questions.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import view_translation
from app.actions.view_translation import Tally
from app.config import AppConfig
from app.db import session_scope
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline.context import AiContext
from app.repositories import versions as versions_repo

Sessions = sessionmaker[Session]

MISSING = "That version doesn't exist."


def translate(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    *,
    version_id: str,
    job_id: str | None = None,
) -> Result[Tally]:
    with session_scope(sessions) as session:
        if versions_repo.get(session, version_id) is None:
            return Err(ErrorKind.NOT_FOUND, MISSING)
        return Ok(view_translation.update_views(session, version_id))


def ask(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    *,
    version_id: str,
    job_id: str | None = None,
) -> Result[Tally]:
    with session_scope(sessions) as session:
        if versions_repo.get(session, version_id) is None:
            return Err(ErrorKind.NOT_FOUND, MISSING)
        return Ok(Tally(questions=view_translation.add_questions(session, version_id)))
