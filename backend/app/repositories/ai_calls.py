"""AI calls repository (PRD §3.5 ai_calls): usage only, never prompt or document text."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import AiCallRecord, AiUsageRow
from app.repositories.tables import AiCall, Job


def add(session: Session, job_id: str | None, calls: list[AiCallRecord]) -> None:
    for call in calls:
        session.add(AiCall(job_id=job_id, **call.model_dump()))
    session.flush()


def usage_for_job(session: Session, job_id: str) -> dict[str, int]:
    row = session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(AiCall.input_tokens), 0),
            func.coalesce(func.sum(AiCall.output_tokens), 0),
        ).where(AiCall.job_id == job_id)
    ).one()
    return {"calls": row[0], "input_tokens": row[1], "output_tokens": row[2]}


def recent(session: Session, limit: int) -> list[AiUsageRow]:
    rows = session.scalars(
        select(AiCall).order_by(AiCall.created_at.desc(), AiCall.id.desc()).limit(limit)
    )
    return [
        AiUsageRow(
            id=r.id,
            created_at=r.created_at,
            job_id=r.job_id,
            stage_id=r.stage_id,
            prompt_version=r.prompt_version,
            model=r.model,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            duration_ms=r.duration_ms,
            status=r.status,
        )
        for r in rows
    ]


def totals(session: Session) -> dict[str, int]:
    row = session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(AiCall.input_tokens), 0),
            func.coalesce(func.sum(AiCall.output_tokens), 0),
        )
    ).one()
    return {"calls": row[0], "input_tokens": row[1], "output_tokens": row[2]}


def real_usage_by_job(
    session: Session, job_types: tuple[str, ...], limit: int
) -> list[tuple[str | None, int, int]]:
    """(target ID, input tokens, output tokens) of the latest finished jobs of these types that
    made real calls, newest first. Mock calls (status "mock") never count."""
    rows = session.execute(
        select(Job.target_id, func.sum(AiCall.input_tokens), func.sum(AiCall.output_tokens))
        .join(AiCall, AiCall.job_id == Job.id)
        .where(Job.type.in_(job_types), Job.status == "done", AiCall.status == "ok")
        .group_by(Job.id)
        .order_by(Job.created_at.desc(), Job.id.desc())
        .limit(limit)
    ).all()
    return [(r[0], int(r[1] or 0), int(r[2] or 0)) for r in rows]
