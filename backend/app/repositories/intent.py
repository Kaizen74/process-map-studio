"""Intent statements (PRD §3.5 `intent_statements`, §3.16; P13a): the only database access."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.reality import IntentConflictRecord, IntentRecord
from app.repositories.tables import IntentConflict, IntentStatement


def add(session: Session, fields: dict[str, Any]) -> IntentRecord:
    row = IntentStatement(**fields)
    session.add(row)
    session.flush()
    return IntentRecord.model_validate(row)


def get(session: Session, intent_id: str) -> IntentRecord | None:
    row = session.get(IntentStatement, intent_id)
    return IntentRecord.model_validate(row) if row else None


def for_engagement(session: Session, engagement_id: str) -> list[IntentRecord]:
    rows = session.scalars(
        select(IntentStatement)
        .where(IntentStatement.engagement_id == engagement_id)
        .order_by(IntentStatement.created_at, IntentStatement.id)
    )
    return [IntentRecord.model_validate(r) for r in rows]


def update(session: Session, intent_id: str, fields: dict[str, Any]) -> IntentRecord:
    row = session.get(IntentStatement, intent_id)
    assert row is not None
    for name, value in fields.items():
        setattr(row, name, value)
    session.flush()
    return IntentRecord.model_validate(row)


def delete(session: Session, intent_id: str) -> None:
    row = session.get(IntentStatement, intent_id)
    if row is not None:
        session.delete(row)
        session.flush()


def delete_proposed_documents(session: Session, engagement_id: str) -> None:
    """Earlier S1 intent proposals Eric hasn't decided (a rerun replaces them)."""
    rows = session.scalars(
        select(IntentStatement).where(
            IntentStatement.engagement_id == engagement_id,
            IntentStatement.origin == "document",
            IntentStatement.status == "proposed",
        )
    )
    for row in rows:
        session.delete(row)
    session.flush()


# --- Design gaps proposed by IX_compare (intent_conflicts) -------------------------------------


def add_conflict(session: Session, fields: dict[str, Any]) -> IntentConflictRecord:
    row = IntentConflict(**fields)
    session.add(row)
    session.flush()
    return IntentConflictRecord.model_validate(row)


def get_conflict(session: Session, conflict_id: str) -> IntentConflictRecord | None:
    row = session.get(IntentConflict, conflict_id)
    return IntentConflictRecord.model_validate(row) if row else None


def conflicts(session: Session, version_id: str) -> list[IntentConflictRecord]:
    rows = session.scalars(
        select(IntentConflict)
        .where(IntentConflict.version_id == version_id)
        .order_by(IntentConflict.created_at, IntentConflict.id)
    )
    return [IntentConflictRecord.model_validate(r) for r in rows]


def update_conflict(
    session: Session, conflict_id: str, fields: dict[str, Any]
) -> IntentConflictRecord:
    row = session.get(IntentConflict, conflict_id)
    assert row is not None
    for name, value in fields.items():
        setattr(row, name, value)
    session.flush()
    return IntentConflictRecord.model_validate(row)


def delete_proposed_conflicts(session: Session, version_id: str) -> None:
    """Earlier IX_compare proposals Eric hasn't decided (a rerun replaces them)."""
    rows = session.scalars(
        select(IntentConflict).where(
            IntentConflict.version_id == version_id, IntentConflict.status == "proposed"
        )
    )
    for row in rows:
        session.delete(row)
    session.flush()
