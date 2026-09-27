"""Editing a step (API_CONTRACT.md → Review: PATCH /elements/{eid}, PUT …/raci; PRD §5.7.6): the
field rules, the edited status, audit rows and the refreshed lint report. Illustrative Appendix A
engagement, Claude mocked."""

from __future__ import annotations

from typing import Any

import pytest

from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]  # the fixture, shared with the review-action tests


def patch(d: Drafted, label: str, body: Any) -> Any:
    return d.client.patch(f"/api/elements/{d.ids[label]}", json=body)


def element(d: Drafted, label: str) -> dict[str, Any]:
    return dict(d.client.get(f"/api/elements/{d.ids[label]}").json())


def role(d: Drafted, name: str) -> str:
    roles = d.client.get(f"/api/engagements/{d.engagement_id}/roles").json()
    return str(next(r["id"] for r in roles if r["name"] == name))


def test_an_edit_changes_only_what_was_sent_and_is_audited(drafted: Drafted) -> None:
    response = patch(drafted, "Draft load plan", {"label": "Build the load plan", "work_min": 25,
                                                  "kpi": "Plan issued by T-90"})  # fmt: skip
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["label"], body["time"]["work_min"], body["kpi"]) == (
        "Build the load plan", 25, "Plan issued by T-90")  # fmt: skip
    assert body["review_status"] == "edited"
    assert body["time"]["text"] == "About twenty minutes, around T-120"  # not sent, unchanged
    assert body["evidence"][0]["quote"]  # evidence stays
    [row] = drafted.audit()
    assert row["action"] == "Edited step"
    assert row["before"] == {"label": "Draft load plan", "work_min": 20.0, "kpi": "",
                             "review_status": "draft"}  # fmt: skip
    assert row["after"] == {"label": "Build the load plan", "work_min": 25, "kpi":
                            "Plan issued by T-90", "review_status": "edited"}  # fmt: skip
    layout = drafted.client.get(f"/api/versions/{drafted.version_id}/layout").json()
    node = next(n for n in layout["nodes"] if n["id"] == drafted.ids["Draft load plan"])
    assert node["label_lines"] == ["Build the", "load plan"]


def test_sending_the_same_values_changes_nothing(drafted: Drafted) -> None:
    body = patch(drafted, "Draft load plan", {"label": "Draft load plan"}).json()
    assert body["review_status"] == "draft"
    assert drafted.audit() == []


@pytest.mark.parametrize(
    ("label", "body", "where"),
    [
        ("Draft load plan", {"label": "  "}, "label"),
        ("Draft load plan", {"label": "x" * 121}, "label"),
        ("Draft load plan", {"kind": "start"}, "kind"),
        ("Draft load plan", {"lane_role_id": "nope"}, "lane_role_id"),
        ("Draft load plan", {"work_min": -5}, "work_min"),
        ("Draft load plan", {"complexity": "XL"}, "complexity"),
        ("Draft load plan", {"kpi": "k" * 301}, "kpi"),
        ("Special loads OK?", {"decision": {"mechanism": "none"}}, "decision.mechanism"),
        ("Draft load plan", {"constraints": [{"text": " "}]}, "constraints"),
        ("Draft load plan", {"constraints": [{"text": "x", "cause_type": "luck"}]}, "constraints"),
        ("Draft load plan", {"ai_flag": {"component": "magic", "input": "a", "output": "b",
                                         "handoff": "c", "basis": "judgment_support_only"}},
         "ai_flag.component"),
        ("Draft load plan", {"ai_flag": {"component": "action", "input": "a", "output": " ",
                                         "handoff": "c", "basis": "judgment_support_only"}},
         "ai_flag.output"),
    ],
)  # fmt: skip
def test_the_field_rules_name_the_field(
    drafted: Drafted, label: str, body: dict[str, Any], where: str
) -> None:
    response = patch(drafted, label, body)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["details"]["field"] == where
    assert element(drafted, label)["review_status"] == "draft"  # nothing saved


