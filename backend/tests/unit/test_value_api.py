"""The value calculator (API_CONTRACT.md → Value calculator; PRD §3.14; criterion 90; R9b): the
drafted Appendix A sample, with fixture A.11 matched for the measured figures."""

from __future__ import annotations

from typing import Any

import pytest

from app.db import session_scope
from app.repositories import audit
from tests.unit.test_log_alignment_api import EXPECTED, import_log
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_review_edit import role

__all__ = ["drafted"]


def value(d: Drafted, view: str = "done") -> dict[str, Any]:
    response = d.client.get(f"/api/versions/{d.version_id}/value", params={"view": view})
    assert response.status_code == 200, response.text
    return dict(response.json())


def steps(d: Drafted) -> dict[str, dict[str, Any]]:
    return {s["label"]: s for s in value(d)["steps"]}


def costs(d: Drafted, rows: list[dict[str, Any]]) -> Any:
    return d.client.put(f"/api/engagements/{d.engagement_id}/role-costs", json={"rows": rows})


@pytest.fixture()
def measured(drafted: Drafted) -> Drafted:
    lid = import_log(drafted.client, drafted.engagement_id)
    rows = [{"activity": a, "element_id": drafted.ids[s], "status": "confirmed"}
            for a, s in EXPECTED.items()]  # fmt: skip
    drafted.client.put(f"/api/event-logs/{lid}/alignment", json={"rows": rows})
    lc = role(drafted, "Load controller")
    assert costs(drafted, [{"role_id": lc, "hourly_cost": 48, "note": ""}]).status_code == 200
    return drafted


