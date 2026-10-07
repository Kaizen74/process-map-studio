"""System trace on the map (API_CONTRACT.md; PRD §3.13.4, §3.12.7; criterion 87; R5b): fixture
A.11 imported into the drafted Appendix A sample and matched by Eric."""

from __future__ import annotations

from typing import Any

import pytest

from tests.unit.test_log_alignment_api import EXPECTED, import_log
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted
from tests.uploads import wait_for_jobs

__all__ = ["drafted"]

TRACED_LINES = {
    ("Draft load plan", "Special loads OK?"),
    ("Special loads OK?", "Load and return LIR"),
    ("Draft load plan", "Load and return LIR"),
    ("Load and return LIR", "Deviation in limits?"),
    ("Deviation in limits?", "Issue load sheet"),
}


def graph(d: Drafted, version_id: str | None = None) -> dict[str, Any]:
    response = d.client.get(f"/api/versions/{version_id or d.version_id}/graph")
    assert response.status_code == 200, response.text
    return dict(response.json())


def lines(g: dict[str, Any]) -> dict[tuple[str, str], str]:
    labels = {e["id"]: e["label"] for e in g["elements"]}
    return {(labels[x["from"]], labels[x["to"]]): x["sequence_basis"] for x in g["edges"]}


def states(g: dict[str, Any]) -> dict[str, tuple[str, list[str]]]:
    return {e["label"]: (e["source_state"], e["divergence_types"]) for e in g["elements"]}


def traces(d: Drafted, version_id: str | None = None) -> list[dict[str, Any]]:
    response = d.client.get(f"/api/versions/{version_id or d.version_id}/system-traces")
    assert response.status_code == 200, response.text
    return list(response.json())


def confirm(d: Drafted, lid: str, matches: dict[str, str]) -> None:
    rows = [{"activity": a, "element_id": d.ids[s], "status": "confirmed"}
            for a, s in matches.items()]  # fmt: skip
    response = d.client.put(f"/api/event-logs/{lid}/alignment", json={"rows": rows})
    assert response.status_code == 200, response.text


@pytest.fixture()
def traced(drafted: Drafted) -> tuple[Drafted, str, dict[str, Any]]:
    before = graph(drafted)
    lid = import_log(drafted.client, drafted.engagement_id)
    assert graph(drafted) == before and traces(drafted) == []  # proposals change nothing
    confirm(drafted, lid, EXPECTED)
    return drafted, lid, before


def test_confirmed_matches_give_system_trace_lines_and_evidence(
    traced: tuple[Drafted, str, dict[str, Any]],
) -> None:
    d, _, before = traced
    after = graph(d)
    changed = {k for k, v in lines(after).items() if v != lines(before)[k]}
    assert changed == TRACED_LINES
    assert all(lines(after)[k] == "system_trace" for k in TRACED_LINES)
    assert states(after) == states(before)  # A.11 agrees with the map: no state changes
    found = {t["label"]: t for t in traces(d)}
    assert list(found) == ["Draft load plan", "Special loads OK?", "Load and return LIR",
                           "Deviation in limits?", "Issue load sheet"]  # map order  # fmt: skip
    plan = found["Draft load plan"]
    assert (plan["stance"], plan["cases"], plan["events"]) == ("supports", 200, 240)
    assert (plan["rework_cases"], plan["rework_share"]) == (40, 0.2)  # Plan revised: rework
    assert [a["activity"] for a in plan["activities"]] == ["Plan created", "Plan revised"]
    report = found["Load and return LIR"]
    assert report["cases_per_week"] == 25.0 and report["log_name"] == "DCS extract"
    assert 11 <= report["activities"][0]["work"]["median_min"] <= 17
    assert all(t["note"] == "" for t in found.values())
    assert "Approve load plan" not in found  # no system record: silent, never contradicting


def test_a_trace_corroborates_a_step_only_one_account_described(
    traced: tuple[Drafted, str, dict[str, Any]],
) -> None:
    d, lid, before = traced
    assert states(before)["Approve deviation"][0] == "practiced_only"
    confirm(d, lid, {"Manual weight override": "Approve deviation"})  # Eric's choice (23 cases)
    assert states(graph(d))["Approve deviation"] == ("corroborated", [])
    [item] = [t for t in traces(d) if t["label"] == "Approve deviation"]
    assert (item["cases"], item["stance"]) == (23, "supports")


def test_a_reversed_order_contradicts_the_step(drafted: Drafted) -> None:
    rows = ["case_id,activity,timestamp,role"]
    for n in range(6):  # the special-load check recorded before the plan, in 6 cases
        rows += [f"C{n},Special load checked,2026-03-02 08:00,Load controller",
                 f"C{n},Plan created,2026-03-02 08:30,Load controller"]  # fmt: skip
    client = drafted.client
    log = client.post(f"/api/engagements/{drafted.engagement_id}/event-logs",
                      files={"file": ("x.csv", "\n".join(rows).encode(), "text/csv")},
                      data={"name": "Reversed"}).json()  # fmt: skip
    client.put(f"/api/event-logs/{log['id']}/column-map", json={"columns": log["column_map"]})
    approval = {"approved_by_role": "Head of operations", "confirm_approval": True}
    assert client.post(f"/api/event-logs/{log['id']}/import", json=approval).status_code == 202
    wait_for_jobs(client)
    confirm(drafted, log["id"], {"Plan created": "Draft load plan",
                                 "Special load checked": "Special loads OK?"})  # fmt: skip
    after = graph(drafted)
    assert states(after)["Special loads OK?"] == ("trace_contradicted", ["sequence"])
    assert lines(after)[("Draft load plan", "Special loads OK?")] != "system_trace"
    [item] = [t for t in traces(drafted) if t["label"] == "Special loads OK?"]
    assert item["stance"] == "contradicts"
    assert item["note"] == "The system records Special loads OK? before Draft load plan in 6 cases."
    detail = client.get(f"/api/elements/{drafted.ids['Special loads OK?']}").json()
    assert detail["source_state"] == "trace_contradicted"  # the panel agrees with the map


def test_publishing_freezes_the_trace(traced: tuple[Drafted, str, dict[str, Any]]) -> None:
    d, lid, _ = traced
    confirm_all(d)
    shown = graph(d)
    published = publish(d)
    assert published.status_code == 200, published.text
    frozen_graph, frozen_traces = graph(d), traces(d)
    assert lines(frozen_graph) == lines(shown) and states(frozen_graph) == states(shown)
    assert len(frozen_traces) == 5
    # Changing the alignment afterwards leaves the published version as it was.
    d.client.put(f"/api/event-logs/{lid}/alignment", json={"rows": [
        {"activity": a, "element_id": None, "status": "hidden_work"} for a in EXPECTED
    ]})  # fmt: skip
    assert graph(d) == frozen_graph and traces(d) == frozen_traces


def test_unknown_versions_are_404(drafted: Drafted) -> None:
    assert drafted.client.get("/api/versions/nope/system-traces").status_code == 404
