"""Jobs (PRD §4 Pipeline): run, report and resume background work.

`run_job` is what the worker thread (app/worker.py) calls for each job ID. Every outcome is written
to the jobs table, including unexpected errors, so a job never stays "running" forever.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.actions import sources
from app.config import AppConfig
from app.db import session_scope
from app.domain.models import JobView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import jobs as repo
from app.repositories import sources as sources_repo

log = logging.getLogger(__name__)
Sessions = sessionmaker[Session]
Enqueue = Callable[[str], None]

JOB_MISSING = "That job doesn't exist."
READ_STAGE = "Reading the file"
UNEXPECTED = (
    "Something went wrong while reading this file. Nothing else was changed. "
    "Try uploading it again, or use Copy details to report it."
)


def get_job(sessions: Sessions, job_id: str) -> Result[JobView]:
    with session_scope(sessions) as session:
        job = repo.get(session, job_id)
    return Ok(job) if job else Err(ErrorKind.NOT_FOUND, JOB_MISSING)


def _finish(sessions: Sessions, job_id: str, result: Result[str]) -> None:
    with session_scope(sessions) as session:
        match result:
            case Ok(value=message):
                repo.update(session, job_id, status="done", progress=1.0, message=message)
            case Err(kind=ErrorKind.NOT_FOUND):
                repo.update(
                    session,
                    job_id,
                    status="done",
                    progress=1.0,
                    message="The source was deleted before it was read.",
                )
            case Err(message=message):
                repo.update(session, job_id, status="failed", error=message)


def run_job(config: AppConfig, sessions: Sessions, job_id: str) -> None:
    """Run one job and record how it went. Jobs already finished are left alone."""
    with session_scope(sessions) as session:
        job = repo.get(session, job_id)
        if job is None or job.status not in repo.UNFINISHED:
            return
        repo.update(session, job_id, status="running", stage=READ_STAGE, progress=0.0)
    if job.type != sources.READ_JOB:
        _finish(sessions, job_id, Err(ErrorKind.VALIDATION, f"Unknown job type: {job.type}."))
        return
    try:
        result = sources.read_source(config, sessions, job.target_id or "")
    except Exception as exc:  # recorded for Eric in plain words, and in the app log for a fix
        log.exception("Reading job %s failed", job_id)
        sources.mark_unreadable(sessions, job.target_id or "", UNEXPECTED)
        result = Err(ErrorKind.IO, UNEXPECTED, {"type": type(exc).__name__})
    _finish(sessions, job_id, result)


def resume_jobs(sessions: Sessions, enqueue: Enqueue) -> list[str]:
    """At start-up: run unfinished jobs again, and read files still waiting (e.g. from phase P1)."""
    with session_scope(sessions) as session:
        waiting = repo.unfinished(session)
        for job in waiting:
            repo.update(session, job.id, status="queued", stage="", progress=0.0)
        busy = repo.unfinished_targets(session, sources.READ_JOB)
        created = [
            repo.create(
                session,
                engagement_id=info.engagement_id,
                job_type=sources.READ_JOB,
                target_id=info.id,
            )
            for info in sources_repo.pending(session)
            if info.id not in busy
        ]
    job_ids = [job.id for job in waiting] + [job.id for job in created]
    for job_id in job_ids:
        enqueue(job_id)
    return job_ids
