"""Latency gate (PRD §6.2 item 5): p95 < 200 ms on every non-AI endpoint on the fixture data set.

The data set is the PRD Appendix A load-control fixture: the two SOPs, both job descriptions, the
illustrative manual extract (PDF) and the interview transcript, plus three roles. Each endpoint is
called REPEATS times through the real app (TestClient, real SQLite file); the 95th percentile must
stay under the budget.
"""

from __future__ import annotations

import gc
import statistics
import time
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import AppConfig
from app.db import session_scope
from app.domain.models import ClaimRecord
from app.main import create_app
from app.repositories import claims
from tests import fixture_engagement
from tests.paths import BACKEND_ROOT
from tests.uploads import wait_for_jobs

FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "engagement_load_control"
DOCUMENTS = [
    "sop_LC-07.docx",
    "sop_RP-02.docx",
    "jd_load_control_lead.docx",
    "jd_load_controller.docx",
    "manual_extract.pdf",
    "interview_transcript.txt",
]
BUDGET_MS = 200.0
REPEATS = 30

Loaded = tuple[TestClient, dict[str, str]]


def p95_ms(call: Callable[[], Any]) -> float:
    call()  # warm-up: first call pays for imports and caches
    # The objects hundreds of earlier tests left in this process are not the app's: frozen, a full
    # garbage collection doesn't scan them (it once paused a request for 363 ms). The app's own
    # objects are still collected as usual.
    gc.collect()
    gc.freeze()
    try:
        timings = []
        for _ in range(REPEATS):
            start = time.perf_counter()
            call()
            timings.append((time.perf_counter() - start) * 1000)
    finally:
        gc.unfreeze()
    return statistics.quantiles(timings, n=20)[18]


@pytest.fixture(scope="module")
def loaded(tmp_path_factory: pytest.TempPathFactory) -> Loaded:
    from app.config import load_config

    folder = tmp_path_factory.mktemp("latency")
    config: AppConfig = load_config(
        {"PMS_ENV_FILE": str(folder / ".env"), "MOCK_CLAUDE": "1", "DATA_DIR": str(folder / "data")}
    )
    client = TestClient(create_app(config))
    eid = client.post("/api/engagements", json={"name": "Load control"}).json()["id"]
    role = ""
    for name in ("Load controller", "Load control lead", "Ramp agent"):
        role = client.post(f"/api/engagements/{eid}/roles", json={"name": name}).json()["id"]
    source = job = ""
    for name in DOCUMENTS:
        response = client.post(
            f"/api/engagements/{eid}/sources",
            files={"file": (name, (FIXTURES / name).read_bytes(), "application/octet-stream")},
        )
        assert response.status_code == 201
        source, job = response.json()["id"], response.json()["job_id"]
    wait_for_jobs(client)
    # The last document is the interview transcript: map one speaker, find a passage to correct.
    client.put(f"/api/sources/{source}/speakers", json={"Priya Nair": role})
    segment = client.get(f"/api/sources/{source}/segments").json()["segments"][0]["id"]
    # A mocked draft, plus a full rejected-claims register, for the P3 endpoints.
    client.put(f"/api/sources/{source}/speakers", json={"Interviewer": "interviewer"})
    client.put("/api/settings/key", json={"anthropic_api_key": "sk-" + "ant-" + "L4tency" * 5})
    draft_job = client.post(f"/api/engagements/{eid}/draft").json()["job_id"]
    wait_for_jobs(client)
    version = client.get(f"/api/jobs/{draft_job}").json()["target_id"]
    assert version, "the mocked draft did not finish"
    rejected = [
        ClaimRecord(
            source_id=source,
            stage="S1",
            claim_type="activity",
            payload={"text": f"Planted claim {n}", "scrubbed": n % 2},
            segment_ids=[segment],
            quote="not in the source",
            provenance="O",
            basis="",
            verification_status="rejected",
            rejection_reason="quote not found in source",
            rejection_guardrail="G4",
        )
        for n in range(60)
    ]
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        claims.add_claims(session, version, rejected)
    ids = {"eid": eid, "role": role, "source": source, "job": job, "segment": segment}
    # The sample engagement fully drafted (its mock answers match): a real map for graph and lint.
    built = fixture_engagement.build(client)
    sample_job = client.post(f"/api/engagements/{built.engagement_id}/draft").json()["job_id"]
    wait_for_jobs(client)
    sample = client.get(f"/api/jobs/{sample_job}").json()
    assert sample["status"] == "done", sample
    return client, ids | {"draft_job": draft_job, "version": version, "map": sample["target_id"]}


