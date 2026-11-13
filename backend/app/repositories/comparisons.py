"""Country comparisons (PRD §3.5 `country_comparisons`, `country_pairs`, `country_differences`;
DECISIONS 98): the only database access."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.comparisons import ComparisonRecord, DifferenceRecord, PairRecord
from app.repositories.tables import CountryComparison, CountryDifference, CountryPair


def get(session: Session, comparison_id: str) -> ComparisonRecord | None:
    row = session.get(CountryComparison, comparison_id)
    return ComparisonRecord.model_validate(row) if row else None


def find(session: Session, reference_id: str, other_id: str) -> ComparisonRecord | None:
    row = session.scalars(
        select(CountryComparison).where(
            CountryComparison.reference_engagement_id == reference_id,
            CountryComparison.other_engagement_id == other_id,
        )
    ).first()
    return ComparisonRecord.model_validate(row) if row else None


def for_engagement(session: Session, engagement_id: str) -> list[ComparisonRecord]:
    rows = session.scalars(
        select(CountryComparison)
        .where(
            or_(
                CountryComparison.reference_engagement_id == engagement_id,
                CountryComparison.other_engagement_id == engagement_id,
            )
        )
        .order_by(CountryComparison.created_at, CountryComparison.id)
    )
    return [ComparisonRecord.model_validate(r) for r in rows]


def as_other(session: Session, engagement_id: str, version_id: str) -> list[ComparisonRecord]:
    """The comparisons where this engagement, at this version, is the other country."""
    rows = session.scalars(
        select(CountryComparison)
        .where(
            CountryComparison.other_engagement_id == engagement_id,
            CountryComparison.other_version_id == version_id,
        )
        .order_by(CountryComparison.created_at, CountryComparison.id)
    )
    return [ComparisonRecord.model_validate(r) for r in rows]


def create(session: Session, fields: dict[str, Any]) -> ComparisonRecord:
    row = CountryComparison(**fields)
    session.add(row)
    session.flush()
    return ComparisonRecord.model_validate(row)


def update(session: Session, comparison_id: str, fields: dict[str, Any]) -> None:
    row = session.get(CountryComparison, comparison_id)
    assert row is not None
    for name, value in fields.items():
        setattr(row, name, value)
    session.flush()


def pairs(session: Session, comparison_id: str) -> list[PairRecord]:
    rows = session.scalars(
        select(CountryPair)
        .where(CountryPair.comparison_id == comparison_id)
        .order_by(CountryPair.created_at, CountryPair.id)
    )
    return [PairRecord.model_validate(r) for r in rows]


def add_pair(
    session: Session,
    comparison_id: str,
    reference_key: str | None,
    other_key: str | None,
    status: str,
    why: str = "",
) -> None:
    session.add(
        CountryPair(
            comparison_id=comparison_id,
            reference_key=reference_key,
            other_key=other_key,
            status=status,
            why=why,
        )
    )
    session.flush()


def delete_pairs(session: Session, pair_ids: list[str]) -> None:
    for pair_id in pair_ids:
        row = session.get(CountryPair, pair_id)
        if row is not None:
            session.delete(row)
    session.flush()


def differences(session: Session, comparison_id: str) -> list[DifferenceRecord]:
    rows = session.scalars(
        select(CountryDifference)
        .where(CountryDifference.comparison_id == comparison_id)
        .order_by(CountryDifference.created_at, CountryDifference.id)
    )
    return [DifferenceRecord.model_validate(r) for r in rows]


def save_difference(
    session: Session, comparison_id: str, diff_key: str, fields: dict[str, Any]
) -> DifferenceRecord:
    row = session.scalars(
        select(CountryDifference).where(
            CountryDifference.comparison_id == comparison_id, CountryDifference.diff_key == diff_key
        )
    ).first()
    if row is None:
        row = CountryDifference(comparison_id=comparison_id, diff_key=diff_key)
        session.add(row)
    for name, value in fields.items():
        setattr(row, name, value)
    session.flush()
    return DifferenceRecord.model_validate(row)
