"""Audit log repository (PRD §3.5 audit_log)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import literal_column, select
from sqlalchemy.orm import Session

from app.repositories.tables import AuditRow


def record(
    session: Session,
    *,
    actor: str,
    action: str,
    target_type: str,
    target_id: str = "",
    engagement_id: str | None = None,
    version_id: str | None = None,
    before: Any = None,
    after: Any = None,
) -> None:
    session.add(
        AuditRow(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            engagement_id=engagement_id,
            version_id=version_id,
            before=before,
            after=after,
        )
    )


def list_recent(
    session: Session, *, engagement_id: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    """Newest first. Without engagement_id: every row (app-level and engagement-level)."""
    # rowid (SQLite insertion order) breaks exact timestamp ties.
    query = (
        select(AuditRow)
        .order_by(AuditRow.created_at.desc(), literal_column("audit_log.rowid").desc())
        .limit(limit)
    )
    if engagement_id is not None:
        query = query.where(AuditRow.engagement_id == engagement_id)
    return [
        {
            "created_at": row.created_at,
            "actor": row.actor,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "engagement_id": row.engagement_id,
            "before": row.before,
            "after": row.after,
        }
        for row in session.scalars(query)
    ]
