"""The whole journey for a map drafted from documents alone (Eric, 2026-10-20), Claude mocked: the
illustrative sample with its two SOPs and two job descriptions as the only sources. Readiness lets
the draft start and recommends an interview; every step is "documented only" and is asked about;
the As done view holds no step (a "not described" connector, never an invented one); the documents'
silence about two exits is left for Eric to fill; once he does, the quality card (a Limited
warning, never a blocker), publishing, every export and the views that read a published map all
work without an interview."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.actions.readiness import ADD_TRANSCRIPT
from app.config import AppConfig
from app.services import signal
from tests import fixture_engagement
from tests.fixtures.make_ai_fixtures import DOCUMENTS_ONLY
from tests.unit.test_draft_api import make_client, run_draft, with_key
from tests.unit.test_review_actions import Drafted
from tests.uploads import FIXTURES, wait_for_jobs

STEPS = [
    ("Draft load plan", "activity", "Load controller"),
    ("Approve load plan", "approval", "Load control lead"),
    ("Special loads OK?", "decision", "Load controller"),
    ("Return loading report", "activity", "Ramp"),
    ("Deviation in limits?", "decision", "Load control lead"),
    ("Issue load sheet", "activity", "Load controller"),
]
STEP_LABELS = [label for label, _kind, _lane in STEPS]
STRUCTURAL = {"start", "end"}
# What the documents never say, added by Eric: where a refused special load and a deviation
# outside tolerance go.
MISSING_EXITS = [
    ("Special loads OK?", "Draft load plan", "no", "No: re-plan"),
    ("Deviation in limits?", "Draft load plan", "no", "Outside tolerance"),
]


def add_missing_exits(client: TestClient, version_id: str) -> None:
    """Eric adds the two exits the documents don't describe (as on the Review screen)."""
    graph = client.get(f"/api/versions/{version_id}/graph").json()
    ids = {e["label"]: e["id"] for e in graph["elements"]}
    for start, end, kind, label in MISSING_EXITS:
        body = {"from": ids[start], "to": ids[end], "kind": kind, "label": label}
        response = client.post(f"/api/versions/{version_id}/edges", json=body)
        assert response.status_code == 201, response.text


@pytest.fixture()
def documents_only(settings_config: AppConfig) -> Iterator[Drafted]:
    for client in make_client(settings_config):
        client.put("/api/settings/profile", json={"owner_name": "Owner"})
        built = fixture_engagement.build(with_key(client), DOCUMENTS_ONLY)
        readiness = client.get(f"/api/engagements/{built.engagement_id}/readiness").json()
        assert readiness["ready_to_draft"] is True, readiness
        assert readiness["recommended"] == [ADD_TRANSCRIPT]
        assert readiness["signal"]["detail"] == signal.DOCUMENTS_ONLY.detail
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


def test_documents_alone_draft_a_documented_only_map(documents_only: Drafted) -> None:
    d = documents_only
    graph = get(d, f"/api/versions/{d.version_id}/graph")
    lanes = {r["id"]: r["name"] for r in graph["roles"]}
    steps = [e for e in graph["elements"] if e["kind"] not in STRUCTURAL]
    assert [(e["label"], e["kind"], lanes[e["lane_role_id"]]) for e in steps] == STEPS
    assert {e["source_state"] for e in steps} == {"documented_only"}
    assert {e["view_membership"] for e in steps} == {"documented_only"}
    assert {e["provenance"] for e in steps} == {"O"}
    # Only documents are behind the map: no interview evidence, nothing invented.
    kinds = {ev["source_kind"] for e in steps for ev in e["evidence"]}
    assert kinds <= {"sop", "job_description"} and "sop" in kinds
    # The T-10 deadline is in the SOP, so it passes the grounding checks here.
    assert get(d, f"/api/versions/{d.version_id}/rejected-claims")["items"] == []
    issue = next(e for e in steps if e["label"] == "Issue load sheet")
    assert issue["kpi"] == "Final load sheet no later than T-10"
    state = get(d, f"/api/engagements/{d.engagement_id}/draft")
    assert state["summary"]["steps"] == 6


def test_as_done_shows_no_invented_step(documents_only: Drafted) -> None:
    """Constraint 23: As done shows only what lived accounts or traces support; the gap is a
    "not described" connector."""
    d = documents_only
    url = f"/api/versions/{d.version_id}"
    done = get(d, f"{url}/graph?view=done")
    assert [e["kind"] for e in done["elements"]] == ["start", "end"]
    assert [(e["kind"], e["label"]) for e in done["edges"]] == [("gap", "Not described")]
    documented = get(d, f"{url}/graph?view=documented")
    assert [e["label"] for e in documented["elements"] if e["kind"] not in STRUCTURAL] == (
        STEP_LABELS
    )
    for view in ("done", "documented"):
        assert get(d, f"{url}/layout?view={view}")["lanes"]


