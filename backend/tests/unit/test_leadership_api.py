"""The leadership view endpoints (API_CONTRACT.md → Leadership view; PRD §4 Views, §5.4 Leadership,
§6.3 P11) on the illustrative Appendix A map, published."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]

GROUPS = ("work", "wait", "rework_loops", "handoffs")


@pytest.fixture()
def published(drafted: Drafted) -> Drafted:
    confirm_all(drafted)
    response = publish(drafted)
    assert response.status_code == 200, response.text
    return drafted


def view(d: Drafted) -> dict[str, Any]:
    response = d.client.get(f"/api/versions/{d.version_id}/leadership")
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_a_draft_is_refused_in_plain_words(drafted: Drafted) -> None:
    response = drafted.client.get(f"/api/versions/{drafted.version_id}/leadership")
    assert response.status_code == 409
    assert response.json()["error"]["message"] == (
        "The leadership view shows a published map. Publish this draft first, then open Leadership."
    )
    assert drafted.client.get("/api/versions/nope/leadership").status_code == 404


def test_the_three_parts_of_the_published_sample(published: Drafted) -> None:
    body = view(published)
    assert (body["version"]["label"], body["version"]["state"]) == ("v1.0", "published")
    assert set(body) == {"version", "facts", "interpretation", "recommendation", "reality"}
    assert body["reality"] is None  # the Reality views switch is off (P13b, G17)
    phases = [(p["name"], p["work_min"], p["wait_min"], p["rework_loops"], p["handoffs"])
              for p in body["facts"]["phases"]]  # fmt: skip
    assert phases == [
        # A.10 (C3): + the hand-overs stitched across the interviews (plan → loading, loading
        # report → deviation check).
        ("Plan", 20, 0, 1, 4),
        ("Check and load", 80, 15, 1, 5),
        ("Close out", 15, 0, 1, 3),
    ]
    causes = {c["cause_type"]: c for c in body["interpretation"]["causes"]}
    assert causes["system_fragmentation"]["systemic"] is True
    # A.10 (C3): + the landscape interview's weakness (the loading report on a separate system).
    assert causes["system_fragmentation"]["evidence_weight"] == {"supporting": 4, "sources": 6}
    assert causes["single_point_knowledge"]["systemic"] is False
    rec = body["recommendation"]
    assert (rec["recoverable_wait_min"], rec["rework_loops"]) == (15, 3)
    assert rec["decisions_needed"] == [{"cause_type": "system_fragmentation", "text": ""}]
    # Every figure's steps exist on the published map (drill-back).
    graph = published.client.get(f"/api/versions/{published.version_id}/graph").json()
    on_map = {e["id"] for e in graph["elements"]}
    linked = {
        *(i for p in body["facts"]["phases"] for group in GROUPS for i in p["links"][group]),
        *(i for c in body["interpretation"]["causes"] for i in c["element_ids"]),
        *rec["recoverable_wait_element_ids"],
        *rec["rework_element_ids"],
        *(f["element_id"] for f in rec["ai_flags"]),
    }  # fmt: skip
    assert linked and linked <= on_map
    assert "Priya" not in json.dumps(body)


def test_decision_lines_are_saved_for_systemic_causes_only(published: Drafted) -> None:
    url = f"/api/versions/{published.version_id}/leadership/decisions"
    line = "Fund one digital loading report across Ramp and Load control."
    saved = published.client.put(url, json=[{"cause_type": "system_fragmentation", "text": line}])
    assert saved.status_code == 200, saved.text
    assert saved.json() == [{"cause_type": "system_fragmentation", "text": line}]
    assert view(published)["recommendation"]["decisions_needed"][0]["text"] == line
    audit = published.client.get(f"/api/versions/{published.version_id}/audit").json()
    assert audit[0]["action"] == "Saved leadership decisions"

    local = published.client.put(url, json=[{"cause_type": "capacity_mismatch", "text": "x"}])
    assert local.status_code == 422
    assert local.json()["error"]["message"] == "Decisions are recorded for systemic causes only."
    long = published.client.put(
        url, json=[{"cause_type": "system_fragmentation", "text": "x" * 501}]
    )
    assert long.status_code == 422
    assert long.json()["error"]["message"] == "Keep each decision under 500 characters."
    assert published.client.put(url, json=[{"cause_type": "x", "extra": 1}]).status_code == 422

    cleared = published.client.put(url, json=[{"cause_type": "system_fragmentation", "text": " "}])
    assert cleared.json() == [{"cause_type": "system_fragmentation", "text": ""}]
    assert (
        published.client.put("/api/versions/nope/leadership/decisions", json=[]).status_code == 404
    )


def test_decisions_on_a_draft_are_refused(drafted: Drafted) -> None:
    url = f"/api/versions/{drafted.version_id}/leadership/decisions"
    response = drafted.client.put(url, json=[])
    assert response.status_code == 409
