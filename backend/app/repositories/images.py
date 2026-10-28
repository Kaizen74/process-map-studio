"""Images repository (PRD §3.5 images): pictures on steps, uploaded or suggested from a PDF."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import ElementKind, ImageStatus, ReviewStatus
from app.domain.models import ImageRecord
from app.repositories.tables import (
    Element,
    EvidenceLink,
    Image,
    MapVersion,
    Source,
    SourceSegment,
)


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


def discard_suggested(session: Session, version_id: str) -> int:
    """Mark every open suggestion on the version's steps discarded; returns how many."""
    rows = session.scalars(
        select(Image)
        .join(Element, Element.id == Image.element_id)
        .where(Element.version_id == version_id, Image.status == ImageStatus.SUGGESTED.value)
    ).all()
    for row in rows:
        row.status = ImageStatus.DISCARDED.value
    session.flush()
    return len(rows)


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


# --- Suggestions from PDFs (P8) ------------------------------------------------------------------


def page_matches(session: Session, version_id: str) -> list[tuple[str, ImageRecord]]:
    """(step id, PDF picture saved for the source) for each step of the version (not start, end or
    rejected) whose verified evidence cites a passage on the picture's page of the same source."""
    rows = session.execute(
        select(Element.id, Image)
        .join(EvidenceLink, EvidenceLink.element_id == Element.id)
        .join(SourceSegment, SourceSegment.id == EvidenceLink.segment_id)
        .join(
            Image,
            (Image.source_id == SourceSegment.source_id) & (Image.page == SourceSegment.page),
        )
        .where(
            Element.version_id == version_id,
            Element.kind.not_in([ElementKind.START.value, ElementKind.END.value]),
            Element.review_status != ReviewStatus.REJECTED.value,
            EvidenceLink.verified.is_(True),
            Image.element_id.is_(None),
            Image.origin == "extracted",
        )
        .distinct()
        .order_by(Element.created_at, Element.id, Image.page, Image.stored_path)
    )
    return [(element_id, ImageRecord.model_validate(image)) for element_id, image in rows]


def placed(session: Session, version_id: str) -> set[tuple[str, str]]:
    """(step id, file) for every image row already on the version's steps, any status."""
    rows = session.execute(
        select(Image.element_id, Image.stored_path)
        .join(Element, Element.id == Image.element_id)
        .where(Element.version_id == version_id)
    )
    return {(element_id or "", path) for element_id, path in rows}


def move(session: Session, successors: dict[str, str]) -> None:
    """Move the images of each step to its successor (a refresh replacing an unreviewed step)."""
    for row in session.scalars(select(Image).where(Image.element_id.in_(list(successors)))):
        row.element_id = successors[row.element_id or ""]
    session.flush()


def for_version(session: Session, version_id: str) -> list[ImageRecord]:
    """The version's images that aren't discarded, on steps that aren't rejected; suggestions
    first within a step, then in the order they were added (the caller orders the steps)."""
    rows = session.scalars(
        select(Image)
        .join(Element, Element.id == Image.element_id)
        .where(
            Element.version_id == version_id,
            Element.review_status != ReviewStatus.REJECTED.value,
            Image.status != "discarded",
        )
        .order_by((Image.status != "suggested"), Image.created_at, Image.id)
    )
    return [ImageRecord.model_validate(r) for r in rows]
