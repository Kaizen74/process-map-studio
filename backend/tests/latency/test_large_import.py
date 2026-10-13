"""Criterion 94 (P10b R12; PRD §3.13.3, constraint 24): a 500,000-event log imports as a
background job with progress, the screen can follow it the whole time, and afterwards every
metric endpoint meets p95 < 200 ms. Also: no user ID from the extract is stored anywhere.

The log is generated in memory (100,000 cases with 5 activities each over four months, user
IDs U01-U20 mapped to two roles); nothing is written outside the test's own folder."""

from __future__ import annotations

import io
import time
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import AppConfig, load_config
from app.main import create_app
from tests.latency.test_latency import BUDGET_MS, p95_ms

CASES = 100_000
ACTIVITIES = ("Plan created", "Special load checked", "Weight deviation checked",
              "Loading report received", "Load sheet issued")  # fmt: skip
USERS = [f"U{n:02d}" for n in range(1, 21)]
IMPORT_BUDGET_S = 300.0  # generous: about 35 s on the build machine
POLL_BUDGET_MS = 3000.0  # the screen polls every second; any answer within 3 s keeps it live


def big_log() -> bytes:
    out = io.StringIO()
    out.write("case_id,activity,timestamp,end_timestamp,resource\n")
    base = datetime(2026, 1, 5, 6, 0)
    for case in range(CASES):
        start = base + timedelta(minutes=(case * 7) % (60 * 24 * 110))
        for step, activity in enumerate(ACTIVITIES):
            begin = start + timedelta(minutes=step * 20 + case % 13)
            end = begin + timedelta(minutes=5 + (case + step) % 11)
            user = USERS[(case + step) % len(USERS)]
            out.write(f"FL{case},{activity},{begin:%Y-%m-%d %H:%M:%S},{end:%Y-%m-%d %H:%M:%S},"
                      f"{user}\n")  # fmt: skip
    return out.getvalue().encode()


@pytest.fixture(scope="module")
def config(tmp_path_factory: pytest.TempPathFactory) -> AppConfig:
    folder = tmp_path_factory.mktemp("large_import")
    return load_config(
        {"PMS_ENV_FILE": str(folder / ".env"), "MOCK_CLAUDE": "1", "DATA_DIR": str(folder / "data")}
    )


def test_a_500k_event_log_imports_with_progress_and_fast_metrics(config: AppConfig) -> None:
    with TestClient(create_app(config)) as client:
        eid = client.post("/api/engagements", json={"name": "Load control"}).json()["id"]
        roles = [client.post(f"/api/engagements/{eid}/roles", json={"name": name}).json()["id"]
                 for name in ("Load controller", "Ramp")]  # fmt: skip
        data = big_log()
        uploaded = client.post(
            f"/api/engagements/{eid}/event-logs",
            files={"file": ("dcs_large.csv", data, "text/csv")},
            data={"name": "DCS extract", "window_start": "2026-01-01", "window_end": "2026-06-30"},
        )
        assert uploaded.status_code == 201, uploaded.text
        log = uploaded.json()
        assert log["validation_report"]["rows_read"] == CASES * len(ACTIVITIES)
        lid = log["id"]
        assert client.put(f"/api/event-logs/{lid}/column-map",
                          json={"columns": log["column_map"]}).status_code == 200  # fmt: skip
        role_map = {u: roles[n % 2] for n, u in enumerate(USERS)}
        assert client.put(f"/api/event-logs/{lid}/role-map",
                          json={"roles": role_map}).status_code == 200  # fmt: skip
        started = client.post(f"/api/event-logs/{lid}/import",
                              json={"approved_by_role": "Head of ground operations",
                                    "confirm_approval": True})  # fmt: skip
        assert started.status_code == 202, started.text

        # While it runs, the screen polls the job and lists the logs: always answered, quickly.
        job_url = f"/api/jobs/{started.json()['job_id']}"
        began, slowest, messages, shares = time.perf_counter(), 0.0, [], []
        while True:
            for url in (job_url, f"/api/engagements/{eid}/event-logs"):
                t0 = time.perf_counter()
                response = client.get(url)
                slowest = max(slowest, (time.perf_counter() - t0) * 1000)
                assert response.status_code == 200, response.text
            job = client.get(job_url).json()
            if job["status"] in ("done", "failed"):
                break
            if job["message"] and (not messages or messages[-1] != job["message"]):
                messages.append(job["message"])
                shares.append(job["progress"])
            assert time.perf_counter() - began < IMPORT_BUDGET_S, "the import took too long"
            time.sleep(0.5)
        elapsed = time.perf_counter() - began
        assert job["status"] == "done", job
        assert job["message"] == "Imported 500,000 events from 100,000 cases."
        assert slowest < POLL_BUDGET_MS, f"a poll took {slowest:.0f} ms during the import"
        assert any(m.startswith("Saving events: ") for m in messages), messages
        assert shares == sorted(shares), shares  # progress only goes forward
        print(f"\n500,000 events imported in {elapsed:.1f} s; slowest poll {slowest:.0f} ms")

        # Afterwards: every metric endpoint within the latency budget (criterion 94).
        for scope in ("activity", "transition", "case", "variant", "role"):
            url = f"/api/event-logs/{lid}/metrics?scope={scope}"
            assert client.get(url).status_code == 200
            p95 = p95_ms(lambda url=url: client.get(url))
            assert p95 < BUDGET_MS, f"{scope}: p95 {p95:.1f} ms"

        # Constraint 24: no user ID from the extract anywhere in the data folder.
        stored = b"".join(p.read_bytes() for p in config.data_dir.rglob("*") if p.is_file())
        for user in USERS:
            assert f",{user}".encode() not in stored and f'"{user}"'.encode() not in stored, user
