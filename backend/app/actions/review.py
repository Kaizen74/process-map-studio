"""Reviewing a draft's steps (PRD §3.5 versions and locking, §5.7.5, §5.8; phase P6).

Confirm, reject and restore change a step's review status. Confirmed, edited and added steps are
locked: no pipeline run ever writes to them (constraint 8). Only a draft version changes; start
and end come from the scope card. Every change writes an audit row and refreshes the version's
stored lint report, so the quality card and the Lint tab never show a stale state.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import ElementKind, ReviewStatus
from app.domain.graph import ElementDetail
from app.domain.models import AuditEntry
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import elements as map_repo
from app.repositories import versions as versions_repo

Sessions = sessionmaker[Session]

LOCKED = {ReviewStatus.CONFIRMED.value, ReviewStatus.EDITED.value, ReviewStatus.ADDED.value}
STRUCTURAL = {ElementKind.START.value, ElementKind.END.value}
DRAFT_STATE = "draft"

ELEMENT_MISSING = versions_action.ELEMENT_MISSING
NOT_A_DRAFT = "This version is published and can't be changed. Reopen it as a new draft."
STRUCTURAL_STEP = (
    "Start and end come from the engagement's trigger and end point; change them on Setup."
)
RESTORE_FIRST = "This step is rejected. Restore it before confirming it."
NOT_REJECTED = "Only a rejected step can be restored."

ACTIONS = {
    "confirm": "Confirmed step",
    "reject": "Rejected step",
    "restore": "Restored step",
}


def _next_status(action: str, current: str) -> Result[str]:
    if action == "confirm":
        if current == ReviewStatus.REJECTED.value:
            return Err(ErrorKind.CONFLICT, RESTORE_FIRST)
        return Ok(current if current in LOCKED else ReviewStatus.CONFIRMED.value)
    if action == "reject":
        return Ok(ReviewStatus.REJECTED.value)
    if current != ReviewStatus.REJECTED.value:
        return Err(ErrorKind.CONFLICT, NOT_REJECTED)
    return Ok(ReviewStatus.DRAFT.value)


def review(
    config: AppConfig, sessions: Sessions, element_id: str, action: str
) -> Result[ElementDetail]:
    """Confirm, reject or restore one step (`action` is a key of ACTIONS)."""
    actor = actor_name(config)
    with session_scope(sessions) as session:
        element = map_repo.element(session, element_id)
        version_id = map_repo.element_version_id(session, element_id)
        version = versions_repo.get(session, version_id) if version_id else None
        if element is None or version is None:
            return Err(ErrorKind.NOT_FOUND, ELEMENT_MISSING)
        if version.state != DRAFT_STATE:
            return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
        if element.kind in STRUCTURAL:
            return Err(ErrorKind.VALIDATION, STRUCTURAL_STEP, {"field": "kind"})
        match _next_status(action, element.review_status):
            case Err() as err:
                return err
            case Ok(value=status):
                pass
        if status != element.review_status:
            map_repo.update_element(session, element_id, {"review_status": status})
            audit.record(
                session,
                actor=actor,
                action=ACTIONS[action],
                target_type="element",
                target_id=element_id,
                engagement_id=version.engagement_id,
                version_id=version.id,
                before={"review_status": element.review_status},
                after={"review_status": status},
            )
    if status != element.review_status:
        versions_action.lint_version(sessions, version.id)
    return versions_action.get_element(sessions, element_id)


def get_audit(sessions: Sessions, version_id: str) -> Result[list[AuditEntry]]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        terms = redaction.name_replacements(session, version.engagement_id)
        labels = {e.id: e.label for e in map_repo.elements(session, version_id)}
        rows = audit.list_for_version(session, version_id)
    return Ok(
        [
            AuditEntry(
                **row,
                target_label=redaction.hide(labels.get(row["target_id"], ""), terms),
            )
            for row in rows
        ]
    )
