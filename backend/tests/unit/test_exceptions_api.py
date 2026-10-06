"""Exceptions, rework and workarounds on the sample (API_CONTRACT.md → GET /versions/{vid}/
exceptions; X2): As done shows a third of the steps off the usual route (special loads refused,
the busy-wave workaround, a deviation outside limits) with two rework loops; As documented shows
none of it. Read-only, names hidden. Claude mocked."""

from __future__ import annotations

from typing import Any

from app.db import session_scope
from app.repositories import elements as map_repo
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]


def report(d: Drafted, view: str | None = None) -> Any:
    found = d.client.get(f"/api/versions/{d.version_id}/exceptions",
                         params={"view": view} if view else {})  # fmt: skip
    assert found.status_code == 200, found.text
    return found.json()


def test_as_done_shows_the_exception_handling_and_the_workaround(drafted: Drafted) -> None:
    done = report(drafted)
    assert done["view"] == "done"
    assert done["summary"] == {
        "steps": 9, "usual_steps": 6, "exception_steps": 2, "variation_steps": 1,
        "off_usual_share": 0.33, "routes": 3, "rework_loops": 2, "workarounds": 1,
        "extra_handoffs": 4, "frequency_stated": 0,
    }  # fmt: skip
    assert {s["label"]: s["route"] for s in done["steps"]} == {
        "Draft load plan": "usual", "Special loads OK?": "usual",
        "Resolve or offload": "exception", "Load and return LIR": "usual",
        "Busy wave?": "usual", "Read report at aircraft": "variation",
        "Deviation in limits?": "usual", "Approve deviation": "exception",
        "Issue load sheet": "usual",
    }  # fmt: skip
    assert [(r["from_label"], r["condition"], r["labels"], r["lanes"],
             [(x["kind"], x["label"]) for x in r["exits"]]) for r in done["routes"]] == [
        ("Special loads OK?", "No", ["Resolve or offload"], ["Airline ops"],
         [("loops_back", "Draft load plan")]),
        ("Busy wave?", "on a busy wave", ["Read report at aircraft"], ["Load controller"],
         [("rejoins", "Deviation in limits?")]),
        ("Deviation in limits?", "Outside limits", ["Approve deviation"], ["Captain"],
         [("rejoins", "Issue load sheet"), ("loops_back", "Load and return LIR")]),
    ]  # fmt: skip
    assert [(w["label"], w["condition"], w["stated_reason"]) for w in done["workarounds"]] == [
        ("Read report at aircraft", "on a busy wave", "otherwise we'd miss the slot")
    ]
    assert [(x["from_label"], x["to_label"], x["label"]) for x in done["loops"]] == [
        ("Resolve or offload", "Draft load plan", "Re-plan"),
        ("Approve deviation", "Load and return LIR", "Re-trim"),
    ]
    # Nobody said how often any of it happens: one question per route, from the bank (M5.s2).
    assert [(q["question_id"], q["about"]) for q in done["questions"]] == [
        ("M5.s2", "Special loads OK? → No: Resolve or offload"),
        ("M5.s2", "Busy wave? → on a busy wave: Read report at aircraft"),
        ("M5.s2", "Deviation in limits? → Outside limits: Approve deviation"),
    ]
    asked = {q["wording"] for q in done["questions"]}
    assert asked == {"How often does something like that happen?"}


def test_as_documented_shows_only_the_documents_rework(drafted: Drafted) -> None:
    documented = report(drafted, "documented")
    assert documented["summary"]["off_usual_share"] == 0.0
    assert documented["routes"] == [] and documented["workarounds"] == []
    assert [(x["from_label"], x["to_label"]) for x in documented["loops"]] == [
        ("Approve load plan", "Draft load plan")
    ]


def test_read_only_names_hidden_and_errors(drafted: Drafted) -> None:
    def snapshot() -> list[tuple[str, str | None, str]]:
        with session_scope(drafted.client.app.state.sessions) as session:  # type: ignore[attr-defined]
            return [(e.id, e.lane_role_id, e.label)
                    for e in map_repo.elements(session, drafted.version_id)]  # fmt: skip

    before = snapshot()
    body = drafted.client.get(f"/api/versions/{drafted.version_id}/exceptions").text
    assert snapshot() == before
    terms = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/redaction-terms").json()
    assert terms and not any(t["term"] in body for t in terms)
    assert drafted.client.get("/api/versions/nope/exceptions").status_code == 404
    url = f"/api/versions/{drafted.version_id}/exceptions"
    assert drafted.client.get(url, params={"view": "sideways"}).status_code == 422
