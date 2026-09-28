"""Images repository (PRD §3.5 images): pictures on steps, uploaded or suggested from a PDF."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import ImageRecord
from app.repositories.tables import Element, Image, MapVersion, Source


def add(session: Session, record: ImageRecord) -> ImageRecord:
    row = Image(**record.model_dump(exclude={"id", "created_at"}))
    session.add(row)
    session.flush()
    return ImageRecord.model_validate(row)


def get(session: Session, image_id: str) -> ImageRecord | None:
    row = session.get(Image, image_id)
    return ImageRecord.model_validate(row) if row else None


def for_element(session: Session, element_id: str) -> list[ImageRecord]:
    """Not discarded; suggestions first, then in the order they were added."""
    rows = session.scalars(
        select(Image)
        .where(Image.element_id == element_id, Image.status != "discarded")
        .order_by((Image.status != "suggested"), Image.created_at, Image.id)
    )
    return [ImageRecord.model_validate(r) for r in rows]


def update(session: Session, image_id: str, fields: dict[str, Any]) -> ImageRecord:
    row = session.get(Image, image_id)
    assert row is not None
    for key, value in fields.items():
        setattr(row, key, value)
    session.flush()
    return ImageRecord.model_validate(row)


def delete(session: Session, image_id: str) -> None:
    row = session.get(Image, image_id)
    if row is not None:
        session.delete(row)
        session.flush()


def path_users(session: Session, stored_path: str) -> int:
    """How many image rows use this file (reopened drafts share files with their version)."""
    return (
        session.scalar(
            select(func.count()).select_from(Image).where(Image.stored_path == stored_path)
        )
        or 0
    )


def owner(session: Session, element_id: str) -> tuple[str, str, str] | None:
    """(version_id, version state, engagement_id) of an element."""
    row = session.execute(
        select(Element.version_id, MapVersion.state, MapVersion.engagement_id)
        .join(MapVersion, MapVersion.id == Element.version_id)
        .where(Element.id == element_id)
    ).first()
    return (row[0], row[1], row[2]) if row else None


def source_names(session: Session, source_ids: list[str]) -> dict[str, str]:
    if not source_ids:
        return {}
    rows = session.execute(select(Source.id, Source.filename).where(Source.id.in_(source_ids)))
    return {sid: name for sid, name in rows}
