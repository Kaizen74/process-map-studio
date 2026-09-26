"""Jobs actions (PRD §4): running, failures, deleted sources, resuming after a restart."""

from __future__ import annotations

import io
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.actions import jobs, sources
from app.config import AppConfig
from app.db import session_scope
from app.domain.models import EngagementCreate
from app.domain.result import Err, ErrorKind, Ok
from app.repositories import jobs as jobs_repo
from app.services import parsing
from tests.uploads import FIXTURES

Sessions = sessionmaker[Session]


@pytest.fixture()
def engagement(settings_config: AppConfig, sessions: Sessions) -> str:
    from app.actions import engagements

    created = engagements.create_engagement(settings_config, sessions, EngagementCreate(name="E"))
    assert isinstance(created, Ok)
    return created.value.id


def add(config: AppConfig, sessions: Sessions, engagement: str, name: str) -> tuple[str, str]:
    """Upload without running the job; returns (source id, job id)."""
    queued: list[str] = []
    result = sources.upload_source(
        config,
        sessions,
        engagement,
        filename=name,
        stream=io.BytesIO((FIXTURES / name).read_bytes()),
        content_type="",
        enqueue=queued.append,
    )
    assert isinstance(result, Ok) and result.value.job_id == queued[0]
    return result.value.id, queued[0]


def job_status(sessions: Sessions, job_id: str) -> tuple[str, str, str]:
    result = jobs.get_job(sessions, job_id)
    assert isinstance(result, Ok)
    return result.value.status, result.value.message, result.value.error


def test_running_a_job_reads_the_source_and_records_the_outcome(
    settings_config: AppConfig, sessions: Sessions, engagement: str
) -> None:
    source_id, job_id = add(settings_config, sessions, engagement, "sop_LC-07.docx")
    assert job_status(sessions, job_id)[0] == "queued"
    jobs.run_job(settings_config, sessions, job_id)
    assert job_status(sessions, job_id) == ("done", "Read 10 passages.", "")
    view = sources.get_source(sessions, source_id)
    assert isinstance(view, Ok) and view.value.text_status == "ready"
    jobs.run_job(settings_config, sessions, job_id)  # a finished job is not run again
    assert job_status(sessions, job_id)[0] == "done"


def test_an_unexpected_error_fails_the_job_and_the_source_in_plain_words(
    settings_config: AppConfig, sessions: Sessions, engagement: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_id, job_id = add(settings_config, sessions, engagement, "sop_LC-07.docx")

    def boom(_path: Path) -> None:
        raise MemoryError("too big")

    monkeypatch.setattr(parsing, "parse_docx", boom)
    jobs.run_job(settings_config, sessions, job_id)
    status, _, error = job_status(sessions, job_id)
    assert status == "failed" and error == jobs.UNEXPECTED
    view = sources.get_source(sessions, source_id)
    assert isinstance(view, Ok) and (view.value.text_status, view.value.error) == (
        "failed",
        jobs.UNEXPECTED,
    )


def test_a_source_deleted_before_reading_ends_the_job_quietly(
    settings_config: AppConfig, sessions: Sessions, engagement: str
) -> None:
    source_id, job_id = add(settings_config, sessions, engagement, "sop_LC-07.docx")
    assert isinstance(sources.delete_source(settings_config, sessions, source_id), Ok)
    jobs.run_job(settings_config, sessions, job_id)
    assert job_status(sessions, job_id) == (
        "done",
        "The source was deleted before it was read.",
        "",
    )


def test_unknown_job_types_fail_and_missing_jobs_are_ignored(
    settings_config: AppConfig, sessions: Sessions, engagement: str
) -> None:
    with session_scope(sessions) as session:
        job = jobs_repo.create(session, engagement_id=engagement, job_type="mystery", target_id="x")
    jobs.run_job(settings_config, sessions, job.id)
    assert job_status(sessions, job.id)[0] == "failed"
    jobs.run_job(settings_config, sessions, "nope")  # nothing to do, no error
    missing = jobs.get_job(sessions, "nope")
    assert isinstance(missing, Err) and missing.kind == ErrorKind.NOT_FOUND


def test_resume_runs_unfinished_jobs_and_reads_files_left_waiting(
    settings_config: AppConfig, sessions: Sessions, engagement: str
) -> None:
    _, queued_job = add(settings_config, sessions, engagement, "sop_LC-07.docx")
    running_source, running_job = add(settings_config, sessions, engagement, "sop_RP-02.docx")
    with session_scope(sessions) as session:
        jobs_repo.update(session, running_job, status="running", stage="Reading the file")
    # A phase-P1 transcript: stored, waiting, and no job at all.
    p1_source, p1_job = add(settings_config, sessions, engagement, "interview_transcript.txt")
    with sqlite3.connect(settings_config.data_dir / "app.db") as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (p1_job,))
        conn.execute(
            "UPDATE sources SET error = 'Waiting: transcript files are read from build phase P2.' "
            "WHERE id = ?",
            (p1_source,),
        )

    queued: list[str] = []
    resumed = jobs.resume_jobs(sessions, queued.append)
    assert resumed == queued and resumed[:2] == [queued_job, running_job] and len(resumed) == 3
    for job_id in queued:
        jobs.run_job(settings_config, sessions, job_id)
    for source_id in (running_source, p1_source):
        view = sources.get_source(sessions, source_id)
        assert isinstance(view, Ok) and (view.value.text_status, view.value.error) == ("ready", "")
    assert jobs.resume_jobs(sessions, queued.append) == []  # nothing left to do
