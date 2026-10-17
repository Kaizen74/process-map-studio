"""R5b: what Eric's confirmed alignment does to a map (PRD §3.13.4, §3.12.7; criterion 87)."""

from __future__ import annotations

from app.services import system_trace as tracing
from app.services.system_trace import TraceEdge, TraceLog, TraceStep

STEPS = [
    TraceStep("plan", "Draft load plan", "corroborated"),
    TraceStep("check", "Special loads OK?", "corroborated"),
    TraceStep("report", "Read report at aircraft", "practiced_only"),
    TraceStep("approve", "Approve load plan", "documented_only"),
    TraceStep("sheet", "Issue load sheet", "documented_only", ("threshold",)),
]
EDGES = [TraceEdge("e1", "plan", "check"), TraceEdge("e2", "check", "report"),
         TraceEdge("e3", "report", "sheet"), TraceEdge("e4", "plan", "approve")]  # fmt: skip


def log(matched: dict[str, str], cases: dict[str, int],
        moves: list[tuple[str, str, int]]) -> TraceLog:  # fmt: skip
    return TraceLog("L1", matched, cases, moves)


def test_order_the_system_records_becomes_the_lines_basis() -> None:
    trace = log({"Created": "plan", "Revised": "plan", "Checked": "check"},
                {"Created": 200, "Revised": 40, "Checked": 200},
                [("Created", "Checked", 160), ("Revised", "Checked", 40),
                 ("Created", "Revised", 40)])  # fmt: skip
    out = tracing.overlay(STEPS, EDGES, [trace])
    assert out.edge_basis == {"e1": "system_trace"}
    assert tracing.step_moves(trace) == {("plan", "check"): 200}  # rework within a step left out
    assert out.states == {} and out.divergences == {}  # both were corroborated already
    assert out.stances == {("L1", "plan"): "supports", ("L1", "check"): "supports"}


def test_a_reversed_order_contradicts_the_later_step() -> None:
    trace = log({"Created": "plan", "Checked": "check"}, {"Created": 6, "Checked": 6},
                [("Checked", "Created", 6), ("Created", "Checked", 1)])  # fmt: skip
    out = tracing.overlay(STEPS, EDGES, [trace])
    assert out.edge_basis == {}
    assert out.states == {"check": "trace_contradicted"}
    assert out.divergences == {"check": ["sequence"]}
    assert out.stances[("L1", "check")] == "contradicts"
    assert out.notes[("L1", "check")] == (
        "The system records Special loads OK? before Draft load plan in 6 cases."
    )


def test_fewer_than_five_cases_change_nothing() -> None:
    trace = log({"Created": "plan", "Checked": "check"}, {"Created": 4, "Checked": 4},
                [("Checked", "Created", 4)])  # fmt: skip
    out = tracing.overlay(STEPS, EDGES, [trace])
    assert (out.edge_basis, out.states, out.stances) == ({}, {}, {})
    small = log({"Created": "plan", "Checked": "check"}, {"Created": 9, "Checked": 9},
                [("Created", "Checked", 4)])  # fmt: skip
    assert tracing.overlay(STEPS, EDGES, [small]).edge_basis == {}  # the move needs 5 cases too


def test_a_trace_corroborates_a_one_sided_account() -> None:
    trace = log({"Read": "report", "Issued": "sheet"}, {"Read": 23, "Issued": 23}, [])
    out = tracing.overlay(STEPS, EDGES, [trace])
    assert out.states == {"report": "corroborated", "sheet": "corroborated"}
    assert out.divergences == {}  # a divergence already there stays as it was


def test_silence_is_never_contradiction() -> None:
    """Approve load plan has no system record: the system is silent, nothing changes."""
    trace = log({"Created": "plan"}, {"Created": 200}, [])
    out = tracing.overlay(STEPS, EDGES, [trace])
    assert "approve" not in out.states and ("L1", "approve") not in out.stances
    assert out.states == {}


def test_contradiction_outranks_support_across_logs() -> None:
    agree = TraceLog("L1", {"Created": "plan", "Read": "report"}, {"Created": 50, "Read": 50}, [])
    reverse = TraceLog("L2", {"Checked": "check", "Read": "report"}, {"Checked": 9, "Read": 9},
                       [("Read", "Checked", 9)])  # fmt: skip
    out = tracing.overlay(STEPS, EDGES, [agree, reverse])
    assert out.stances[("L1", "report")] == "supports"
    assert out.stances[("L2", "report")] == "contradicts"  # L2 records the report before the check
    assert out.states == {"report": "trace_contradicted"}  # not corroborated by L1's support
    assert out.divergences == {"report": ["sequence"]}


def test_a_trace_item_gives_volume_per_week_and_rework() -> None:
    item = tracing.trace_item(
        STEPS[0], "el-1", {"id": "L1", "name": "DCS extract", "system": "DCS", "weeks": 8},
        {"cases": 200, "events": 240, "rework_cases": 40}, [], "supports", "",
    )  # fmt: skip
    assert (item["cases_per_week"], item["rework_share"]) == (25.0, 0.2)
    assert item["log_name"] == "DCS extract"
