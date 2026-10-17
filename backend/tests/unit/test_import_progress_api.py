"""The import job's progress and safety on large logs (P10b R12; criterion 94; API_CONTRACT.md →
POST /event-logs/{lid}/import): events saved in batches with progress after each, nothing left
behind when it fails part-way, and Start doesn't read the file again."""

from __future__ import annotations

from typing import Any

import pytest

from app.actions import event_logs as actions
from app.db import session_scope
from app.repositories import event_logs as repo
from tests.unit.test_event_logs_api import Engagement
from tests.unit.test_event_logs_api import engagement as engagement  # the shared fixture
from tests.uploads import wait_for_jobs


def test_the_import_saves_in_batches_and_reports_progress(
    engagement: Engagement, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[str, float, str]] = []
    real = actions._progress

    def watch(sessions: Any, job_id: str, stage: str, progress: float, message: str) -> None:
        real(sessions, job_id, stage, progress, message)
        with session_scope(sessions) as session:  # saved where the screen reads it
            job = actions.jobs_repo.get(session, job_id)
            assert job is not None and (job.stage, job.message) == (stage, message)
        seen.append((stage, progress, message))

    monkeypatch.setattr(actions, "BATCH", 400)
    monkeypatch.setattr(actions, "_progress", watch)
    lid = engagement.ready()
    started = engagement.start(lid)
    wait_for_jobs(engagement.client)
    assert [m for _, _, m in seen] == [
        "Reading the extract and turning user IDs into roles.",
        "Working out the figures from 1,063 events.",
        "Saving events: 400 of 1,063.",
        "Saving events: 800 of 1,063.",
        "Saving events: 1,063 of 1,063.",
    ]
    shares = [p for _, p, _ in seen]
    assert shares == sorted(shares) and shares[0] > 0 and shares[-1] < 1
    job = engagement.client.get(f"/api/jobs/{started.json()['job_id']}").json()
    assert (job["status"], job["progress"]) == ("done", 1.0)
    assert job["message"] == "Imported 1,063 events from 200 cases."
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        assert repo.event_count(session, lid) == 1063


def test_a_failure_part_way_leaves_no_events_or_figures(
    engagement: Engagement, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = repo.add_events
    calls = {"n": 0}

    def second_batch_fails(session: Any, log_id: str, events: list[dict[str, Any]]) -> int:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("disk full")
        return real(session, log_id, events)

    monkeypatch.setattr(actions, "BATCH", 400)
    monkeypatch.setattr(repo, "add_events", second_batch_fails)
    lid = engagement.ready()
    started = engagement.start(lid)
    wait_for_jobs(engagement.client)
    job = engagement.client.get(f"/api/jobs/{started.json()['job_id']}").json()
    assert (job["status"], job["error"]) == ("failed", actions.UNEXPECTED)
    assert engagement.client.get(f"/api/event-logs/{lid}").json()["status"] == "failed"
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        assert repo.event_count(session, lid) == 0  # the first batch was removed again
        assert repo.metrics(session, lid, "activity") == []
    assert actions._held(lid) is None


def test_start_uses_the_report_already_worked_out(
    engagement: Engagement, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads: list[str] = []
    real = actions._parse

    def counted(*args: Any) -> Any:
        reads.append("read")
        return real(*args)

    monkeypatch.setattr(actions, "_parse", counted)
    lid = engagement.ready()
    # The upload reads the file; confirming the suggested columns unchanged reads nothing; the
    # user IDs mapped to roles change the report, so it is read once more.
    before = len(reads)
    assert before == 2
    # Asking again with nothing changed reads nothing; a change reads once more.
    assert engagement.client.get(f"/api/event-logs/{lid}").status_code == 200
    started = engagement.start(lid)
    assert started.status_code == 202
    wait_for_jobs(engagement.client)
    assert len(reads) == before + 1  # only the import job itself reads the file again
