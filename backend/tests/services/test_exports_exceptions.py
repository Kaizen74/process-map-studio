"""Exceptions, rework and workarounds in the Master Process Map and the HTML map (X6,
2026-10-06, Eric's decision): the same lines in both, facts and the SME's own words only."""

from __future__ import annotations

from app.domain.exports import ExportInput
from app.domain.graph import CycleTime, Graph, GraphProcess, GraphVersion
from app.domain.sensemaking import ExceptionEdgeInput, ExceptionStepInput
from app.services import exceptions, exports
from tests.services.test_exceptions import ASK, SAMPLE_EDGES, SAMPLE_STEPS


def bundle(with_report: bool = True) -> ExportInput:
    graph = Graph(
        version=GraphVersion(id="v", label="v0.1", state="draft"),
        process=GraphProcess(name="Load control", trigger="", end_point="", kpi="",
                             cycle_time=CycleTime(elapsed_min=0, work_min=0, incomplete_steps=0)),
        roles=[], phases=[], elements=[], edges=[],
    )  # fmt: skip
    report = exceptions.analyse(SAMPLE_STEPS, SAMPLE_EDGES, "done", ASK) if with_report else None
    return ExportInput(graph=graph, sources=[], published_at="", validated_by="",
                       open_questions=[], exceptions=report)  # fmt: skip


def test_the_lines_give_the_facts_routes_loops_workarounds_and_what_to_ask() -> None:
    lines = exports.exception_lines(bundle())
    assert lines[0] == (
        "- 3 of 9 steps (33%) are off the usual route: 2 on exception routes, 1 variation. "
        "2 rework loops; 1 workaround. The exception routes add 4 hand-overs."
    )
    assert lines[2] == (
        "- Variation: Busy? → on a busy wave: Read at aircraft (Load controller); then it rejoins "
        "the usual route at In limits?; 0 extra hand-overs; how often: not stated yet; reason "
        "given: “otherwise we'd miss the slot”."
    )
    assert "- Rework loop: Resolve goes back to Plan (Re-plan)." in lines
    assert sum(1 for x in lines if x.startswith("- Still to ask [M5.s2]")) == 3
    assert all(x.startswith("- ") for x in lines)  # the HTML map lists every line


def test_a_map_from_before_the_two_views_says_so() -> None:
    assert exports.exception_lines(bundle(with_report=False)) == [
        "This map was drafted before the two views; exceptions are not worked out."
    ]


def test_the_summary_for_a_quiet_map_and_an_empty_one() -> None:
    def step(key: str, kind: str = "activity") -> ExceptionStepInput:
        return ExceptionStepInput(element_id=key, label=key, kind=kind)

    def line(a: str, b: str) -> ExceptionEdgeInput:
        return ExceptionEdgeInput(from_id=a, to_id=b, kind="sequence")

    steps = [step("Start", "start"), step("Do"), step("Check"), step("End", "end")]
    lines = [line("Start", "Do"), line("Do", "Check"), line("Check", "End")]
    report = exceptions.analyse(steps, lines, "done", ASK)
    assert exports.exception_summary(report.summary) == (
        "All 2 steps are on the usual route; no exception routes, rework loops or workarounds."
    )
    one = report.summary.model_copy(update={"steps": 1, "usual_steps": 1})
    assert exports.exception_summary(one) == (
        "The only step is on the usual route; no exception routes, rework loops or workarounds."
    )
    empty = report.summary.model_copy(update={"steps": 0})
    assert exports.exception_summary(empty) == "No steps in this view yet."
