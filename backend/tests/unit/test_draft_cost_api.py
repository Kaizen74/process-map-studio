"""The draft cost estimate and the spending limit (deep review item 5, 2026-10-19;
API_CONTRACT.md → Draft → estimate, Settings → spending). Claude mocked: mock calls never count
as measured usage."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import AppConfig
from app.db import session_scope
from app.domain.models import AiCallRecord
from app.main import create_app
from app.repositories import ai_calls
from app.repositories import jobs as jobs_repo
from tests import fixture_engagement
from tests.unit.test_draft_api import run_draft, with_key


@pytest.fixture()
def built(settings_config: AppConfig) -> Iterator[tuple[TestClient, str]]:
    with TestClient(create_app(settings_config)) as client:
        engagement = fixture_engagement.build(with_key(client))
        yield client, engagement.engagement_id


def estimate(client: TestClient, eid: str) -> dict[str, object]:
    response = client.get(f"/api/engagements/{eid}/draft/estimate")
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_an_estimate_before_any_real_draft_is_assumed(built: tuple[TestClient, str]) -> None:
    client, eid = built
    found = estimate(client, eid)
    sources = [s for s in client.get(f"/api/engagements/{eid}/sources").json()
               if s["text_status"] == "ready" and s["kind"] != "policy_or_charter"]  # fmt: skip
    assert found["sources"] == len(sources) == len(fixture_engagement.SOURCES)
    chars = found["characters"]
    assert isinstance(chars, int) and chars > 1000
    assert (found["basis"], found["drafts_measured"], found["model"]) == (
        "assumed", 0, "claude-opus-5-5")  # fmt: skip
    assert (found["input_tokens"], found["output_tokens"]) == (chars, round(chars * 0.5))
    assert found["cost_usd"] == round((chars * 4 + round(chars * 0.5) * 20) / 1_000_000, 2)
    assert (found["limit_usd"], found["over_limit"], found["prices_checked_on"]) == (
        None, False, "2026-10-19")  # fmt: skip
    assert client.get("/api/engagements/nope/draft/estimate").status_code == 404


def test_a_mock_draft_never_counts_but_a_real_one_does(
    built: tuple[TestClient, str],
) -> None:
    client, eid = built
    job = run_draft(client, eid)  # mocked: its calls are "mock" and carry no tokens
    assert estimate(client, eid)["basis"] == "assumed"
    sessions = client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        assert jobs_repo.get(session, job["id"]) is not None
        ai_calls.add(session, job["id"], [AiCallRecord(
            stage_id="S1_extract", prompt_version="", model="claude-opus-5-5", status="ok",
            input_hash="", input_tokens=90_000, output_tokens=30_000)])  # fmt: skip
    found = estimate(client, eid)
    chars = found["characters"]
    assert isinstance(chars, int)
    assert (found["basis"], found["drafts_measured"]) == ("measured", 1)
    # The draft read the same sources, so the measured ratio gives back its own usage.
    assert (found["input_tokens"], found["output_tokens"]) == (90_000, 30_000)


def test_a_draft_above_the_limit_doesn_t_start(built: tuple[TestClient, str]) -> None:
    client, eid = built
    saved = client.put("/api/settings/spending", json={"draft_cost_limit_usd": 0.01})
    assert saved.status_code == 200 and saved.json()["draft_cost_limit_usd"] == 0.01
    found = estimate(client, eid)
    assert found["over_limit"] is True and found["limit_usd"] == 0.01
    refused = client.post(f"/api/engagements/{eid}/draft")
    assert refused.status_code == 409
    body = refused.json()["error"]
    assert body["code"] == "COST_LIMIT"
    assert body["message"] == (
        f"This draft is estimated at about US${found['cost_usd']:,.2f}, above your limit of "
        "US$0.01. Raise the limit in Settings, or draft from fewer sources."
    )
    assert body["details"]["limit_usd"] == 0.01
    assert client.get(f"/api/engagements/{eid}/draft").json()["job"] is None  # nothing started
    cleared = client.put("/api/settings/spending", json={"draft_cost_limit_usd": None})
    assert cleared.json()["draft_cost_limit_usd"] is None
    assert client.post(f"/api/engagements/{eid}/draft").status_code == 202


def test_the_limit_must_be_a_sensible_amount(built: tuple[TestClient, str]) -> None:
    client, _ = built
    for bad in (0, -5, 1000.01):
        response = client.put("/api/settings/spending", json={"draft_cost_limit_usd": bad})
        assert response.status_code == 422
        assert response.json()["error"]["details"]["field"] == "draft_cost_limit_usd"
    assert client.get("/api/settings").json()["draft_cost_limit_usd"] is None
    most = client.put("/api/settings/spending", json={"draft_cost_limit_usd": 1000})
    assert most.status_code == 200 and most.json()["draft_cost_limit_usd"] == 1000
