"""Leadership repository (PRD §4 Views): Eric's "Decision needed" lines per version."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.repositories.tables import LeadershipDecision


def decisions(session: Session, version_id: str) -> dict[str, str]:
    """Cause type → saved text."""
    rows = session.scalars(
        select(LeadershipDecision).where(LeadershipDecision.version_id == version_id)
    )
    return {r.cause_type: r.text for r in rows}


def replace(session: Session, version_id: str, lines: dict[str, str]) -> None:
    """The version's lines become exactly these (blank texts are dropped)."""
    session.execute(delete(LeadershipDecision).where(LeadershipDecision.version_id == version_id))
    for cause_type, text in lines.items():
        if text:
            session.add(LeadershipDecision(version_id=version_id, cause_type=cause_type, text=text))
    session.flush()
