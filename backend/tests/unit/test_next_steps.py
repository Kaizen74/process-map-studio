"""What to do next before publishing, and accepting the remaining steps in one go (2026-10-28,
Eric: "not sure what I need to do when"; reviewing step by step "felt like a wall"). API_CONTRACT
→ GET /versions/{vid}/next-steps, POST /versions/{vid}/accept-remaining. Claude mocked."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.db import session_scope
from app.repositories import elements as map_repo
from tests.unit.test_documents_only_journey import add_missing_exits, documents_only
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["documents_only", "drafted"]


def next_steps(d: Drafted) -> dict[str, Any]:
    response = d.client.get(f"/api/versions/{d.version_id}/next-steps")
    assert response.status_code == 200, response.text
    return dict(response.json())


def accept(d: Drafted, phase_id: str | None = None) -> Any:
    body = {"phase_id": phase_id} if phase_id else None
    return d.client.post(f"/api/versions/{d.version_id}/accept-remaining", json=body)


def summary(found: dict[str, Any]) -> list[tuple[str, int, int]]:
    return [(s["key"], s["count"], s["bulk"]) for s in found["steps"]]


def status(d: Drafted, label: str) -> str:
    response = d.client.get(f"/api/elements/{d.ids[label]}")
    assert response.status_code == 200, response.text
    return str(response.json()["review_status"])


def test_a_fresh_draft_has_one_thing_to_do_review_its_steps(drafted: Drafted) -> None:
    found = next_steps(drafted)
    assert found["ready_to_publish"] is False
    assert summary(found) == [("review_steps", 10, 10)]
    [step] = found["steps"]
    assert step["title"] == "Review 10 steps"
    assert "accept the 10 that need nothing fixed as drafted" in step["detail"]


def test_accepting_the_rest_leaves_publish_as_the_only_step(drafted: Drafted) -> None:
    response = accept(drafted)
    assert response.status_code == 200, response.text
    assert response.json() == {"accepted": 10, "skipped": []}
    assert status(drafted, "Approve load plan") == "confirmed"
    found = next_steps(drafted)
    assert found["ready_to_publish"] is True
    assert summary(found) == [("publish", 0, 0)]
    assert found["steps"][0]["title"] == "Publish the map"
    rows = [r for r in drafted.audit() if r["action"] == "Accepted remaining steps as drafted"]
    assert [(r["after"]["count"], r["after"]["phase_id"]) for r in rows] == [(10, None)]
    assert publish(drafted).status_code == 200  # the list and Publish agree


def test_one_phase_at_a_time(drafted: Drafted) -> None:
    graph = drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()
    plan = next(p["id"] for p in graph["phases"] if p["name"] == "Plan")
    in_plan = [e["label"] for e in graph["elements"] if e["phase_id"] == plan]
    response = accept(drafted, plan)
    assert response.status_code == 200, response.text
    assert response.json()["accepted"] == len(in_plan) > 0
    assert all(status(drafted, label) == "confirmed" for label in in_plan)
    assert status(drafted, "Issue load sheet") == "draft"
    assert summary(next_steps(drafted)) == [("review_steps", 10 - len(in_plan), 10 - len(in_plan))]
    wrong = accept(drafted, "not-a-phase")
    assert wrong.status_code == 422
    assert wrong.json()["error"]["message"] == "That phase isn't in this version."


def test_must_fix_steps_are_left_for_eric_and_listed_first(documents_only: Drafted) -> None:
    """The documents-only map: two decisions miss an exit (L4). They stay unreviewed until the
    exits are added; everything else is accepted."""
    d = documents_only
    found = next_steps(d)
    assert summary(found) == [("fix_map", 2, 0), ("review_steps", 6, 4)]
    fix = found["steps"][0]
    assert fix["title"] == "Fix 2 problems on the map"
    assert {i["element_id"] for i in fix["items"]} == {
        d.ids["Special loads OK?"],
        d.ids["Deviation in limits?"],
    }
    response = accept(d).json()
    assert response["accepted"] == 4
    assert [(s["label"], s["reason"].split(":")[0]) for s in response["skipped"]] == [
        ("Special loads OK?", "Fix the map problem first"),
        ("Deviation in limits?", "Fix the map problem first"),
    ]
    assert status(d, "Special loads OK?") == "draft"
    add_missing_exits(d.client, d.version_id)
    assert summary(next_steps(d)) == [("review_steps", 2, 2)]
    assert accept(d).json() == {"accepted": 2, "skipped": []}
    assert next_steps(d)["ready_to_publish"] is True


def test_a_partly_supported_step_is_checked_by_hand(drafted: Drafted) -> None:
    with session_scope(drafted.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        map_repo.update_element(session, drafted.ids["Resolve or offload"], {"needs_check": True})
    found = next_steps(drafted)
    assert summary(found) == [("check_steps", 1, 0), ("review_steps", 10, 9)]
    assert found["steps"][0]["items"][0]["element_id"] == drafted.ids["Resolve or offload"]
    response = accept(drafted).json()
    assert response["accepted"] == 9
    assert response["skipped"] == [
        {
            "element_id": drafted.ids["Resolve or offload"],
            "label": "Resolve or offload",
            "reason": "Only partly supported: check its evidence first.",
        }
    ]


def test_the_list_counts_exactly_what_publish_refuses(documents_only: Drafted) -> None:
    d = documents_only
    blockers = publish(d).json()["error"]["details"]["blockers"]
    by_type = Counter(b["type"] for b in blockers)
    counts = {s["key"]: s["count"] for s in next_steps(d)["steps"]}
    assert counts["review_steps"] == by_type["unreviewed_element"]
    assert counts["fix_map"] == by_type["lint_failure"] + by_type["quality_check"]


def test_a_published_version_has_no_steps_left_and_changes_nothing(drafted: Drafted) -> None:
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    response = drafted.client.get(f"/api/versions/{drafted.version_id}/next-steps")
    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Only a draft has steps left before publishing."
    assert accept(drafted).status_code == 409
    for path in ("next-steps", "accept-remaining"):
        method = drafted.client.get if path == "next-steps" else drafted.client.post
        assert method(f"/api/versions/nope/{path}").status_code == 404
