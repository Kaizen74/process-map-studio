"""Variants through the map, the step summary and Add as step from hidden work (API_CONTRACT.md →
system-traces, system-variants, POST /versions/{vid}/elements; PRD §5.6, §3.13.4; criterion 89;
R8): fixture A.11 imported into the drafted Appendix A sample and matched by Eric."""

from __future__ import annotations

from typing import Any

import pytest

from tests.unit.test_log_alignment_api import EXPECTED, import_log
from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_review_edit import role
from tests.uploads import wait_for_jobs

__all__ = ["drafted"]

HIDDEN = "Manual weight override"


def variants(d: Drafted) -> dict[str, Any]:
    response = d.client.get(f"/api/versions/{d.version_id}/system-variants")
    assert response.status_code == 200, response.text
    return dict(response.json())


def decide(d: Drafted, lid: str, rows: list[dict[str, Any]]) -> None:
    response = d.client.put(f"/api/event-logs/{lid}/alignment", json={"rows": rows})
    assert response.status_code == 200, response.text


@pytest.fixture()
def matched(drafted: Drafted) -> tuple[Drafted, str]:
    lid = import_log(drafted.client, drafted.engagement_id)
    rows = [{"activity": a, "element_id": drafted.ids[s], "status": "confirmed"}
            for a, s in EXPECTED.items()]  # fmt: skip
    rows.append({"activity": HIDDEN, "element_id": None, "status": "hidden_work"})
    decide(drafted, lid, rows)
    return drafted, lid


def test_each_trace_item_carries_the_step_summary(matched: tuple[Drafted, str]) -> None:
    d, _ = matched
    traces = d.client.get(f"/api/versions/{d.version_id}/system-traces").json()
    items = {t["label"]: t for t in traces}
    plan = items["Draft load plan"]
    assert (plan["main_activity"], plan["cases_per_month"]) == ("Plan created", 108.3)  # 25/week
    assert plan["wait_before"] is None  # the first activity of every case waits for nothing
    assert (plan["variants"], plan["variant_share"]) == (3, 0.98)
    report = items["Load and return LIR"]
    assert report["main_activity"] == "Loading report received"
    assert report["wait_before"]["median_min"] == 39.1 and report["basis"] == "wait"
    assert 11 <= report["work"]["median_min"] <= 17  # A.11: 15 minutes stated, about 13 measured


def test_variants_read_through_the_matches_and_compared_with_each_view(
    matched: tuple[Drafted, str],
) -> None:
    d, _ = matched
    [log] = variants(d)["logs"]
    assert (log["log_name"], log["cases"], log["too_few"]) == ("DCS extract", 200, 1)
    first, second, third = log["variants"]
    assert (first["rank"], first["cases"], first["share"]) == (1, 141, 0.705)
    assert [p["label"] for p in first["path"]] == ["Draft load plan", "Special loads OK?",
        "Load and return LIR", "Deviation in limits?", "Issue load sheet"]  # fmt: skip
    assert first["views"] == {"done": {"fits": True, "notes": []},
                              "documented": {"fits": True, "notes": []}}  # fmt: skip
    # The plan revised after the special-load check: the documents have no way back.
    assert [p["activity"] for p in second["path"]][2] == "Plan revised"
    assert second["views"]["done"]["fits"] is True
    no_way = "The As documented view has no way from Special loads OK? to Draft load plan."
    assert second["views"]["documented"] == {"fits": False, "notes": [no_way]}
    # The override: hidden work, in both views.
    override = next(p for p in third["path"] if p["activity"] == HIDDEN)
    assert (override["status"], override["element_id"]) == ("hidden_work", None)
    assert third["views"]["done"]["notes"] == [f"{HIDDEN} is hidden work: no step on the map."]
    assert second["cumulative_share"] == 0.885 and third["cumulative_share"] == 0.98


def test_the_hidden_work_list_says_where_the_work_happens(matched: tuple[Drafted, str]) -> None:
    d, _ = matched
    [item] = variants(d)["logs"][0]["hidden_work"]
    assert (item["activity"], item["cases"], item["share"]) == (HIDDEN, 23, 0.115)
    assert item["role_id"] == role(d, "Load controller")
    assert (item["after_label"], item["after_element_id"]) == (
        "Deviation in limits?", d.ids["Deviation in limits?"])  # fmt: skip
    assert (item["before_label"], item["before_element_id"]) == (
        "Issue load sheet", d.ids["Issue load sheet"])  # fmt: skip
    assert variants(d)["too_few_steps"] == []


def test_undecided_activities_are_named_and_nothing_is_matched(drafted: Drafted) -> None:
    import_log(drafted.client, drafted.engagement_id)  # proposals only
    [log] = variants(drafted)["logs"]
    assert log["hidden_work"] == []
    for variant in log["variants"]:
        assert {p["status"] for p in variant["path"]} == {"not_matched"}
        assert variant["views"]["done"]["fits"] is False
        assert variant["views"]["done"]["notes"][-1] == (
            "No activity of this variant is matched to a step yet.")  # fmt: skip


