"""The whole journey for a map drafted from an interview alone (P12, Eric's decision 2026-09-29),
Claude mocked: the illustrative sample with its transcript as the only source. Drafting, review,
the quality card (a Limited warning, never a blocker), publishing, every export and the views that
read a published map all work without a document, and the grounding checks still refuse what only
a document states."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest

from app.config import AppConfig
from app.services import signal
from tests import fixture_engagement
from tests.unit.test_draft_api import make_client, run_draft, with_key
from tests.unit.test_review_actions import Drafted

STEPS = [
    ("Draft load plan", "activity", "Load controller"),
    ("Special loads OK?", "decision", "Load controller"),
    ("Resolve or offload", "activity", "Airline ops"),
    ("Load aircraft", "activity", "Ramp"),
    # v1.10 A.5: the busy-wave decision and its lived branch come from the interview alone.
    ("Busy wave?", "decision", "Load controller"),
    ("Read report at aircraft", "activity", "Load controller"),
    ("Deviation in limits?", "decision", "Load controller"),
    ("Approve deviation", "approval", "Captain"),
    ("Issue load sheet", "activity", "Load controller"),
]
STEP_LABELS = [label for label, _kind, _lane in STEPS]
STRUCTURAL = {"start", "end"}


@pytest.fixture()
def interview_only(settings_config: AppConfig) -> Iterator[Drafted]:
    for client in make_client(settings_config):
        client.put("/api/settings/profile", json={"owner_name": "Owner"})
        built = fixture_engagement.build(with_key(client), ["interview_transcript.txt"])
        job = run_draft(client, built.engagement_id)
        assert job["status"] == "done", job
        graph = client.get(f"/api/versions/{job['target_id']}/graph").json()
        ids = {e["label"]: e["id"] for e in graph["elements"]}
        yield Drafted(client, built.engagement_id, job["target_id"], ids)


def get(d: Drafted, path: str) -> Any:
    response = d.client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def confirm_all(d: Drafted) -> None:
    for label in STEP_LABELS:
        assert d.act(label, "confirm").status_code == 200


def test_an_interview_alone_drafts_a_practiced_only_map(interview_only: Drafted) -> None:
    d = interview_only
    graph = get(d, f"/api/versions/{d.version_id}/graph")
    lanes = {r["id"]: r["name"] for r in graph["roles"]}
    steps = [e for e in graph["elements"] if e["kind"] not in STRUCTURAL]
    assert [(e["label"], e["kind"], lanes[e["lane_role_id"]]) for e in steps] == STEPS
    assert {e["source_state"] for e in steps} == {"practiced_only"}
    # Only the interview is behind the map: no silent document, no document evidence.
    assert {ev["source_kind"] for e in steps for ev in e["evidence"]} == {"interview_transcript"}
    assert get(d, f"/api/versions/{d.version_id}/lint")["failures"] == []
    # The T-10 deadline is only in the SOP: without it, the grounding check refuses it (G5).
    rejected = get(d, f"/api/versions/{d.version_id}/rejected-claims")["items"]
    assert [(r["guardrail"], r["reason"]) for r in rejected] == [
        ("G5", "number not found in cited text: T-10")
    ]
    issue = next(e for e in steps if e["label"] == "Issue load sheet")
    assert issue["kpi"] == ""
    state = get(d, f"/api/engagements/{d.engagement_id}/draft")
    assert state["summary"]["steps"] == 9


def test_the_quality_card_warns_but_publishing_is_allowed(interview_only: Drafted) -> None:
    d = interview_only
    card = get(d, f"/api/versions/{d.version_id}/quality-card")
    assert signal.QUALITY_WARNING in card["warnings"]
    assert [c["id"] for c in card["checks"] if c["status"] == "fail"] == ["Q6"]  # review only
    confirm_all(d)
    published = d.client.post(f"/api/versions/{d.version_id}/publish")
    assert published.status_code == 200, published.text
    body = published.json()
    assert (body["label"], body["quality_card"]["all_green"]) == ("v1.0", True)
    assert body["signal"]["level"] == "limited"
    [listed] = get(d, f"/api/engagements/{d.engagement_id}/versions")
    assert listed["signal"] == body["signal"]


def test_every_export_and_view_of_the_published_map(interview_only: Drafted) -> None:
    d = interview_only
    confirm_all(d)
    assert d.client.post(f"/api/versions/{d.version_id}/publish").status_code == 200
    url = f"/api/versions/{d.version_id}/export"
    md = d.client.get(f"{url}/md").text
    assert "Signal strength: Limited (1 of 3). Built from interviews only." in md
    assert "All hard checks green: yes." in md
    html = d.client.get(f"{url}/html").text
    assert "Signal strength: Limited (1 of 3)" in html
    graph = json.loads(d.client.get(f"{url}/json").text)
    assert len([e for e in graph["elements"] if e["kind"] not in STRUCTURAL]) == 9
    assert d.client.get(f"{url}/csv").status_code == 200
    for text in (md, html, json.dumps(graph)):
        assert "Priya" not in text
    # The views that read a map work with one source.
    matrix = get(d, f"/api/versions/{d.version_id}/alignment-matrix")
    assert matrix and get(d, f"/api/versions/{d.version_id}/layout")["lanes"]
    leadership = d.client.get(f"/api/versions/{d.version_id}/leadership")
    assert leadership.status_code == 200, leadership.text
    # Reopening keeps the signal: it is worked out from the sources the map was drafted from.
    reopened = d.client.post(f"/api/versions/{d.version_id}/reopen")
    assert reopened.status_code == 201, reopened.text
    assert reopened.json()["signal"]["level"] == "limited"
