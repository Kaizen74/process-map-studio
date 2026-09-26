"""The background job worker (PRD §4: long work runs as jobs; phase P2).

One thread runs jobs one at a time, in the order they were submitted. It knows nothing about what
a job does: it is given a `run(job_id)` function (app/actions/jobs.py) that loads the job, does the
work and records the outcome in the jobs table, so a crash or restart never loses a job (Start
runs unfinished jobs again). The thread starts when there is work and stops when the queue has
been empty for a moment, so idle apps (and tests) keep no threads running.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable

log = logging.getLogger(__name__)

IDLE_SECONDS = 0.5


class JobWorker:
    def __init__(self, run: Callable[[str], None]) -> None:
        self._run = run
        self._queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self._busy = threading.Condition(self._lock)
        self._outstanding = 0
        self._thread: threading.Thread | None = None

    def submit(self, job_id: str) -> None:
        """Queue a job; it runs after the jobs submitted before it."""
        with self._lock:
            self._outstanding += 1
            self._queue.put(job_id)
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, name="job-worker", daemon=True)
                self._thread.start()

    def drain(self, timeout: float = 30.0) -> bool:
        """Wait until every submitted job has finished (tests and shutdown). False on timeout."""
        deadline = time.monotonic() + timeout
        with self._busy:
            while self._outstanding:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._busy.wait(remaining)
        return True

    def _loop(self) -> None:
        while True:
            try:
                job_id = self._queue.get(timeout=IDLE_SECONDS)
            except queue.Empty:
                with self._lock:
                    if self._queue.empty():
                        self._thread = None
                        return
                continue
            try:
                self._run(job_id)
            except Exception:  # the job records its own failure; never let the thread die
                log.exception("Job %s stopped unexpectedly", job_id)
            finally:
                with self._busy:
                    self._outstanding -= 1
                    self._busy.notify_all()
