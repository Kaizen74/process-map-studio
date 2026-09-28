"""Validation questions for the offline SME session (PRD §5.7.10 Questions tab; phase P6)."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.actions.review import DRAFT_STATE, NOT_A_DRAFT
from app.config import AppConfig
from app.db import session_scope
from app.domain.models import QuestionView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import elements as map_repo
from app.repositories import versions as versions_repo

Sessions = sessionmaker[Session]

QUESTION_MISSING = "That question doesn't exist."
STATUSES = {"open": "Reopened question", "answered": "Marked question answered"}


def question_views(session: Session, version_id: str, engagement_id: str) -> list[QuestionView]:
    terms = redaction.name_replacements(session, engagement_id)
    labels = {e.id: e.label for e in map_repo.elements(session, version_id)}
    phases = {p.id: p.name for p in map_repo.phases(session, version_id)}
    return [
        QuestionView(
            id=q.id,
            element_id=q.element_id,
            element_label=redaction.hide(labels.get(q.element_id or "", ""), terms),
            phase_id=q.phase_id,
            phase_name=redaction.hide(phases.get(q.phase_id or "", ""), terms),
            question=redaction.hide(q.question, terms),
            reason=q.reason,
            status=q.status,
        )
        for q in map_repo.questions(session, version_id)
    ]


def list_questions(sessions: Sessions, version_id: str) -> Result[list[QuestionView]]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        return Ok(question_views(session, version.id, version.engagement_id))


def set_status(
    config: AppConfig, sessions: Sessions, question_id: str, status: str
) -> Result[QuestionView]:
    if status not in STATUSES:
        return Err(ErrorKind.VALIDATION, "A question is open or answered.", {"field": "status"})
    actor = actor_name(config)
    with session_scope(sessions) as session:
        found = map_repo.question(session, question_id)
        version = versions_repo.get(session, found[0]) if found else None
        if found is None or version is None:
            return Err(ErrorKind.NOT_FOUND, QUESTION_MISSING)
        if version.state != DRAFT_STATE:
            return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
        before = found[1].status
        if before != status:
            map_repo.set_question_status(session, question_id, status)
            audit.record(
                session,
                actor=actor,
                action=STATUSES[status],
                target_type="question",
                target_id=question_id,
                engagement_id=version.engagement_id,
                version_id=version.id,
                before={"status": before},
                after={"status": status},
            )
        view = next(q for q in question_views(session, version.id, version.engagement_id)
                    if q.id == question_id)  # fmt: skip
    return Ok(view)
