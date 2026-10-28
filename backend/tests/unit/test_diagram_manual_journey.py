"""Eric's case (2026-10-28), end to end with Claude mocked: one manual whose process is a boxed
flow diagram, each stage labelled with its team, drafted with no interview. The diagram is read
box by box with its label, so claims naming the team pass the role check and a claim naming a
team the page doesn't show is still rejected; the logo isn't a picture suggestion and each icon is
suggested once; the draft map downloads before anything is reviewed; "What to do next" lists the
must-fix exits first; the rest is accepted in one go; pictures are discarded in one go; once Eric
adds the exits the map publishes, Limited ("Built from documents only")."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from app.config import AppConfig
from app.services import signal
from tests import fixture_engagement
from tests.fixtures.make_ai_fixtures import DIAGRAM_ROLE, DIAGRAM_SOURCES
from tests.unit.test_draft_api import make_client, run_draft, with_key
from tests.unit.test_review_actions import Drafted

STEPS = [
    ("Draft load plan", "activity", "Load control team"),
    ("Approve load plan", "approval", "Load control lead"),
    ("Load ULDs", "activity", "Ramp"),
    ("Return loading report", "activity", "Ramp"),
    ("Deviation in limits?", "decision", "Captain"),
    ("Accept final load sheet", "approval", "Captain"),
]
STRUCTURAL = {"start", "end"}


@pytest.fixture()
def diagram(settings_config: AppConfig) -> Iterator[Drafted]:
    for client in make_client(settings_config):
        client.put("/api/settings/profile", json={"owner_name": "Owner"})
        built = fixture_engagement.build(with_key(client), DIAGRAM_SOURCES)
        added = client.post(f"/api/engagements/{built.engagement_id}/roles", json=DIAGRAM_ROLE)
        assert added.status_code == 201, added.text
        job = run_draft(client, built.engagement_id)
        assert job["status"] == "done", job
        graph = client.get(f"/api/versions/{job['target_id']}/graph").json()
        ids = {e["label"]: e["id"] for e in graph["elements"]}
        drafted = Drafted(client, built.engagement_id, job["target_id"], ids)
        drafted.source_id = built.sources[DIAGRAM_SOURCES[0]]  # type: ignore[attr-defined]
        drafted.job = job  # type: ignore[attr-defined]
        yield drafted


def get(d: Drafted, path: str) -> Any:
    response = d.client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_diagram_is_read_box_by_box_with_its_team_label(diagram: Drafted) -> None:
    d = diagram
    page = get(d, f"/api/sources/{d.source_id}/segments?page_size=200")  # type: ignore[attr-defined]
    texts = [s["text"] for s in page["segments"] if s["page"] == 1]
    assert texts[2].startswith("LOAD CONTROL TEAM: 1. PLAN THE LOAD • Draft the preliminary")
    assert texts[3].startswith("RAMP TEAM: 2. LOAD THE AIRCRAFT • Load ULDs as per the load plan")
    assert not any("A. ACCEPT CARGO" in t and "1. PLAN THE LOAD" in t for t in texts)


def test_claims_naming_the_boxes_team_pass_and_a_team_the_page_doesnt_show_is_rejected(
    diagram: Drafted,
) -> None:
    d = diagram
    graph = get(d, f"/api/versions/{d.version_id}/graph")
    lanes = {r["id"]: r["name"] for r in graph["roles"]}
    steps = [e for e in graph["elements"] if e["kind"] not in STRUCTURAL]
    assert [(e["label"], e["kind"], lanes[e["lane_role_id"]]) for e in steps] == STEPS
    assert {e["source_state"] for e in steps} == {"documented_only"}
    rejected = get(d, f"/api/versions/{d.version_id}/rejected-claims")["items"]
    assert [(r["guardrail"], r["reason"]) for r in rejected] == [
        ("G5", "role not found in cited text: Airline ops")
    ]
    ready = get(d, f"/api/engagements/{d.engagement_id}/readiness")
    assert ready["signal"]["detail"] == signal.DOCUMENTS_ONLY.detail


def test_only_the_icons_are_suggested_each_once(diagram: Drafted) -> None:
    d = diagram
    pictures = get(d, f"/api/versions/{d.version_id}/images")
    assert len(pictures) == 2  # the logo on every page is never suggested
    assert len({p["element_id"] for p in pictures}) == 1  # both on the first step citing page 1
    assert {p["status"] for p in pictures} == {"suggested"}


def test_from_a_whole_draft_to_a_published_map(diagram: Drafted) -> None:
    d = diagram
    html = d.client.get(f"/api/versions/{d.version_id}/export/html")
    assert html.status_code == 200
    assert "Draft: not reviewed, not published. 0 of 6 steps reviewed." in html.text
    for label, _kind, _lane in STEPS:
        assert label in html.text

    steps = get(d, f"/api/versions/{d.version_id}/next-steps")["steps"]
    assert [(s["key"], s["count"], s["bulk"]) for s in steps] == [
        ("fix_map", 2, 0),
        ("review_steps", 6, 4),
        ("pictures", 2, 2),
    ]

    discarded = d.client.post(f"/api/versions/{d.version_id}/images/discard-suggestions")
    assert discarded.json() == {"discarded": 2}
    accepted = d.client.post(f"/api/versions/{d.version_id}/accept-remaining").json()
    assert accepted["accepted"] == 4
    assert [s["label"] for s in accepted["skipped"]] == [
        "Deviation in limits?",
        "Accept final load sheet",
    ]

    # Eric adds the exits the diagram doesn't show, then accepts the last two.
    for start, end, kind, label in (
        ("Deviation in limits?", "Load ULDs", "no", "Outside tolerance: re-trim"),
        ("Accept final load sheet", "Deviation in limits?", "reject", "Refused"),
    ):
        body = {"from": d.ids[start], "to": d.ids[end], "kind": kind, "label": label}
        assert d.client.post(f"/api/versions/{d.version_id}/edges", json=body).status_code == 201
    assert d.client.post(f"/api/versions/{d.version_id}/accept-remaining").json() == {
        "accepted": 2,
        "skipped": [],
    }
    ready = get(d, f"/api/versions/{d.version_id}/next-steps")
    assert ready["ready_to_publish"] is True

    published = d.client.post(f"/api/versions/{d.version_id}/publish")
    assert published.status_code == 200, published.text
    assert published.json()["signal"]["detail"] == signal.DOCUMENTS_ONLY.detail
    md = d.client.get(f"/api/versions/{d.version_id}/export/md").text
    assert "Built from documents only." in md


def test_a_step_the_comparison_left_out_is_still_grounded_in_its_own_claims(
    diagram: Drafted,
) -> None:
    """Eric's cargo manual (2026-10-28): two steps came back with no passage, "not assessed" and
    drawn As done, because the comparison call left them out. A step's own checked claims ground
    it: the passage they quote supports it, so it is documented only, drawn As documented only,
    and passes L2."""
    d = diagram
    step = get(d, f"/api/elements/{d.ids['Return loading report']}")
    passages = [e for e in step["evidence"] if e["stance"] == "supports"]
    assert passages and all(e["verified"] for e in passages)
    assert step["source_state"] == "documented_only"
    assert step["view_membership"] == "documented_only"
    report = get(d, f"/api/versions/{d.version_id}/lint")
    assert not [f for f in report["failures"] if f["rule"] == "L2"], report


def test_claims_about_another_flow_on_the_page_are_set_aside_and_listed(diagram: Drafted) -> None:
    """DECISIONS 81: the page also shows the export flow (accept cargo, build ULDs). This
    engagement maps load control from "Flight scheduled" to "Final load sheet issued", so those
    checked claims are kept off the map, out of the rejected claims, and listed, each with its
    passage."""
    d = diagram
    aside = get(d, f"/api/versions/{d.version_id}/outside-flow")
    assert aside["total"] == 2
    assert [(c["claim_text"], c["claim_type"], c["source_name"], c["anchor"])
            for c in aside["items"]] == [
        ("Cargo acceptance verifies pieces, weight and dimensions.", "activity",
         "process_flow_diagram.pdf", "p. 1"),
        ("The Build-up team secures and nets the ULDs as required.", "activity",
         "process_flow_diagram.pdf", "p. 1"),
    ]  # fmt: skip
    assert all(c["passage_available"] and c["segment_id"] for c in aside["items"])
    graph = get(d, f"/api/versions/{d.version_id}/graph")
    assert [e["label"] for e in graph["elements"] if e["kind"] not in STRUCTURAL] == [
        label for label, _kind, _lane in STEPS
    ]
    rejected = get(d, f"/api/versions/{d.version_id}/rejected-claims")
    assert rejected["total"] == 1
    assert d.job["message"].endswith(  # type: ignore[attr-defined]
        " 2 claims about other flows set aside: see Outside this flow."
    )
