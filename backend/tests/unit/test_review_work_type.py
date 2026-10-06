"""Confirming or changing a step's work type (API_CONTRACT.md → Review: PUT …/work-type;
PRD §3.12.4, §5.7.7 4a, criteria 54 and 55, constraint 7). Illustrative Appendix A engagement,
Claude mocked. Work types drafted there (G1): Draft load plan complicated, Special loads OK? clear
(with an automation flag), Busy wave? not classified (with a work-type question)."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import update

from app.db import session_scope
from app.repositories.tables import MapVersion
from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_review_edit import element, patch
from tests.unit.test_review_refresh import refresh

__all__ = ["drafted"]


def put(d: Drafted, label: str, body: dict[str, Any]) -> Any:
    return d.client.put(f"/api/elements/{d.ids[label]}/work-type", json=body)


def test_confirming_the_proposed_work_type_keeps_the_step_unreviewed(drafted: Drafted) -> None:
    response = put(drafted, "Draft load plan", {"work_type": "complicated", "confirm": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["work_type"], body["constraint_type"], body["work_type_status"]) == (
        "complicated",
        "governing",
        "confirmed",
    )
    assert body["review_status"] == "draft"  # confirming the type is not reviewing the step
    [row] = drafted.audit()
    assert row["action"] == "Confirmed work type"
    assert row["before"] == {"work_type": "complicated", "constraint_type": "governing",
                             "work_type_status": "proposed"}  # fmt: skip
    assert row["after"]["work_type_status"] == "confirmed"
    # Confirming again changes nothing and writes no second row.
    put(drafted, "Draft load plan", {"work_type": "complicated", "confirm": True})
    assert len(drafted.audit()) == 1


def test_changing_the_work_type_is_an_edit_and_complex_work_is_never_automated(
    drafted: Drafted,
) -> None:
    before = element(drafted, "Special loads OK?")
    assert before["ai_flag"]["basis"] == "rule_based_automate_candidate"
    assert before["decision"]["mechanism"] == "rule_based"
    response = put(drafted, "Special loads OK?", {"work_type": "complex", "confirm": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["work_type"], body["constraint_type"], body["work_type_status"]) == (
        "complex",
        "enabling",
        "confirmed",
    )
    assert body["review_status"] == "edited"  # locked like any of Eric's edits
    assert body["ai_flag"] is None  # constraint 7
    assert body["decision"]["mechanism"] == "judgment"  # criterion 55
    [row] = drafted.audit()
    assert row["action"] == "Changed work type"
    assert row["before"] == {"work_type": "clear", "constraint_type": "rigid",
                             "work_type_status": "proposed", "review_status": "draft",
                             "ai_flag": "rule_based_automate_candidate",
                             "decision_mechanism": "rule_based"}  # fmt: skip
    assert row["after"] == {"work_type": "complex", "constraint_type": "enabling",
                            "work_type_status": "confirmed", "review_status": "edited",
                            "ai_flag": None, "decision_mechanism": "judgment"}  # fmt: skip
    lint = drafted.client.get(f"/api/versions/{drafted.version_id}/lint").json()
    assert lint["failures"] == []  # the stored report was refreshed and stays clean


def test_classifying_a_step_answers_its_work_type_question(drafted: Drafted) -> None:
    url = f"/api/versions/{drafted.version_id}/questions"

    def work_type_question() -> dict[str, Any]:
        questions = drafted.client.get(url).json()
        return next(
            q for q in questions
            if q["reason"] == "work_type" and q["element_id"] == drafted.ids["Busy wave?"]
        )  # fmt: skip

    assert work_type_question()["status"] == "open"
    body = put(drafted, "Busy wave?", {"work_type": "complicated", "constraint_type": None,
                                       "confirm": True}).json()  # fmt: skip
    assert (body["work_type"], body["constraint_type"]) == ("complicated", None)  # sent as null
    assert work_type_question()["status"] == "answered"


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"work_type": "complex"}, "confirm"),
        ({"work_type": "complex", "confirm": False}, "confirm"),
        ({"work_type": "not_classified", "confirm": True}, "work_type"),
        ({"work_type": "simple", "confirm": True}, "work_type"),
        ({"work_type": "complex", "constraint_type": "loose", "confirm": True}, "constraint_type"),
    ],
)
def test_the_request_rules_name_the_field(
    drafted: Drafted, body: dict[str, Any], field: str
) -> None:
    response = put(drafted, "Draft load plan", body)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["details"]["field"] == field
    assert drafted.audit() == []


def test_only_steps_of_a_draft_change(drafted: Drafted) -> None:
    body = {"work_type": "complex", "confirm": True}
    assert put(drafted, "Flight scheduled", body).status_code == 422  # start comes from Setup
    missing = drafted.client.put("/api/elements/nope/work-type", json=body)
    assert missing.status_code == 404
    drafted.act("Draft load plan", "reject")
    assert put(drafted, "Draft load plan", body).status_code == 409
    with session_scope(drafted.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        session.execute(
            update(MapVersion).where(MapVersion.id == drafted.version_id).values(state="published")
        )
    assert put(drafted, "Issue load sheet", body).status_code == 409


def test_an_automation_flag_on_complex_work_is_refused_by_the_edit_form(drafted: Drafted) -> None:
    put(drafted, "Draft load plan", {"work_type": "complex", "confirm": True})
    flag = {"component": "action", "input": "Load forecast", "output": "Plan",
            "handoff": "Load controller checks it",
            "basis": "rule_based_automate_candidate"}  # fmt: skip
    response = patch(drafted, "Draft load plan", {"ai_flag": flag})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["details"]["field"] == "ai_flag.basis"
    assert "complex work" in response.json()["error"]["message"]
    support = patch(
        drafted, "Draft load plan", {"ai_flag": flag | {"basis": "judgment_support_only"}}
    )
    assert support.status_code == 200, support.text


def test_a_confirmed_work_type_is_kept_through_refresh(drafted: Drafted) -> None:
    put(drafted, "Draft load plan", {"work_type": "complicated", "confirm": True})
    job = refresh(drafted)
    assert job["status"] == "done", job
    graph = drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()
    step = next(e for e in graph["elements"] if e["label"] == "Draft load plan")
    assert (step["work_type"], step["work_type_status"], step["review_status"]) == (
        "complicated",
        "confirmed",
        "draft",
    )
    others = [e for e in graph["elements"] if e["label"] == "Issue load sheet"]
    assert others[0]["work_type_status"] == "proposed"  # only Eric's confirmation carries over
