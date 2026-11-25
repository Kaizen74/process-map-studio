"""The process at a glance (PRD §3.20; DECISIONS 110): counted as the leadership view counts, the
data lens from Eric's records, never 0 for "not known", and the same figures in the Capability
Compass return file."""

from __future__ import annotations

from typing import Any

from app.domain.leadership import ProcessSummary
from app.services import process_summary
from tests.unit.test_accountability_api import graph
from tests.unit.test_compass_return import download, published
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]

STEPS = {"activity", "decision", "approval"}


def handoffs(g: dict[str, Any]) -> list[dict[str, Any]]:
    lanes = {e["id"]: (e["lane_role_id"], e["kind"]) for e in g["elements"]
             if e["review_status"] != "rejected"}  # fmt: skip
    return [
        x for x in g["edges"]
        if x["from"] in lanes and x["to"] in lanes
        and lanes[x["from"]][1] in STEPS and lanes[x["to"]][1] in STEPS
        and lanes[x["from"]][0] != lanes[x["to"]][0]
    ]  # fmt: skip


def test_the_summary_counts_as_the_leadership_view_and_knows_what_it_cannot_count(
    drafted: Drafted,
) -> None:
    d = drafted
    confirm_all(d)
    assert publish(d).status_code == 200
    body = d.client.get(f"/api/versions/{d.version_id}/leadership").json()
    s = body["summary"]
    phases = body["facts"]["phases"]
    assert s["handoffs"] == sum(p["handoffs"] for p in phases)  # exactly as Leadership counts
    assert s["rework_loops"] == body["recommendation"]["rework_loops"]
    assert s["work_min"] == sum(p["work_min"] for p in phases)
    assert s["wait_min"] == sum(p["wait_min"] for p in phases)
    g = graph(d)
    steps = [e for e in g["elements"] if e["kind"] in STEPS and e["review_status"] != "rejected"]
    assert s["steps"] == len(steps) == len(s["links"]["steps"])
    assert s["decisions"] == sum(1 for e in steps if e["kind"] == "decision")
    assert s["approvals"] == sum(1 for e in steps if e["kind"] == "approval")
    assert s["roles"] == len({e["lane_role_id"] for e in steps})
    # Nothing recorded yet: the data lens is not known, never 0; the Reality views are off.
    assert (s["systems"], s["handoffs_manual"], s["off_system_steps"], s["no_record_steps"]) == (
        None, None, None, None,
    )  # fmt: skip
    assert s["process_owner"] == "" and s["steps_differing"] is None
    metrics = process_summary.metrics(ProcessSummary.model_validate(s))
    assert set(metrics) == {"steps", "decisions", "approvals", "handoffs", "roles",
                            "rework_loops", "work_min", "wait_min"}  # fmt: skip


def test_systems_and_handoffs_by_hand_from_erics_records(drafted: Drafted) -> None:
    d = drafted
    g = graph(d)
    steps = [e for e in g["elements"] if e["kind"] in STEPS]
    made = d.client.post(f"/api/engagements/{d.engagement_id}/roles",
                         json={"name": "Load control system", "is_system": True})  # fmt: skip
    system = made.json()["id"]
    records = [
        {"status": "system", "role_id": system},
        {"status": "other", "other": "Weighbridge log"},
        {"status": "other", "other": "weighbridge  LOG"},  # the same system, written differently
        {"status": "none"},  # paper or memory: not a system
    ]
    for step, record in zip(steps, records, strict=False):
        r = d.client.put(f"/api/elements/{step['id']}/system-of-record", json=record)
        assert r.status_code == 200, r.text
    lines = handoffs(g)
    moves = ["re_keyed", "email_spreadsheet", "system_interface"]
    for line, move in zip(lines, moves, strict=False):
        r = d.client.put(f"/api/versions/{d.version_id}/edges/{line['id']}/data-move",
                         json={"data_move": move})  # fmt: skip
        assert r.status_code == 200, r.text
    d.client.patch(f"/api/engagements/{d.engagement_id}",
                   json={"process_owner_other": "Head of ground operations"})  # fmt: skip
    confirm_all(d)
    assert publish(d).status_code == 200
    s = d.client.get(f"/api/versions/{d.version_id}/leadership").json()["summary"]
    assert s["systems"] == 2
    assert s["links"]["systems"] == [e["id"] for e in steps[:3]]
    assert (s["handoffs_manual"], s["handoffs_known"], s["handoffs"]) == (2, 3, len(lines))
    assert set(s["links"]["handoffs_manual"]) == {lines[0]["from"], lines[1]["from"]}
    assert s["process_owner"] == "Head of ground operations"


def test_the_return_file_carries_the_same_figures(drafted: Drafted) -> None:
    d = drafted
    link = published(d)
    file = download(d).json()
    [found] = [f for f in file["findings"] if f["kind"] == "process_summary"]
    s = d.client.get(f"/api/versions/{d.version_id}/leadership").json()["summary"]
    assert found["metrics"] == process_summary.metrics(ProcessSummary.model_validate(s))
    assert found["ref"] == link["pilot_ref"]
    assert found["figure"] == f"{s['steps']} steps, {s['handoffs']} handoffs"
    assert found["detail"].startswith(f"Counted on the published map: {s['steps']} steps, ")
    assert "process_owner" not in found  # not named: left out
