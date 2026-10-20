"""GET /api/engagements/{id}/readiness against a real database (API_CONTRACT.md → Readiness)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.actions.readiness import ADD_KEY, ADD_SOURCE, ADD_TRANSCRIPT
from app.config import AppConfig
from app.db import session_scope
from app.main import create_app
from app.repositories.tables import Element, GapAnalysis, MapVersion, SourceSegment
from tests.paths import BACKEND_ROOT
from tests.uploads import wait_for_jobs

FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "engagement_load_control"
KEY = "sk-" + "ant-" + "api03-" + "R3ady" * 9 + "Qw7e"


@pytest.fixture()
def client(settings_config: AppConfig) -> TestClient:
    return TestClient(create_app(settings_config), raise_server_exceptions=False)


@pytest.fixture()
def engagement(client: TestClient) -> str:
    body = {"name": "Load control", "trigger": "Flight scheduled", "end_point": "Load sheet issued"}
    return str(client.post("/api/engagements", json=body).json()["id"])


def readiness(client: TestClient, engagement: str) -> dict[str, Any]:
    response = client.get(f"/api/engagements/{engagement}/readiness")
    assert response.status_code == 200, response.text
    return dict(response.json())


def upload(client: TestClient, engagement: str, name: str, data: bytes | None = None) -> str:
    content = data if data is not None else (FIXTURES / name).read_bytes()
    response = client.post(
        f"/api/engagements/{engagement}/sources",
        files={"file": (name, content, "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    wait_for_jobs(client)
    return str(response.json()["id"])


def add_rows(client: TestClient, *rows: Any) -> None:
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        for row in rows:
            session.add(row)
            session.flush()


def test_unknown_engagement_is_404(client: TestClient) -> None:
    response = client.get("/api/engagements/nope/readiness")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_new_engagement_without_key(client: TestClient) -> None:
    created = client.post("/api/engagements", json={"name": "Blank"}).json()
    body = readiness(client, created["id"])
    assert body["key_set"] is False
    assert body["next_step"] == "setup"
    # Either kind of source can start a draft (2026-10-20): with neither, one is asked for.
    assert body["missing"] == [ADD_KEY, ADD_SOURCE]
    assert body["recommended"] == [] and body["signal"] is None
    assert body["nav"]["setup"] == "not_started" and body["nav_counts"] == {}
    assert body["ready_to_draft"] is False and body["blockers_count"] == 0


def test_key_and_uploaded_word_sop(client: TestClient, engagement: str, env_file: Path) -> None:
    env_file.write_text(f"ANTHROPIC_API_KEY={KEY}\n")
    upload(client, engagement, "sop_LC-07.docx")
    body = readiness(client, engagement)
    assert KEY not in str(body)
    assert body["key_set"] is True and body["documents_ready"] is True
    assert body["nav"]["setup"] == "done"
    # Documents alone can be drafted (Eric, 2026-10-20); the interview is recommended, so it
    # stays on the path but is no longer the next step.
    assert body["nav"]["sources"] == "done" and body["nav_counts"] == {}
    assert body["missing"] == [] and body["ready_to_draft"] is True
    assert body["recommended"] == [ADD_TRANSCRIPT]
    assert body["signal"]["level"] == "limited" and "documents only" in body["signal"]["detail"]
    assert body["nav"]["interview"] == "not_started" and body["next_step"] == "draft"


def test_a_read_transcript_is_ready_and_its_speakers_need_mapping(
    client: TestClient, engagement: str
) -> None:
    upload(client, engagement, "interview_transcript.txt")
    body = readiness(client, engagement)
    assert body["transcripts_ready"] is True and body["speakers_unmapped"] == 2
    assert "Map 2 speakers in interview_transcript.txt" in body["missing"]


def test_unmapped_speakers_are_counted(client: TestClient, engagement: str) -> None:
    source_id = upload(client, engagement, "sop_LC-07.docx")
    add_rows(
        client,
        *[
            SourceSegment(source_id=source_id, seq=100 + i, speaker_label=label, text="…")
            for i, label in enumerate(["Priya Nair", "Priya Nair", "Interviewer"])
        ],
    )
    body = readiness(client, engagement)
    assert body["speakers_unmapped"] == 2
    assert "Map 2 speakers in sop_LC-07.docx" in body["missing"]


def test_draft_review_publish_and_gap_analysis(client: TestClient, engagement: str) -> None:
    draft = MapVersion(engagement_id=engagement, label="v0.1", state="draft")
    add_rows(client, draft)
    add_rows(
        client,
        *[
            Element(
                version_id=draft.id,
                stable_key=f"k{i}",
                kind="activity",
                label=f"Step {i}",
                provenance="O",
                review_status="confirmed" if i < 2 else "draft",
            )
            for i in range(5)
        ],
    )
    body = readiness(client, engagement)
    assert body["draft_exists"] is True and body["nav"]["draft"] == "done"
    # 3 steps left to review, plus the quality card's other blockers (P7): these bare steps have
    # no verified passage (Q2) and no roles or connections (Q4). Q6 "Fully reviewed" is the
    # 3 steps themselves, so it isn't counted twice.
    assert body["blockers_count"] == 3
    assert body["nav"]["review"] == "attention" and body["nav_counts"]["review"] == 3 + 2
    assert (
        body["nav"]["published"] == "not_started" and body["nav"]["gap_analysis"] == "not_started"
    )

    published = MapVersion(engagement_id=engagement, label="v1.0", state="published")
    add_rows(client, published)
    add_rows(client, GapAnalysis(version_id=published.id, mode="internal", status="finalised"))
    body = readiness(client, engagement)
    assert body["nav"]["published"] == "done" and body["nav"]["leadership"] == "done"
    assert body["nav"]["gap_analysis"] == "done"


def test_home_summary_still_reports_latest_version(client: TestClient, engagement: str) -> None:
    add_rows(client, MapVersion(engagement_id=engagement, label="v0.1", state="draft"))
    summary = client.get("/api/engagements").json()[0]
    assert summary["latest_version"] == {"label": "v0.1", "state": "draft"}
    assert summary["review_progress"] == {"reviewed": 0, "total": 0}
