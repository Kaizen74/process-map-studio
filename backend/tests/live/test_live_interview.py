"""The interview-only live check (P12, Eric's request 2026-09-29): his sample interview
(tests/sample_interview.py) drafted on its own by the real Claude model, to see how it sequences
and organises the activities when there is no document to lean on.

Runs only when Eric asks (`pytest -m live tests/live/test_live_interview.py`); the default suite
leaves it out. It uses his key the same way as the fixture evaluation (read only, never written,
printed or logged) and sends only the sample interview, with the people named in it hidden.
Costs: one draft, billed to his Anthropic account.

The report (labels and counts only) is written to PMS_LIVE_INTERVIEW_REPORT, or to the test's
temporary folder, and printed; the test fails if a check is missed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests import sample_interview
from tests.live import capture, evaluation, interview
from tests.live.test_live_run import eric_settings, live_client  # noqa: F401 (the fixture)

pytestmark = pytest.mark.live


def save(report: str, tmp_path: Path) -> None:
    default = tmp_path / "live-interview-check.md"
    path = Path(os.environ.get("PMS_LIVE_INTERVIEW_REPORT", default))
    path.write_text(report, encoding="utf-8")
    print(f"\n{report}\nReport saved to {path}")


def draft(client: TestClient) -> interview.InterviewRun:
    sample = sample_interview.build(client)
    eid = sample.engagement_id
    started = client.post(f"/api/engagements/{eid}/draft")
    assert started.status_code == 202, started.text
    vid = str(capture.job(client, started.json()["job_id"])["target_id"])
    versions = client.get(f"/api/engagements/{eid}/versions").json()
    return interview.InterviewRun(
        graph=client.get(f"/api/versions/{vid}/graph").json(),
        segments=capture.segments(client, eid),
        signal=next(v["signal"] for v in versions if v["id"] == vid),
        questions=client.get(f"/api/versions/{vid}/questions").json(),
        rejected=client.get(f"/api/versions/{vid}/rejected-claims").json(),
    )


def test_live_interview_only_draft(live_client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    model = eric_settings()["ANTHROPIC_MODEL"]
    problems = len(capture.FORMAT_PROBLEMS)
    try:
        run = draft(live_client)
    except AssertionError as failed:
        save(evaluation.render_failure(str(failed), capture.usage(live_client), model), tmp_path)
        raise
    run.calls = capture.usage(live_client)
    run.format_problems = capture.FORMAT_PROBLEMS[problems:]
    checks = interview.evaluate(run, sample_interview.NAMES)
    save(interview.render(run, checks, model), tmp_path)
    missed = [f"{c.code} {c.name}: {c.detail}" for c in checks if c.passed is False]
    assert not missed, "Checks missed:\n" + "\n".join(missed)
