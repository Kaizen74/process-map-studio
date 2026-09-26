"""The background job worker (app/worker.py): order, survival, idle exit, drain."""

from __future__ import annotations

import threading
import time

from app import worker as worker_module
from app.worker import JobWorker


def test_jobs_run_one_at_a_time_in_submission_order() -> None:
    ran: list[str] = []
    active = []

    def run(job_id: str) -> None:
        active.append(job_id)
        assert len(active) == 1
        time.sleep(0.01)
        ran.append(job_id)
        active.pop()

    worker = JobWorker(run)
    for job_id in ("a", "b", "c"):
        worker.submit(job_id)
    assert worker.drain(5)
    assert ran == ["a", "b", "c"]


def test_a_failing_job_does_not_stop_the_worker() -> None:
    ran: list[str] = []

    def run(job_id: str) -> None:
        if job_id == "bad":
            raise RuntimeError("boom")
        ran.append(job_id)

    worker = JobWorker(run)
    worker.submit("bad")
    worker.submit("good")
    assert worker.drain(5)
    assert ran == ["good"]


def test_the_thread_stops_when_idle_and_restarts_for_new_work() -> None:
    worker_module.IDLE_SECONDS = 0.05
    try:
        ran: list[str] = []
        worker = JobWorker(ran.append)
        worker.submit("one")
        assert worker.drain(5)
        deadline = time.monotonic() + 2
        while worker._thread is not None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert worker._thread is None
        worker.submit("two")
        assert worker.drain(5)
        assert ran == ["one", "two"]
    finally:
        worker_module.IDLE_SECONDS = 0.5


def test_drain_times_out_while_a_job_is_still_running() -> None:
    release = threading.Event()
    worker = JobWorker(lambda _job: release.wait(5) and None)
    worker.submit("slow")
    assert worker.drain(0.05) is False
    release.set()
    assert worker.drain(5) is True
