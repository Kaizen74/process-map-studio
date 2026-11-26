"""Eric's own suggested probes (DECISIONS 113): the only database access for `owner_probes`."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.interview import OwnerProbe
from app.repositories.tables import OwnerProbe as Row


def _view(row: Row) -> OwnerProbe:
    return OwnerProbe(id=row.id, text=row.text, about=row.about)


def list_for(session: Session, engagement_id: str) -> list[OwnerProbe]:
    """In the order added."""
    query = select(Row).where(Row.engagement_id == engagement_id)
    return [_view(r) for r in session.scalars(query.order_by(Row.created_at, Row.id))]


def add(session: Session, engagement_id: str, text: str, about: str) -> OwnerProbe:
    row = Row(engagement_id=engagement_id, text=text, about=about)
    session.add(row)
    session.flush()
    return _view(row)


def get(session: Session, probe_id: str) -> tuple[str, OwnerProbe] | None:
    """(engagement ID, probe) or None."""
    row = session.get(Row, probe_id)
    return (row.engagement_id, _view(row)) if row else None


def update(session: Session, probe_id: str, fields: dict[str, str]) -> OwnerProbe | None:
    row = session.get(Row, probe_id)
    if row is None:
        return None
    for key, value in fields.items():
        setattr(row, key, value)
    session.flush()
    return _view(row)


def delete(session: Session, probe_id: str) -> None:
    row = session.get(Row, probe_id)
    if row is not None:
        session.delete(row)
        session.flush()
