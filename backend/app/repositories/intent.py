"""Intent statements (PRD §3.5 `intent_statements`, §3.16; P13a): the only database access."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.reality import IntentRecord
from app.repositories.tables import IntentStatement


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
