"""Emerging themes (PRD §3.5 `emergent_themes`; Appendix E tier 3; C7b): the only database
access for them."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.sensemaking import ThemeProposal, ThemeRecord
from app.repositories.tables import EmergentTheme

PROPOSED = "proposed"


def for_engagement(session: Session, engagement_id: str) -> list[ThemeRecord]:
    rows = session.scalars(
        select(EmergentTheme)
        .where(EmergentTheme.engagement_id == engagement_id)
        .order_by(EmergentTheme.created_at, EmergentTheme.id)
    )
    return [ThemeRecord.model_validate(r) for r in rows]


def get(session: Session, theme_id: str) -> ThemeRecord | None:
    row = session.get(EmergentTheme, theme_id)
    return ThemeRecord.model_validate(row) if row else None


def replace_proposed(
    session: Session, engagement_id: str, version_id: str, kept: list[ThemeProposal]
) -> None:
    """The version's proposed themes become `kept`; decided ones (accepted, renamed, dismissed)
    are never touched (constraint 8)."""
    for row in session.scalars(
        select(EmergentTheme).where(
            EmergentTheme.version_id == version_id, EmergentTheme.status == PROPOSED
        )
    ):
        session.delete(row)
    for theme in kept:
        session.add(EmergentTheme(engagement_id=engagement_id, version_id=version_id,
                                  theme=theme.theme, fragment_ids=theme.claim_ids,
                                  basis=theme.basis, status=PROPOSED))  # fmt: skip
    session.flush()


def update(session: Session, theme_id: str, fields: dict[str, str]) -> ThemeRecord:
    row = session.get(EmergentTheme, theme_id)
    assert row is not None
    for name, value in fields.items():
        setattr(row, name, value)
    session.flush()
    return ThemeRecord.model_validate(row)
