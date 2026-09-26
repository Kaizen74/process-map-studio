"""Jobs repository (PRD §3.5 jobs): background work and its progress."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import JobStage, JobView
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
        stages=[JobStage.model_validate(stage) for stage in row.stages or []],
        created_at=row.created_at,
    )


def create(
    session: Session,
    *,
    engagement_id: str,
    job_type: str,
    target_id: str | None,
    stages: list[JobStage] | None = None,
) -> JobView:
    row = Job(
        engagement_id=engagement_id,
        type=job_type,
        target_id=target_id,
        status="queued",
        stages=[stage.model_dump() for stage in stages or []],
    )
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
    target_id: str | None = None,
    stages: list[JobStage] | None = None,
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
        ("target_id", target_id),
    ):
        if value is not None:
            setattr(row, name, value)
    if stages is not None:
        row.stages = [s.model_dump() for s in stages]
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


def latest(session: Session, engagement_id: str, job_type: str) -> JobView | None:
    """The most recently started job of a type for an engagement."""
    row = session.scalars(
        select(Job)
        .where(Job.engagement_id == engagement_id, Job.type == job_type)
        .order_by(Job.created_at.desc(), Job.id.desc())
    ).first()
    return _view(row) if row else None
