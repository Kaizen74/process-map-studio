"""What we are testing (DECISIONS 95): the only database access for `testing_items`."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.compass import TestingItem
from app.repositories.tables import TestingItem as Row


def _view(row: Row) -> TestingItem:
    return TestingItem(
        id=row.id, ref=row.ref, text=row.text, refuted_by=row.refuted_by, origin=row.origin,
        verdict=row.verdict, evidence_refs=list(row.evidence_refs), note=row.note,
    )  # fmt: skip


def _rows(session: Session, engagement_id: str) -> list[Row]:
    query = select(Row).where(Row.engagement_id == engagement_id)
    return list(session.scalars(query.order_by(Row.created_at, Row.ref, Row.id)))


def list_for(session: Session, engagement_id: str) -> list[TestingItem]:
    """In the order added (principles as the hand-off lists them, then Eric's own)."""

    def place(row: Row) -> tuple[int, str, int, str]:
        digits = "".join(ch for ch in row.ref if ch.isdigit())
        first = row.origin == "compass"  # created together, so by their number
        return (0 if first else 1, "" if first else row.created_at, int(digits or 0), row.ref)

    return [_view(r) for r in sorted(_rows(session, engagement_id), key=place)]


def add(
    session: Session, engagement_id: str, *, ref: str, text: str, refuted_by: str, origin: str
) -> TestingItem:
    row = Row(engagement_id=engagement_id, ref=ref, text=text, refuted_by=refuted_by,
              origin=origin, verdict="open", evidence_refs=[], note="")  # fmt: skip
    session.add(row)
    session.flush()
    return _view(row)


def get(session: Session, item_id: str) -> tuple[str, TestingItem] | None:
    """(engagement ID, item) or None."""
    row = session.get(Row, item_id)
    return (row.engagement_id, _view(row)) if row else None


def update(session: Session, item_id: str, fields: dict[str, Any]) -> TestingItem | None:
    row = session.get(Row, item_id)
    if row is None:
        return None
    for name, value in fields.items():
        setattr(row, name, value)
    session.flush()
    return _view(row)


def delete(session: Session, item_id: str) -> None:
    row = session.get(Row, item_id)
    if row is not None:
        session.delete(row)
        session.flush()
