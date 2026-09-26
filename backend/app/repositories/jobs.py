"""Jobs repository (PRD §3.5 jobs): background work and its progress."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import JobView
from app.repositories.tables import Job

UNFINISHED = ("queued", "running")


def _view(row: Job) -> JobView:
    return JobView(
        id=row.id,
        engagement_id=row.engagement_id,
        type=row.type,
        target_id=row.target_id,
        status=row.status,
        stage=row.stage,
        progress=row.progress,
        message=row.message,
        error=row.error,
        created_at=row.created_at,
    )


def create(session: Session, *, engagement_id: str, job_type: str, target_id: str) -> JobView:
    row = Job(engagement_id=engagement_id, type=job_type, target_id=target_id, status="queued")
    session.add(row)
    session.flush()
    return _view(row)


def get(session: Session, job_id: str) -> JobView | None:
    row = session.get(Job, job_id)
    return _view(row) if row else None


def update(
    session: Session,
    job_id: str,
    *,
    status: str | None = None,
    stage: str | None = None,
    progress: float | None = None,
    message: str | None = None,
    error: str | None = None,
) -> JobView | None:
    row = session.get(Job, job_id)
    if row is None:
        return None
    for name, value in (
        ("status", status),
        ("stage", stage),
        ("progress", progress),
        ("message", message),
        ("error", error),
    ):
        if value is not None:
            setattr(row, name, value)
    session.flush()
    return _view(row)


def unfinished(session: Session) -> list[JobView]:
    """Queued or running jobs, oldest first (to run again after a restart)."""
    rows = session.scalars(
        select(Job).where(Job.status.in_(UNFINISHED)).order_by(Job.created_at, Job.id)
    )
    return [_view(row) for row in rows]


def unfinished_targets(session: Session, job_type: str) -> set[str]:
    rows = session.scalars(
        select(Job.target_id).where(Job.type == job_type).where(Job.status.in_(UNFINISHED))
    )
    return {target for target in rows if target}
