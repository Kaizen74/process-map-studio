"""Discrepancy items (PRD §3.5 `discrepancy_items`, §3.17.6; P13a): the only database access."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.reality import DiscrepancyItemRecord
from app.repositories.tables import DiscrepancyItem


def for_engagement(session: Session, engagement_id: str) -> list[DiscrepancyItemRecord]:
    rows = session.scalars(
        select(DiscrepancyItem)
        .where(DiscrepancyItem.engagement_id == engagement_id)
        .order_by(DiscrepancyItem.created_at, DiscrepancyItem.id)
    )
    return [DiscrepancyItemRecord.model_validate(r) for r in rows]


def add(session: Session, fields: dict[str, Any]) -> DiscrepancyItemRecord:
    row = DiscrepancyItem(**fields)
    session.add(row)
    session.flush()
    return DiscrepancyItemRecord.model_validate(row)


def get(session: Session, item_id: str) -> DiscrepancyItemRecord | None:
    row = session.get(DiscrepancyItem, item_id)
    return DiscrepancyItemRecord.model_validate(row) if row else None


def update(session: Session, item_id: str, fields: dict[str, Any]) -> DiscrepancyItemRecord:
    row = session.get(DiscrepancyItem, item_id)
    assert row is not None
    for name, value in fields.items():
        setattr(row, name, value)
    session.flush()
    return DiscrepancyItemRecord.model_validate(row)
