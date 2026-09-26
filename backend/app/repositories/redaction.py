"""Redaction terms repository (PRD §3.5 redaction_terms): names to hide, and confidential terms."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import RedactionTermView
from app.repositories.tables import RedactionTerm

# Origins of terms that hide names; `confidential_term` only restricts web research.
NAME_ORIGINS = ("speaker_map", "manual")


def _view(row: RedactionTerm) -> RedactionTermView:
    return RedactionTermView(
        id=row.id,
        engagement_id=row.engagement_id,
        term=row.term,
        replacement=row.replacement,
        origin=row.origin,
    )


def list_terms(
    session: Session, engagement_id: str, origins: Iterable[str]
) -> list[RedactionTermView]:
    rows = session.scalars(
        select(RedactionTerm)
        .where(RedactionTerm.engagement_id == engagement_id)
        .where(RedactionTerm.origin.in_(list(origins)))
        .order_by(RedactionTerm.created_at, RedactionTerm.id)
    )
    return [_view(row) for row in rows]


def find(
    session: Session, engagement_id: str, term: str, origins: Iterable[str]
) -> RedactionTermView | None:
    """The term with this text (ignoring case), among the given origins."""
    row = session.scalars(
        select(RedactionTerm)
        .where(RedactionTerm.engagement_id == engagement_id)
        .where(RedactionTerm.origin.in_(list(origins)))
        .where(func.lower(RedactionTerm.term) == term.lower())
    ).first()
    return _view(row) if row else None


def get(session: Session, term_id: str) -> RedactionTermView | None:
    row = session.get(RedactionTerm, term_id)
    return _view(row) if row else None


def add(
    session: Session, *, engagement_id: str, term: str, replacement: str, origin: str
) -> RedactionTermView:
    row = RedactionTerm(
        engagement_id=engagement_id, term=term, replacement=replacement, origin=origin
    )
    session.add(row)
    session.flush()
    return _view(row)


def set_replacement(session: Session, term_id: str, replacement: str) -> None:
    row = session.get(RedactionTerm, term_id)
    if row is not None:
        row.replacement = replacement
        session.flush()


def delete(session: Session, term_id: str) -> bool:
    row = session.get(RedactionTerm, term_id)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def replace_replacement(
    session: Session, engagement_id: str, old: str, new: str, origins: Iterable[str]
) -> None:
    """After a role is renamed: terms shown as the old role name now show the new one."""
    rows = session.scalars(
        select(RedactionTerm)
        .where(RedactionTerm.engagement_id == engagement_id)
        .where(RedactionTerm.origin.in_(list(origins)))
        .where(RedactionTerm.replacement == old)
    )
    for row in rows:
        row.replacement = new
    session.flush()
