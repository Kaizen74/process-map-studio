"""Map versions repository (PRD §3.5 map_versions): drafts and published versions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import VersionView
from app.repositories.tables import MapVersion


def _view(row: MapVersion) -> VersionView:
    return VersionView(
        id=row.id,
        engagement_id=row.engagement_id,
        label=row.label,
        state=row.state,
        created_at=row.created_at,
    )


def create(session: Session, *, engagement_id: str, label: str, state: str) -> VersionView:
    row = MapVersion(engagement_id=engagement_id, label=label, state=state)
    session.add(row)
    session.flush()
    return _view(row)


def get(session: Session, version_id: str) -> VersionView | None:
    row = session.get(MapVersion, version_id)
    return _view(row) if row else None


def current_draft(session: Session, engagement_id: str) -> VersionView | None:
    """The engagement's one draft, if any (PRD §3.5: at most one draft at a time)."""
    row = session.scalars(
        select(MapVersion)
        .where(MapVersion.engagement_id == engagement_id)
        .where(MapVersion.state == "draft")
        .order_by(MapVersion.created_at.desc(), MapVersion.id)
    ).first()
    return _view(row) if row else None


def delete(session: Session, version_id: str) -> None:
    row = session.get(MapVersion, version_id)
    if row is not None:
        session.delete(row)
        session.flush()