def test_a_step_matched_in_fewer_than_5_cases_has_too_few_cases(drafted: Drafted) -> None:
    rows = ["case_id,activity,timestamp,role"]
    for n in range(6):
        rows.append(f"C{n},Plan created,2026-03-02 08:00,Load controller")
        if n < 3:  # the special-load check recorded in 3 cases only
            rows.append(f"C{n},Special load checked,2026-03-02 08:30,Load controller")
    client = drafted.client
    log = client.post(f"/api/engagements/{drafted.engagement_id}/event-logs",
                      files={"file": ("x.csv", "\n".join(rows).encode(), "text/csv")},
                      data={"name": "Small"}).json()  # fmt: skip
    client.put(f"/api/event-logs/{log['id']}/column-map", json={"columns": log["column_map"]})
    approval = {"approved_by_role": "Head of operations", "confirm_approval": True}
    assert client.post(f"/api/event-logs/{log['id']}/import", json=approval).status_code == 202
    wait_for_jobs(client)
    decide(drafted, log["id"], [
        {"activity": "Plan created", "element_id": drafted.ids["Draft load plan"],
         "status": "confirmed"},
        {"activity": "Special load checked", "element_id": drafted.ids["Special loads OK?"],
         "status": "confirmed"},
    ])  # fmt: skip
    assert variants(drafted)["too_few_steps"] == [drafted.ids["Special loads OK?"]]


def add_from_hidden_work(d: Drafted, lid: str, **fields: Any) -> Any:
    body = {"kind": "activity", "label": HIDDEN, "provenance": "O",
            "lane_role_id": role(d, "Load controller"),
            "after_element_id": d.ids["Deviation in limits?"],
            "system_activity": {"log_id": lid, "activity": HIDDEN}} | fields  # fmt: skip
    return d.client.post(f"/api/versions/{d.version_id}/elements", json=body)


def test_add_as_step_from_hidden_work(matched: tuple[Drafted, str]) -> None:
    d, lid = matched
    response = add_from_hidden_work(d, lid)
    assert response.status_code == 201, response.text
    step = response.json()
    assert (step["provenance"], step["review_status"]) == ("O", "added")
    assert [e for e in step["evidence"] if e["segment_id"]] == []  # its evidence is the trace
    # The hidden-work decision became a confirmed match to the new step.
    table = d.client.get(f"/api/event-logs/{lid}/alignment").json()
    row = next(r for r in table["rows"] if r["activity"] == HIDDEN)
    assert (row["element_id"], row["status"], row["confirmed"]) == (step["id"], "confirmed", True)
    traces = d.client.get(f"/api/versions/{d.version_id}/system-traces").json()
    [trace] = [t for t in traces if t["element_id"] == step["id"]]
    assert (trace["cases"], trace["stance"]) == (23, "supports")
    # Lint L2 and quality Q2 accept the system trace for this observed step.
    lint = d.client.get(f"/api/versions/{d.version_id}/lint").json()
    assert not [f for f in lint["failures"] if f["element_id"] == step["id"]]
    card = d.client.get(f"/api/versions/{d.version_id}/quality-card").json()
    q2 = next(c for c in card["checks"] if c["id"] == "Q2")
    assert HIDDEN not in q2["detail"]
    # The hidden-work list no longer lists it.
    assert variants(d)["logs"][0]["hidden_work"] == []
    [audit] = [a for a in d.audit() if a["action"] == "Added step"]
    assert (audit["after"]["system_activity"], audit["after"]["log_id"]) == (HIDDEN, lid)


def test_without_the_trace_an_observed_step_still_needs_a_passage(
    matched: tuple[Drafted, str],
) -> None:
    d, lid = matched
    step = add_from_hidden_work(d, lid).json()
    # Eric undoes the match: the step has nothing behind it any more.
    decide(d, lid, [{"activity": HIDDEN, "element_id": None, "status": "hidden_work"}])
    card = d.client.get(f"/api/versions/{d.version_id}/quality-card").json()
    q2 = next(c for c in card["checks"] if c["id"] == "Q2")
    assert q2["status"] == "fail" and HIDDEN in q2["detail"]
    assert step["id"]


def test_add_from_hidden_work_is_refused_for_other_activities(
    matched: tuple[Drafted, str],
) -> None:
    d, lid = matched
    matched_activity = {"log_id": lid, "activity": "Plan created"}
    other = add_from_hidden_work(d, lid, system_activity=matched_activity)
    assert other.status_code == 422
    assert other.json()["error"]["details"]["field"] == "system_activity"
    assert "confirmed as hidden work" in other.json()["error"]["message"]
    elsewhere = add_from_hidden_work(d, lid, system_activity={"log_id": "nope", "activity": HIDDEN})
    assert elsewhere.status_code == 422
    plain = add_from_hidden_work(d, lid, system_activity=None)
    assert plain.status_code == 422
    assert plain.json()["error"]["details"]["field"] == "segment_ids"


def test_add_from_hidden_work_needs_5_cases(drafted: Drafted) -> None:
    rows = ["case_id,activity,timestamp,role"]
    for n in range(6):
        rows.append(f"C{n},Plan created,2026-03-02 08:00,Load controller")
    rows += [f"C{n},Phone call,2026-03-02 08:10,Load controller" for n in range(3)]
    client = drafted.client
    log = client.post(f"/api/engagements/{drafted.engagement_id}/event-logs",
                      files={"file": ("x.csv", "\n".join(rows).encode(), "text/csv")},
                      data={"name": "Small"}).json()  # fmt: skip
    client.put(f"/api/event-logs/{log['id']}/column-map", json={"columns": log["column_map"]})
    approval = {"approved_by_role": "Head of operations", "confirm_approval": True}
    client.post(f"/api/event-logs/{log['id']}/import", json=approval)
    wait_for_jobs(client)
    decide(drafted, log["id"], [{"activity": "Phone call", "element_id": None,
                                 "status": "hidden_work"}])  # fmt: skip
    response = add_from_hidden_work(
        drafted,
        log["id"],
        label="Phone call",
        system_activity={"log_id": log["id"], "activity": "Phone call"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "That activity is recorded in fewer than 5 cases."


def test_unknown_versions_are_404(drafted: Drafted) -> None:
    assert drafted.client.get("/api/versions/nope/system-variants").status_code == 404