ENDPOINTS: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/api/health", None),
    ("GET", "/api/settings", None),
    ("GET", "/api/engagements", None),
    ("GET", "/api/engagements/{eid}", None),
    ("PATCH", "/api/engagements/{eid}", {"trigger": "Flight scheduled"}),
    ("GET", "/api/engagements/{eid}/readiness", None),
    ("GET", "/api/engagements/{eid}/roles", None),
    ("PATCH", "/api/roles/{role}", {"aliases": ["RA"]}),
    ("GET", "/api/engagements/{eid}/sources", None),
    ("GET", "/api/sources/{source}", None),
    ("PATCH", "/api/sources/{source}", {"owner": "Load Control"}),
    ("GET", "/api/sources/{source}/segments", None),
    ("GET", "/api/jobs/{job}", None),
    ("GET", "/api/sources/{source}/segments?raw=1", None),
    ("GET", "/api/sources/{source}/speakers", None),
    ("PUT", "/api/sources/{source}/speakers", {"Interviewer": "interviewer"}),
    ("PATCH", "/api/segments/{segment}", {"text": "Walk me through the last flight you planned."}),
    ("GET", "/api/engagements/{eid}/redaction-terms", None),
    ("GET", "/api/engagements/{eid}/draft", None),
    ("GET", "/api/jobs/{draft_job}", None),
    ("GET", "/api/versions/{version}/rejected-claims", None),
    ("GET", "/api/settings/usage", None),
    ("GET", "/api/versions/{map}/graph", None),
    ("GET", "/api/versions/{map}/layout", None),
    ("GET", "/api/versions/{map}/lint", None),
]


@pytest.mark.parametrize(
    ("method", "path", "body"), ENDPOINTS, ids=[f"{m} {p}" for m, p, _ in ENDPOINTS]
)
def test_endpoint_p95_under_budget(
    loaded: Loaded, method: str, path: str, body: dict[str, Any] | None
) -> None:
    client, ids = loaded
    url = path.format(**ids)

    def call() -> None:
        response = client.request(method, url, json=body)
        assert response.status_code == 200, response.text

    p95 = p95_ms(call)
    print(f"\n{method} {path}: p95 {p95:.1f} ms")  # shown with pytest -s
    assert p95 < BUDGET_MS, f"{method} {path}: p95 {p95:.1f} ms (budget {BUDGET_MS:.0f} ms)"


@pytest.mark.parametrize("name", ["sop_LC-07.docx", "manual_extract.pdf"])
def test_upload_p95_under_budget(loaded: Loaded, name: str) -> None:
    """Uploading stores the file and queues its reading job (the reading itself runs after)."""
    client, ids = loaded
    data = (FIXTURES / name).read_bytes()
    created: list[str] = []

    def call() -> None:
        response = client.post(
            f"/api/engagements/{ids['eid']}/sources",
            files={"file": (name, data, "application/octet-stream")},
        )
        assert response.status_code == 201
        created.append(response.json()["id"])

    p95 = p95_ms(call)
    print(f"\nupload {name}: p95 {p95:.1f} ms")  # shown with pytest -s
    wait_for_jobs(client)
    for source_id in created:
        client.delete(f"/api/sources/{source_id}")
    assert p95 < BUDGET_MS, f"upload {name}: p95 {p95:.1f} ms (budget {BUDGET_MS:.0f} ms)"


def test_adding_and_removing_names_p95_under_budget(loaded: Loaded) -> None:
    client, ids = loaded
    added: list[str] = []

    def add() -> None:
        response = client.post(
            f"/api/engagements/{ids['eid']}/redaction-terms", json={"term": f"Name {len(added)}"}
        )
        assert response.status_code == 201
        added.append(response.json()["id"])

    def remove() -> None:
        response = client.delete(f"/api/redaction-terms/{added.pop()}")
        assert response.status_code == 204

    p95_add = p95_ms(add)
    p95_remove = p95_ms(remove)
    print(f"\nPOST redaction-terms: p95 {p95_add:.1f} ms; DELETE: p95 {p95_remove:.1f} ms")
    assert p95_add < BUDGET_MS and p95_remove < BUDGET_MS