def test_a_judgment_step_is_never_an_automation_candidate(drafted: Drafted) -> None:
    flag = {"component": "reasoning", "input": "Weights", "output": "Decision",
            "handoff": "Captain", "basis": "rule_based_automate_candidate"}  # fmt: skip
    response = patch(drafted, "Deviation in limits?", {"ai_flag": flag})
    assert response.status_code == 422
    assert response.json()["error"]["message"] == (
        "A judgment step is never an automation candidate. Choose support only."
    )
    flag["basis"] = "judgment_support_only"
    body = patch(drafted, "Deviation in limits?", {"ai_flag": flag}).json()
    assert body["ai_flag"]["basis"] == "judgment_support_only"
    assert patch(drafted, "Deviation in limits?", {"ai_flag": None}).json()["ai_flag"] is None


def test_a_hidden_name_is_refused_without_repeating_it(drafted: Drafted) -> None:
    response = patch(drafted, "Issue load sheet", {"kpi": "Priya Nair signs by T-10"})
    assert response.status_code == 422
    assert response.json()["error"]["message"] == (
        "The KPI contains a name from your list of names to hide. Use the role instead."
    )
    assert "Priya" not in response.text


def test_raci_rules(drafted: Drafted) -> None:
    lc, lead, ramp = role(drafted, "Load controller"), role(drafted, "Load control lead"), role(
        drafted, "Ramp")  # fmt: skip
    url = f"/api/elements/{drafted.ids['Draft load plan']}/raci"
    cases = [
        ([{"role_id": lc, "letter": "R"}], "Choose who is Accountable for this step."),
        ([{"role_id": lc, "letter": "A"}], "An activity needs exactly one Responsible role."),
        ([{"role_id": lc, "letter": "R"}, {"role_id": lc, "letter": "A"},
          {"role_id": lead, "letter": "A"}], "A step has one Accountable role."),
        ([{"role_id": "nope", "letter": "R"}], "Choose one of this engagement's roles"),
        ([{"role_id": lc, "letter": "X"}], "RACI letters are R, A, C or I."),
    ]  # fmt: skip
    for raci, message in cases:
        response = drafted.client.put(url, json=raci)
        assert response.status_code == 422, raci
        assert response.json()["error"]["message"].startswith(message)
    ok = [
        {"role_id": lc, "letter": "R"},
        {"role_id": lc, "letter": "A", "contested": True},
        {"role_id": lead, "letter": "A", "contested": True},
        {"role_id": ramp, "letter": "I"},
    ]
    body = drafted.client.put(url, json=ok).json()  # fmt: skip
    assert sorted((r["role_name"], r["letter"], r["contested"]) for r in body["raci"]) == [
        ("Load control lead", "A", True),
        ("Load controller", "A", True),
        ("Load controller", "R", False),
        ("Ramp", "I", False),
    ]
    assert body["review_status"] == "edited"


def test_raci_entries_that_stay_keep_their_passages(drafted: Drafted) -> None:
    before = element(drafted, "Deviation in limits?")
    kept = [{"role_id": r["role_id"], "letter": r["letter"], "contested": r["contested"]}
            for r in before["raci"] if r["letter"] == "A"]  # fmt: skip
    body = drafted.client.put(
        f"/api/elements/{drafted.ids['Deviation in limits?']}/raci", json=kept
    ).json()
    assert [r["letter"] for r in body["raci"]] == ["A", "A"]
    assert all(r["sources"] for r in body["raci"])  # the competing passages are still there


def test_editing_refreshes_lint(drafted: Drafted) -> None:
    lint_url = f"/api/versions/{drafted.version_id}/lint"
    patch(drafted, "Issue load sheet", {"lane_role_id": role(drafted, "Ramp")})
    rules = [f["rule"] for f in drafted.client.get(lint_url).json()["failures"]]
    assert rules == ["L6"]  # the activity no longer sits in its Responsible role's lane


def test_rejected_start_and_unknown_fields_are_refused(drafted: Drafted) -> None:
    drafted.act("Issue load sheet", "reject")
    rejected = patch(drafted, "Issue load sheet", {"label": "New"})
    assert rejected.status_code == 409
    assert rejected.json()["error"]["message"] == (
        "This step is rejected. Restore it before editing it."
    )
    assert patch(drafted, "Flight scheduled", {"label": "New"}).status_code == 422
    assert patch(drafted, "Draft load plan", {"colour": "red"}).status_code == 422
    assert drafted.client.patch("/api/elements/nope", json={"label": "x"}).status_code == 404
