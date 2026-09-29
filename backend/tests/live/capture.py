"""Drive the fixture engagement through the real API and capture what the evaluation scores
(PRD §6.3 P12). Used by the live test with the real key and, offline, with Claude mocked."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests import fixture_engagement
from tests.live.evaluation import RunCapture

# A live draft makes dozens of calls at high effort; the mocked one finishes in seconds.
JOB_TIMEOUT_S = 3600
# Why answers failed the format check: the field and the rule broken (JSON position or Pydantic
# message), never the answer's text. Filled by the live test's wrapper around the validation.
FORMAT_PROBLEMS: list[str] = []


def drain(client: TestClient) -> None:
    assert client.app.state.worker.drain(JOB_TIMEOUT_S), "background jobs did not finish"  # type: ignore[attr-defined]


def job(client: TestClient, job_id: str) -> dict[str, Any]:
    drain(client)
    body = client.get(f"/api/jobs/{job_id}").json()
    assert body["status"] == "done", f"{body['type']} job ended {body['status']}: {body['error']}"
    return dict(body)


def draft(client: TestClient) -> tuple[str, str]:
    """Set up the Appendix A engagement, draft it, then add the A.7 Setup: (engagement, version)."""
    built = fixture_engagement.build(client)
    eid = built.engagement_id
    started = client.post(f"/api/engagements/{eid}/draft")
    assert started.status_code == 202, started.text
    vid = str(job(client, started.json()["job_id"])["target_id"])
    # The A.7 Setup for the gap analyses, set after drafting as in the mocked tests.
    setup = client.patch(f"/api/engagements/{eid}", json=fixture_engagement.GAP_SETUP)
    assert setup.status_code == 200, setup.text
    return eid, vid


def segments(client: TestClient, engagement_id: str) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for source in client.get(f"/api/engagements/{engagement_id}/sources").json():
        page = client.get(f"/api/sources/{source['id']}/segments", params={"page_size": 500})
        found |= {s["id"]: s for s in page.json()["segments"]}
    return found


def internal(client: TestClient, version_id: str) -> tuple[dict[str, Any] | None, str]:
    """Analysis A: (report, "") or (None, the job's plain error)."""
    started = client.post(f"/api/versions/{version_id}/gap-analyses/internal")
    assert started.status_code == 202, started.text
    drain(client)
    ran = client.get(f"/api/jobs/{started.json()['job_id']}").json()
    if ran["status"] != "done":
        return None, str(ran["error"])
    return dict(client.get(f"/api/gap-analyses/{started.json()['analysis_id']}").json()), ""


def usage(client: TestClient) -> list[dict[str, Any]]:
    """Every AI call made so far (stage, status and tokens only; never any text)."""
    return list(client.get("/api/settings/usage", params={"limit": 500}).json()["items"])


def external(client: TestClient, version_id: str) -> tuple[dict[str, Any] | None, str]:
    """Analysis B with the brief as drafted, confirmed; (report, "") or (None, why not)."""
    created = client.post(f"/api/versions/{version_id}/gap-analyses/external").json()
    gid = created["analysis"]["id"]
    body = {"brief": created["brief"]["brief"], "confirmed": True}
    assert client.patch(f"/api/gap-analyses/{gid}/brief", json=body).status_code == 200
    on = client.put("/api/settings/research", json={"web_research_enabled": True})
    assert on.status_code == 200, on.text
    started = client.post(f"/api/gap-analyses/{gid}/run")
    if started.status_code != 202:
        return None, started.json()["error"]["message"]
    drain(client)
    ran = client.get(f"/api/jobs/{started.json()['job_id']}").json()
    if ran["status"] != "done":
        return None, ran["error"]
    return dict(client.get(f"/api/gap-analyses/{gid}").json()), ""


def capture(client: TestClient, analyses: bool = True) -> RunCapture:
    """One run: a draft of the fixture and, with `analyses`, Analysis A and B on it."""
    eid, vid = draft(client)
    run = RunCapture(
        graph=client.get(f"/api/versions/{vid}/graph").json(),
        segments=segments(client, eid),
        rejected=client.get(f"/api/versions/{vid}/rejected-claims").json(),
        questions=client.get(f"/api/versions/{vid}/questions").json(),
    )
    if analyses:
        run.internal, run.internal_error = internal(client, vid)
        run.external, run.external_note = external(client, vid)
    return run


def capture_runs(client: TestClient, runs: int) -> list[RunCapture]:
    """The runs, each with the AI calls it made (newest first in the usage list)."""
    captured: list[RunCapture] = []
    for n in range(runs):
        seen = {c["id"] for c in usage(client)}
        problems = len(FORMAT_PROBLEMS)
        run = capture(client, analyses=(n == 0))
        run.calls = [c for c in usage(client) if c["id"] not in seen]
        run.format_problems = FORMAT_PROBLEMS[problems:]
        captured.append(run)
    return captured