def test_every_step_is_asked_about_without_mentioning_an_interview(documents_only: Drafted) -> None:
    d = documents_only
    questions = get(d, f"/api/versions/{d.version_id}/questions")
    asked = [q["element_label"] for q in questions if q["reason"] == "documented_only"]
    assert asked == STEP_LABELS
    assert [q["question"] for q in questions if q["reason"] == "gap"] == [
        "Which role issues the final load sheet?"
    ]
    assert all("interview doesn't" not in q["question"] for q in questions)


def test_the_documents_silence_is_left_for_eric(documents_only: Drafted) -> None:
    """The documents never say where a refused special load or an out-of-tolerance deviation
    goes: the lint names both, and nothing is published until Eric adds them."""
    d = documents_only
    lint = get(d, f"/api/versions/{d.version_id}/lint")
    assert sorted((f["rule"], f["message"]) for f in lint["failures"]) == [
        ("L4", 'Decision "Deviation in limits?" needs at least two labelled exits; it has 1.'),
        ("L4", 'Decision "Special loads OK?" needs at least two labelled exits; it has 1.'),
    ]
    confirm_all(d)
    refused = d.client.post(f"/api/versions/{d.version_id}/publish")
    assert refused.status_code == 409, refused.text
    add_missing_exits(d.client, d.version_id)
    assert get(d, f"/api/versions/{d.version_id}/lint")["failures"] == []


def test_the_quality_card_warns_but_publishing_is_allowed(documents_only: Drafted) -> None:
    d = documents_only
    card = get(d, f"/api/versions/{d.version_id}/quality-card")
    assert signal.DOCUMENTS_QUALITY_WARNING in card["warnings"]
    assert signal.QUALITY_WARNING not in card["warnings"]
    add_missing_exits(d.client, d.version_id)
    confirm_all(d)
    card = get(d, f"/api/versions/{d.version_id}/quality-card")
    assert [c["id"] for c in card["checks"] if c["status"] == "fail"] == []
    published = d.client.post(f"/api/versions/{d.version_id}/publish")
    assert published.status_code == 200, published.text
    body = published.json()
    assert (body["label"], body["quality_card"]["all_green"]) == ("v1.0", True)
    assert body["signal"] == signal.DOCUMENTS_ONLY.model_dump()
    [listed] = get(d, f"/api/engagements/{d.engagement_id}/versions")
    assert listed["signal"] == body["signal"]


def test_every_export_and_view_of_the_published_map(documents_only: Drafted) -> None:
    d = documents_only
    add_missing_exits(d.client, d.version_id)
    confirm_all(d)
    assert d.client.post(f"/api/versions/{d.version_id}/publish").status_code == 200
    url = f"/api/versions/{d.version_id}/export"
    md = d.client.get(f"{url}/md").text
    assert "Signal strength: Limited (1 of 3). Built from documents only." in md
    assert "All hard checks green: yes." in md
    html = d.client.get(f"{url}/html").text
    assert "Signal strength: Limited (1 of 3)" in html
    graph = json.loads(d.client.get(f"{url}/json").text)
    assert len([e for e in graph["elements"] if e["kind"] not in STRUCTURAL]) == 6
    assert d.client.get(f"{url}/csv").status_code == 200
    # The views that read a map work without an interview.
    assert get(d, f"/api/versions/{d.version_id}/alignment-matrix")
    leadership = d.client.get(f"/api/versions/{d.version_id}/leadership")
    assert leadership.status_code == 200, leadership.text
    for path in ("stories", "glossary", "capability-notes", "exceptions", "value"):
        assert d.client.get(f"/api/versions/{d.version_id}/{path}").status_code == 200, path
    reopened = d.client.post(f"/api/versions/{d.version_id}/reopen")
    assert reopened.status_code == 201, reopened.text
    assert reopened.json()["signal"]["level"] == "limited"


def test_adding_an_interview_later_lifts_the_signal(documents_only: Drafted) -> None:
    """The interview stays recommended: once one is read, the next draft is Strong."""
    d = documents_only
    readiness = get(d, f"/api/engagements/{d.engagement_id}/readiness")
    assert readiness["nav"]["interview"] == "not_started"
    assert readiness["next_step"] == "review"  # the interview is no longer in the way
    roles = {r["name"]: r["id"] for r in get(d, f"/api/engagements/{d.engagement_id}/roles")}
    name = "interview_transcript.txt"
    uploaded = d.client.post(
        f"/api/engagements/{d.engagement_id}/sources",
        files={"file": (name, (FIXTURES / name).read_bytes(), "application/octet-stream")},
    )
    assert uploaded.status_code == 201, uploaded.text
    wait_for_jobs(d.client)
    mapped = d.client.put(
        f"/api/sources/{uploaded.json()['id']}/speakers",
        json={"Interviewer": "interviewer", "Priya Nair": roles["Load controller"]},
    )
    assert mapped.status_code == 200, mapped.text
    readiness = get(d, f"/api/engagements/{d.engagement_id}/readiness")
    assert readiness["signal"]["level"] == "strong"
    assert readiness["recommended"] == []
