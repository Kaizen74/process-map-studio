"""Cause library repository (PRD §3.5 cause_library): engagement-level entries per step key and
divergence type."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import CauseRecord
from app.repositories.tables import CauseLibraryEntry, Element, MapVersion


def keys(session: Session, engagement_id: str) -> set[tuple[str, str]]:
    """(step key, divergence type) of every entry the engagement already has."""
    rows = session.execute(
        select(CauseLibraryEntry.element_stable_key, CauseLibraryEntry.divergence_type).where(
            CauseLibraryEntry.engagement_id == engagement_id
        )
    )
    return {(key, divergence) for key, divergence in rows}


def add(session: Session, record: CauseRecord) -> CauseRecord:
    row = CauseLibraryEntry(**record.model_dump(exclude={"id", "created_at"}))
    session.add(row)
    session.flush()
    return CauseRecord.model_validate(row)


def get(session: Session, cause_id: str) -> CauseRecord | None:
    row = session.get(CauseLibraryEntry, cause_id)
    return CauseRecord.model_validate(row) if row else None


def for_engagement(session: Session, engagement_id: str) -> list[CauseRecord]:
    rows = session.scalars(
        select(CauseLibraryEntry)
        .where(CauseLibraryEntry.engagement_id == engagement_id)
        .order_by(CauseLibraryEntry.created_at, CauseLibraryEntry.id)
    )
    return [CauseRecord.model_validate(r) for r in rows]


def set_validation(session: Session, cause_id: str, result: str) -> CauseRecord:
    row = session.get(CauseLibraryEntry, cause_id)
    assert row is not None
    row.validation_result = result
    session.flush()
    return CauseRecord.model_validate(row)


def last_labels(session: Session, engagement_id: str) -> dict[str, str]:
    """The most recent label of each step key in the engagement's versions."""
    rows = session.execute(
        select(Element.stable_key, Element.label)
        .join(MapVersion, MapVersion.id == Element.version_id)
        .where(MapVersion.engagement_id == engagement_id)
        .order_by(Element.created_at, Element.id)
    )
    return {key: label for key, label in rows}