def test_role_costs_per_role_never_per_person(drafted: Drafted) -> None:
    url = f"/api/engagements/{drafted.engagement_id}/role-costs"
    start = drafted.client.get(url).json()
    assert start["currency"] == "SGD"
    assert [r["role_name"] for r in start["rows"]][:3] == ["Load controller", "Load control lead",
                                                           "Ramp"]  # fmt: skip
    assert all(r["hourly_cost"] is None for r in start["rows"])
    lc = role(drafted, "Load controller")
    body = costs(drafted, [{"role_id": lc, "hourly_cost": 48.5, "note": "Loaded rate 2026"}]).json()
    assert body["rows"][0] == {"role_id": lc, "role_name": "Load controller", "hourly_cost": 48.5,
                               "note": "Loaded rate 2026"}  # fmt: skip
    with session_scope(drafted.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        trail = audit.list_recent(session, engagement_id=drafted.engagement_id)
    [row] = [a for a in trail if a["action"] == "Set role costs"]
    assert row["after"] == {"Load controller": 48.5}
    assert costs(drafted, [{"role_id": lc, "hourly_cost": None, "note": ""}]).json()["rows"][0][
        "hourly_cost"] is None  # fmt: skip
    for bad, field in (
        ({"role_id": "nope", "hourly_cost": 1}, "rows[0].role_id"),
        ({"role_id": lc, "hourly_cost": -1}, "rows[0].hourly_cost"),
        ({"role_id": lc, "hourly_cost": 1, "note": "a\nb"}, "rows[0].note"),
    ):
        response = costs(drafted, [{"note": ""} | bad])
        assert response.status_code == 422 and response.json()["error"]["details"]["field"] == field
    assert drafted.client.get("/api/engagements/nope/role-costs").status_code == 404


def test_value_assumptions_have_defaults_and_can_be_changed(drafted: Drafted) -> None:
    url = f"/api/engagements/{drafted.engagement_id}/value-assumptions"
    rows = drafted.client.get(url).json()
    assert [(r["disposition"], r["reduction_pct"], r["default"]) for r in rows] == [
        ("delete", 100.0, True), ("automate_rules", 80.0, True), ("ai_assisted", 50.0, True),
        ("human_approves", 30.0, True), ("keep_human", 0.0, True),
    ]  # fmt: skip
    changed = drafted.client.put(
        url,
        json={
            "rows": [{"disposition": "ai_assisted", "reduction_pct": 40, "note": "Pilot result"}]
        },
    ).json()
    assert changed[2] == {"disposition": "ai_assisted", "reduction_pct": 40.0,
                          "note": "Pilot result", "default": False}  # fmt: skip
    for bad in ({"disposition": "outsource", "reduction_pct": 1},
                {"disposition": "delete", "reduction_pct": 101}):  # fmt: skip
        assert drafted.client.put(url, json={"rows": [bad]}).status_code == 422


def test_without_system_records_only_stated_times_and_no_figure(drafted: Drafted) -> None:
    body = value(drafted)
    plan = {s["label"]: s for s in body["steps"]}["Draft load plan"]
    assert plan["time"] == {"value": 20.0, "label": "estimated",
                            "source": "Stated: About twenty minutes, around T-120"}  # fmt: skip
    assert (plan["volume"], plan["hours_per_month"], plan["evidence"]) == (None, None, None)
    assert plan["missing"] == ["No volume per month: none measured, no override."]
    assert (body["totals"]["steps_counted"], body["potential"]) == (0, "Potential, not committed")


def test_measured_hours_cost_labels_and_scenarios(measured: Drafted) -> None:
    body = value(measured)
    plan = {s["label"]: s for s in body["steps"]}["Draft load plan"]
    assert plan["time"]["value"] == 23.9 and plan["time"]["label"] == "measured"  # rework counts
    assert plan["volume"]["value"] == 108.3  # 25 cases a week
    assert (plan["hours_per_month"], plan["cost_per_month"], plan["evidence"]) == (
        43.1, 2068.8, "measured")  # fmt: skip
    assert (plan["disposition"], plan["chosen"], plan["hours_released"]) == (
        "ai_assisted", False, 21.6)  # fmt: skip
    report = {s["label"]: s for s in body["steps"]}["Load and return LIR"]
    assert report["cost_per_month"] is None and report["missing"] == ["No hourly cost for Ramp."]
    totals = body["totals"]
    assert (totals["steps_counted"], totals["steps_without_cost"], totals["evidence"]) == (
        5, 1, "measured")  # fmt: skip
    assert totals["hours_per_month"] == round(sum(s["hours_per_month"] or 0
                                                  for s in body["steps"]), 1)  # fmt: skip
    automate = next(s for s in body["scenarios"] if s["disposition"] == "automate_rules")
    assert (automate["steps"], automate["hours_released"]) == (2, 13.1)


def test_eric_s_choice_drives_the_scenario(measured: Drafted) -> None:
    measured.client.put(f"/api/elements/{measured.ids['Draft load plan']}/disposition",
                        json={"disposition": "keep_human", "note": ""})  # fmt: skip
    plan = steps(measured)["Draft load plan"]
    assert (plan["disposition"], plan["chosen"], plan["hours_released"]) == (
        "keep_human",
        True,
        0.0,
    )


def test_override_only_where_nothing_is_measured_or_stated(measured: Drafted) -> None:
    url = f"/api/elements/{measured.ids['Resolve or offload']}/value-override"
    missing_note = measured.client.put(url, json={"volume_month": 30})
    assert missing_note.status_code == 422
    assert missing_note.json()["error"]["message"] == "Say where the figure comes from."
    row = measured.client.put(url, json={"volume_month": 30, "note": "Shift log, March"}).json()
    assert row["volume"] == {"value": 30.0, "label": "assumed",
                             "source": "Your figure: Shift log, March"}  # fmt: skip
    assert (row["hours_per_month"], row["evidence"]) == (20.0, "mixed")  # 40 min stated, 30 a month
    [entry] = [a for a in measured.audit() if a["action"] == "Set value override"]
    assert entry["after"] == {"time_min": None, "volume_month": 30.0, "note": "Shift log, March"}
    # A measured time wins over Eric's own (§3.14's order of preference).
    plan_url = f"/api/elements/{measured.ids['Draft load plan']}/value-override"
    plan = measured.client.put(plan_url, json={"time_min": 5, "note": "My guess"}).json()
    assert plan["time"]["label"] == "measured"
    for bad, field in (({"time_min": 0, "note": "x"}, "time_min"),
                       ({"volume_month": 2_000_000, "note": "x"}, "volume_month"),
                       ({"volume_month": 1, "note": "x" * 301}, "note")):  # fmt: skip
        response = measured.client.put(url, json=bad)
        assert response.status_code == 422 and response.json()["error"]["details"]["field"] == field
    cleared = measured.client.put(url, json={"time_min": None, "volume_month": None}).json()
    assert cleared["volume"] is None


def test_views_published_and_unknown(measured: Drafted) -> None:
    documented = {s["label"] for s in value(measured, "documented")["steps"]}
    assert "Approve load plan" in documented and "Approve load plan" not in steps(measured)
    url = f"/api/versions/{measured.version_id}/value"
    assert measured.client.get(url, params={"view": "both"}).status_code == 422
    assert measured.client.get("/api/versions/nope/value").status_code == 404
    assert measured.client.put("/api/elements/nope/value-override",
                               json={"time_min": None}).status_code == 404  # fmt: skip
    confirm_all(measured)
    assert publish(measured).status_code == 200
    assert value(measured)["totals"]["steps_counted"] == 5  # a published version reads the same
    step = measured.ids["Resolve or offload"]
    override = measured.client.put(f"/api/elements/{step}/value-override",
                                   json={"volume_month": 3, "note": "x"})  # fmt: skip
    assert override.status_code == 409
