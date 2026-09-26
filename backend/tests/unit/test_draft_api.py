"""Draft endpoints on a real database, Claude mocked (API_CONTRACT.md → Draft, Jobs, Settings)."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.actions import draft, jobs
from app.actions.readiness import ADD_KEY
from app.config import AppConfig
from app.db import session_scope
from app.domain.result import Err, ErrorKind, Ok
from app.main import create_app
from app.pipeline import context, s1_extract
from app.repositories import jobs as jobs_repo
from app.repositories import versions
from app.repositories.tables import Element
from tests import fixture_engagement
from tests.fixtures import make_ai_fixtures
from tests.uploads import wait_for_jobs

KEY = "sk-" + "ant-" + "api03-" + "Dr4ft" * 9 + "Zx8c"
TRAPS = make_ai_fixtures.TRAPS


def make_client(config: AppConfig) -> Iterator[TestClient]:
    with TestClient(create_app(config), raise_server_exceptions=False) as client:
        yield client


@pytest.fixture()
def client(settings_config: AppConfig) -> Iterator[TestClient]:
    yield from make_client(settings_config)


def with_key(client: TestClient) -> TestClient:
    assert client.put("/api/settings/key", json={"anthropic_api_key": KEY}).status_code == 200
    return client


def run_draft(client: TestClient, engagement_id: str) -> dict[str, Any]:
    response = client.post(f"/api/engagements/{engagement_id}/draft")
    assert response.status_code == 202, response.text
    wait_for_jobs(client)
    job = client.get(f"/api/jobs/{response.json()['job_id']}")
    assert job.status_code == 200
    return dict(job.json())


def draft_state(client: TestClient, engagement_id: str) -> dict[str, Any]:
    response = client.get(f"/api/engagements/{engagement_id}/draft")
    assert response.status_code == 200, response.text
    return dict(response.json())


def broken_mocks(folder: Path) -> Path:
    """Mock answers in the wrong format, twice (first answer and repair)."""
    for stage in ("models_get", *make_ai_fixtures.S1_STAGES, "R_repair"):
        (folder / stage).mkdir(parents=True)
    (folder / "models_get" / "default.json").write_bytes(
        (make_ai_fixtures.MOCKS / "models_get" / "default.json").read_bytes()
    )
    for stage in make_ai_fixtures.S1_STAGES:
        (folder / stage / "default.json").write_text('{"claims": "nope"}')
    (folder / "R_repair" / "default.json").write_text('{"still": "wrong"}')
    return folder


def test_a_draft_runs_every_built_stage_and_reports_counts(client: TestClient) -> None:
    built = fixture_engagement.build(with_key(client))
    job = run_draft(client, built.engagement_id)

    assert job["status"] == "done", job
    assert job["type"] == "draft" and job["progress"] == 1.0
    assert job["claims"] == {"verified": 21, "rejected": 0}
    assert job["usage"]["calls"] == 7  # one per chunk: 3 interview windows + 4 documents
    assert job["message"].startswith("Draft v0.1 is ready: 21 claims verified, 0 rejected")
    stages = {s["id"]: s for s in job["stages"]}
    assert [s["id"] for s in job["stages"]] == [sid for sid, _ in draft.STAGES]
    for sid in ("read", "extract", "check"):
        assert stages[sid]["status"] == "done"
        assert stages[sid]["started_at"] <= stages[sid]["finished_at"]
    assert {stages[s]["status"] for s in ("compare", "verify", "build", "questions")} == {"later"}

    state = draft_state(client, built.engagement_id)
    assert state["version"]["label"] == "v0.1" and state["version"]["id"] == job["target_id"]
    assert state["summary"] == {"verified": 21, "rejected": 0, "open_questions": 2, "scrubbed": 0}
    assert state["job"]["id"] == job["id"]
    readiness = client.get(f"/api/engagements/{built.engagement_id}/readiness").json()
    assert readiness["draft_exists"] is True and readiness["nav"]["draft"] == "done"


def test_drafting_needs_everything_on_the_checklist(client: TestClient) -> None:
    built = fixture_engagement.build(client, ["interview_transcript.txt"])
    response = client.post(f"/api/engagements/{built.engagement_id}/draft")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "CONFLICT"
    assert error["message"] == f"The draft can't start yet: {ADD_KEY}."
    assert ADD_KEY in error["details"]["missing"]
    assert len(error["details"]["missing"]) == 2  # the key and a process document
    assert draft_state(client, built.engagement_id)["job"] is None


def test_missing_engagements_and_versions_are_404(client: TestClient) -> None:
    assert client.post("/api/engagements/nope/draft").status_code == 404
    assert client.get("/api/engagements/nope/draft").status_code == 404
    response = client.get("/api/versions/nope/rejected-claims")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == draft.VERSION_MISSING


def test_an_empty_draft_state_before_the_first_draft(client: TestClient) -> None:
    built = fixture_engagement.build(client, [])
    assert draft_state(client, built.engagement_id) == {
        "job": None,
        "version": None,
        "summary": None,
    }


def test_rejected_claims_register_shows_each_trap(settings_config: AppConfig) -> None:
    config = dataclasses.replace(settings_config, mock_fixtures_dir=TRAPS)
    for client in make_client(config):
        built = fixture_engagement.build(with_key(client))
        job = run_draft(client, built.engagement_id)
        assert job["status"] == "done" and job["claims"] == {"verified": 2, "rejected": 5}

        response = client.get(f"/api/versions/{job['target_id']}/rejected-claims")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 5 == len(body["items"])
        assert body["scrub_count"] == 1
        assert body["instruction_like_count"] >= 1  # RP-02 section 9
        rows = {item["claim_text"].split(":")[0]: item for item in body["items"]}
        assert {k: rows[k]["guardrail"] for k in rows} == {
            "T1": "G3",
            "T2": "G4",
            "T3": "G5",
            "T4": "G5",
            "T5": "G4",
        }
        assert all(item["stage"] == "S1" for item in body["items"])
        t1 = rows["T1"]
        assert t1["passage_available"] is False and t1["anchor"] == "" and t1["segment_id"] is None
        t3 = rows["T3"]
        assert t3["passage_available"] is True and t3["segment_id"]
        assert t3["anchor"] and t3["source_name"] == "interview_transcript.txt"
        assert rows["T5"]["source_name"] == "sop_LC-07.docx" and rows["T5"]["anchor"]
        assert "Priya" not in response.text and "Nair" not in response.text


def test_a_failed_draft_saves_nothing_but_keeps_the_usage(
    settings_config: AppConfig, tmp_path: Path
) -> None:
    config = dataclasses.replace(settings_config, mock_fixtures_dir=broken_mocks(tmp_path / "m"))
    for client in make_client(config):
        built = fixture_engagement.build(
            with_key(client), ["interview_transcript.txt", "sop_LC-07.docx"]
        )
        job = run_draft(client, built.engagement_id)
        assert job["status"] == "failed"
        assert job["error"] == s1_extract.FORMAT_FAILED
        assert "Nothing was saved" in job["error"]
        stages = {s["id"]: s["status"] for s in job["stages"]}
        assert stages["read"] == "done" and stages["extract"] == "failed"
        assert job["claims"] == {"verified": 0, "rejected": 0}
        assert job["usage"]["calls"] == 2  # the first answer and the repair attempt

        state = draft_state(client, built.engagement_id)
        assert state["version"] is None and state["summary"] is None
        assert state["job"]["status"] == "failed"
        readiness = client.get(f"/api/engagements/{built.engagement_id}/readiness").json()
        assert readiness["draft_exists"] is False
        usage = client.get("/api/settings/usage").json()
        assert usage["totals"]["calls"] == 2


def test_drafting_again_replaces_a_draft_without_steps(client: TestClient) -> None:
    built = fixture_engagement.build(with_key(client))
    first = run_draft(client, built.engagement_id)
    second = run_draft(client, built.engagement_id)
    assert second["status"] == "done" and second["target_id"] != first["target_id"]
    state = draft_state(client, built.engagement_id)
    assert state["version"]["id"] == second["target_id"]
    sessions = client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        assert [v.id for v in versions.drafts(session, built.engagement_id)] == [
            second["target_id"]
        ]


def test_a_draft_with_steps_on_it_is_never_replaced(client: TestClient) -> None:
    built = fixture_engagement.build(with_key(client))
    job = run_draft(client, built.engagement_id)
    sessions = client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        session.add(
            Element(
                version_id=job["target_id"],
                stable_key="k1",
                kind="activity",
                label="Build the load plan",
                provenance="O",
            )
        )
    response = client.post(f"/api/engagements/{built.engagement_id}/draft")
    assert response.status_code == 409
    assert response.json()["error"]["message"] == draft.HAS_STEPS


def test_only_one_draft_is_made_at_a_time(client: TestClient) -> None:
    built = fixture_engagement.build(with_key(client))
    state = client.app.state  # type: ignore[attr-defined]
    queued: list[str] = []
    first = draft.start_draft(state.config, state.sessions, built.engagement_id, queued.append)
    assert isinstance(first, Ok) and queued == [first.value.job_id]
    second = draft.start_draft(state.config, state.sessions, built.engagement_id, queued.append)
    assert isinstance(second, Err) and second.kind is ErrorKind.CONFLICT
    assert second.message == draft.BUSY and len(queued) == 1
    job = client.get(f"/api/jobs/{first.value.job_id}").json()
    assert job["status"] == "queued" and job["target_id"] is None
    assert [s["status"] for s in job["stages"]][:3] == ["waiting"] * 3


def test_a_draft_interrupted_by_a_restart_starts_again_cleanly(client: TestClient) -> None:
    built = fixture_engagement.build(with_key(client))
    state = client.app.state  # type: ignore[attr-defined]
    with session_scope(state.sessions) as session:
        half = versions.create(
            session, engagement_id=built.engagement_id, label="v0.1", state="draft"
        )
        job = jobs_repo.create(
            session,
            engagement_id=built.engagement_id,
            job_type=draft.DRAFT_JOB,
            target_id=half.id,
            stages=draft.initial_stages(),
        )
        jobs_repo.update(session, job.id, status="running")
    queued: list[str] = []
    assert jobs.resume_jobs(state.sessions, queued.append) == [job.id]
    jobs.run_job(state.config, state.sessions, job.id)
    finished = client.get(f"/api/jobs/{job.id}").json()
    assert finished["status"] == "done" and finished["target_id"] != half.id
    with session_scope(state.sessions) as session:
        assert versions.get(session, half.id) is None
        assert [v.id for v in versions.drafts(session, built.engagement_id)] == [
            finished["target_id"]
        ]


def test_an_unexpected_error_is_reported_plainly_and_saves_nothing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    built = fixture_engagement.build(with_key(client))

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("bug")

    monkeypatch.setattr(s1_extract, "extract_source", boom)
    job = run_draft(client, built.engagement_id)
    assert job["status"] == "failed" and job["error"] == draft.UNEXPECTED
    assert draft_state(client, built.engagement_id)["version"] is None


def test_no_connection_stops_the_draft_before_anything_is_made(
    settings_config: AppConfig, tmp_path: Path
) -> None:
    config = dataclasses.replace(settings_config, mock_fixtures_dir=tmp_path / "no-answers")
    for client in make_client(config):
        built = fixture_engagement.build(with_key(client))
        job = run_draft(client, built.engagement_id)
        assert job["status"] == "failed" and job["error"] == context.UNREACHABLE
        assert job["stages"][0]["status"] == "failed"
        assert job["usage"]["calls"] == 0
        assert draft_state(client, built.engagement_id)["version"] is None


def test_usage_lists_calls_newest_first_without_any_text(client: TestClient) -> None:
    built = fixture_engagement.build(with_key(client))
    run_draft(client, built.engagement_id)
    response = client.get("/api/settings/usage?limit=3")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 3 and body["totals"]["calls"] == 7
    stamps = [item["created_at"] for item in body["items"]]
    assert stamps == sorted(stamps, reverse=True)
    assert set(body["items"][0]) == {
        "id", "created_at", "job_id", "stage_id", "prompt_version", "model", "input_tokens",
        "output_tokens", "duration_ms", "status",
    }  # fmt: skip
    assert body["items"][0]["status"] == "mock"
    assert "load plan" not in response.text.lower()


@pytest.mark.parametrize("limit", [0, 501])
def test_usage_limit_must_be_sensible(client: TestClient, limit: int) -> None:
    response = client.get(f"/api/settings/usage?limit={limit}")
    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "limit"


def test_draft_jobs_are_found_again_after_waiting(client: TestClient) -> None:
    built = fixture_engagement.build(with_key(client))
    response = client.post(f"/api/engagements/{built.engagement_id}/draft")
    job_id = response.json()["job_id"]
    wait_for_jobs(client)
    assert draft_state(client, built.engagement_id)["job"]["id"] == job_id
