"""Lint rules L1-L12 (PRD §3.7): a clean map passes, and one crafted fault per rule fails it."""

from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise

import pytest

from app.domain.graph import (
    CycleTime,
    Graph,
    GraphAiFlag,
    GraphDecision,
    GraphEdge,
    GraphElement,
    GraphEvidence,
    GraphHandoff,
    GraphProcess,
    GraphRaci,
    GraphRole,
    GraphTime,
    GraphVersion,
)
from app.services.lint import run_lint, run_view_checks
from app.services.views import view_graph

LC, LEAD, CAPTAIN = "lc", "lead", "captain"


def element(key: str, kind: str, **extra: object) -> GraphElement:
    evidence = (
        [GraphEvidence(segment_id=f"seg-{key}", source_id="s1", source_kind="sop",
                       stance="supports", anchor="§1", verified=True)]
        if kind in {"activity", "decision", "approval"}
        else []
    )  # fmt: skip
    fields: dict[str, object] = {
        "id": key, "stable_key": key, "kind": kind, "label": key.capitalize(),
        "lane_role_id": LC, "phase_id": None,
        "time": GraphTime(work_min=10, wait_min=None, text="~10 min"),
        "complexity": None, "kpi": "",
        "decision": GraphDecision(mechanism="none", decider_role_id=None, rule_or_threshold="",
                                  escalation=""),
        "handoff": GraphHandoff(in_="", out=""), "raci": [], "provenance": "O",
        "r_reference": "", "source_state": "corroborated", "divergence_types": [],
        "constraints": [], "k_risk": "", "ai_flag": None, "evidence": evidence,
        "confidence": 0.8, "confidence_breakdown": [], "needs_check": False,
        "review_status": "draft",
    }  # fmt: skip
    fields.update(extra)
    return GraphElement.model_validate(fields)


def raci(role: str, letter: str, contested: bool = False) -> GraphRaci:
    return GraphRaci(role_id=role, letter=letter, contested=contested)


def edge(a: str, b: str, kind: str = "sequence", label: str = "") -> GraphEdge:
    return GraphEdge(id=f"{a}>{b}", from_=a, to=b, kind=kind, label=label)


def flag(**extra: str) -> GraphAiFlag:
    values = {"component": "action", "input": "Report", "output": "Keyed data",
              "handoff": "Load controller", "basis": "rule_based_automate_candidate"}  # fmt: skip
    values.update(extra)
    return GraphAiFlag.model_validate(values)


def clean() -> Graph:
    """start → plan → approve (approve → check; reject → plan) → check? (yes → issue; no → plan)
    → issue → end. Three AI flags, every step with R/A, times, evidence."""
    decide = GraphDecision(mechanism="rule_based", decider_role_id=LC, rule_or_threshold="List",
                           escalation="")  # fmt: skip
    elements = [
        element("start", "start", time=GraphTime(work_min=None, wait_min=None, text="")),
        element("plan", "activity", raci=[raci(LC, "R"), raci(LC, "A")], ai_flag=flag()),
        element("approve", "approval", lane_role_id=LEAD, raci=[raci(LEAD, "A")],
                decision=GraphDecision(mechanism="judgment", decider_role_id=LEAD,
                                       rule_or_threshold="", escalation="")),
        element("check", "decision", decision=decide, raci=[raci(LC, "A")],
                ai_flag=flag(component="reasoning")),
        element("issue", "activity", raci=[raci(LC, "R"), raci(LEAD, "A")],
                ai_flag=flag(component="communication")),
        element("end", "end", time=GraphTime(work_min=None, wait_min=None, text="")),
    ]  # fmt: skip
    edges = [
        edge("start", "plan"),
        edge("plan", "approve"),
        edge("approve", "check", "approve", "Approve"),
        edge("approve", "plan", "reject", "Rework"),
        edge("check", "issue", "yes", "Yes"),
        edge("check", "plan", "no", "No"),
        edge("issue", "end"),
    ]
    return Graph(
        version=GraphVersion(id="v", label="v0.1", state="draft"),
        process=GraphProcess(name="Load control", trigger="T", end_point="E", kpi="",
                             cycle_time=CycleTime(elapsed_min=0, work_min=0, incomplete_steps=0)),
        roles=[GraphRole(id=r, name=r.capitalize(), is_system=False, lane_order=None)
               for r in (LC, LEAD, CAPTAIN)],
        phases=[], elements=elements, edges=edges,
    )  # fmt: skip


def replace(graph: Graph, key: str, **fields: object) -> Graph:
    graph.elements = [e.model_copy(update=fields) if e.id == key else e for e in graph.elements]
    return graph


def test_the_clean_map_passes_every_rule() -> None:
    report = run_lint(clean())
    assert report.failures == []
    assert report.warnings == []


Fault = Callable[[Graph], Graph]


def no_provenance(g: Graph) -> Graph:
    return replace(g, "plan", provenance="")


def no_verified_evidence(g: Graph) -> Graph:
    [ev] = next(e for e in g.elements if e.id == "plan").evidence
    return replace(g, "plan", evidence=[ev.model_copy(update={"verified": False})])


def only_silent_evidence(g: Graph) -> Graph:
    silent = GraphEvidence(segment_id=None, source_id="s1", source_kind="sop", stance="silent",
                           anchor="", verified=False)  # fmt: skip
    return replace(g, "plan", evidence=[silent])


def r_without_reference(g: Graph) -> Graph:
    return replace(g, "issue", provenance="R", evidence=[])


def decision_with_one_labelled_exit(g: Graph) -> Graph:
    g.edges = [e.model_copy(update={"label": ""}) if e.id == "check>plan" else e for e in g.edges]
    return g


def approval_without_reject(g: Graph) -> Graph:
    g.edges = [e for e in g.edges if e.id != "approve>plan"]
    return g


def activity_in_wrong_lane(g: Graph) -> Graph:
    return replace(g, "plan", lane_role_id=LEAD)


def activity_with_two_responsible(g: Graph) -> Graph:
    return replace(g, "plan", raci=[raci(LC, "R"), raci(LEAD, "R"), raci(LC, "A")])


def approval_not_in_accountable_lane(g: Graph) -> Graph:
    return replace(g, "approve", lane_role_id=LC)


def contested_approval_without_ownership(g: Graph) -> Graph:
    return replace(g, "approve", raci=[raci(LEAD, "A", True), raci(CAPTAIN, "A", True)])


def decision_not_in_decider_lane(g: Graph) -> Graph:
    return replace(g, "check", lane_role_id=LEAD)


def orphan_with_no_way_in_or_out(g: Graph) -> Graph:
    g.elements.append(element("orphan", "activity", raci=[raci(LC, "R"), raci(LC, "A")]))
    return g


def dead_end(g: Graph) -> Graph:
    g.edges = [e for e in g.edges if e.id != "issue>end"]
    return g


def two_starts(g: Graph) -> Graph:
    g.elements.append(element("start2", "start"))
    g.edges.append(edge("start2", "plan"))
    return g


def rejecting_the_only_link(g: Graph) -> Graph:
    """Rejecting a step orphans the steps after it (PRD §5.8: Q4 turns red)."""
    return replace(g, "issue", review_status="rejected")


def incomplete_ai_flag(g: Graph) -> Graph:
    return replace(g, "plan", ai_flag=flag(handoff=" "))


def automation_on_a_judgment_step(g: Graph) -> Graph:
    return replace(g, "approve", ai_flag=flag())


def two_accountable(g: Graph) -> Graph:
    return replace(g, "issue", raci=[raci(LC, "R"), raci(LC, "A"), raci(LEAD, "A")])


def no_accountable(g: Graph) -> Graph:
    return replace(g, "issue", raci=[raci(LC, "R")])


FAULTS: list[tuple[str, Fault]] = [
    ("L1", no_provenance),
    ("L2", no_verified_evidence),
    ("L2", only_silent_evidence),
    ("L3", r_without_reference),
    ("L4", decision_with_one_labelled_exit),
    ("L5", approval_without_reject),
    ("L6", activity_in_wrong_lane),
    ("L6", activity_with_two_responsible),
    ("L7", approval_not_in_accountable_lane),
    ("L7", contested_approval_without_ownership),
    ("L8", decision_not_in_decider_lane),
    ("L9", orphan_with_no_way_in_or_out),
    ("L9", dead_end),
    ("L9", two_starts),
    ("L9", rejecting_the_only_link),
    ("L10", incomplete_ai_flag),
    ("L10", automation_on_a_judgment_step),
    ("L11", two_accountable),
    ("L11", no_accountable),
]


@pytest.mark.parametrize(("rule", "fault"), FAULTS, ids=[f"{r}-{f.__name__}" for r, f in FAULTS])
def test_each_fault_fails_its_rule(rule: str, fault: Fault) -> None:
    report = run_lint(fault(clean()))
    assert rule in {f.rule for f in report.failures}, report.failures
    assert all(f.message.endswith(".") for f in report.failures)


def test_contested_approval_in_a_competing_lane_with_ownership_passes() -> None:
    g = replace(
        clean(),
        "approve",
        raci=[raci(LEAD, "A", True), raci(CAPTAIN, "A", True)],
        divergence_types=["ownership"],
    )
    assert run_lint(g).failures == []


def test_start_and_end_need_no_evidence_or_roles() -> None:
    report = run_lint(clean())
    assert not any(f.element_id in {"start", "end"} for f in report.failures)


def test_messages_name_the_step_and_its_roles() -> None:
    report = run_lint(activity_in_wrong_lane(clean()))
    [issue] = [f for f in report.failures if f.rule == "L6"]
    assert issue.element_id == "plan"
    assert issue.message == 'Activity "Plan" sits in the Lead lane but its Responsible role is Lc.'


# --- Warnings (L12) ---------------------------------------------------------------------------


def test_large_map_warns_but_does_not_fail() -> None:
    g = clean()
    extra = [element(f"s{i}", "activity", raci=[raci(LC, "R"), raci(LC, "A")]) for i in range(25)]
    chain = ["plan", *[e.id for e in extra], "approve"]
    g.elements[2:2] = extra
    g.edges = [e for e in g.edges if e.id != "plan>approve"] + [
        edge(a, b) for a, b in pairwise(chain)
    ]
    report = run_lint(g)
    assert report.failures == []
    size = next(w.message for w in report.warnings if w.element_id is None)
    assert size.startswith("Large map (29 steps, 2 lanes)")


def test_steps_without_time_kpi_or_enough_ai_flags_warn() -> None:
    g = replace(clean(), "plan", time=GraphTime(work_min=None, wait_min=None, text=""))
    g = replace(g, "issue", ai_flag=None)
    g.process.kpi = "Load sheet by T-10"
    report = run_lint(g)
    assert report.failures == []
    messages = [w.message for w in report.warnings]
    assert 'Activity "Plan" has no time stated.' in messages
    assert "2 activities have no KPI while the process has one." in messages
    assert "2 AI flags; aim for 3 to 7." in messages


def test_more_than_three_line_crossings_is_a_warning() -> None:
    """L12 needs the layout: a crafted layout whose lines cross four times, then three."""
    from app.domain.layout import Layout, LayoutCanvas, LayoutEdge

    graph = clean()

    def line(eid: str, *points: tuple[int, int]) -> LayoutEdge:
        return LayoutEdge(id=eid, kind="sequence", is_back_edge=False, points=list(points),
                          label="", label_pos=None)  # fmt: skip

    ids = [e.id for e in graph.edges]
    ladder = [line(ids[0], (0, 10 * k), (100, 10 * k)) for k in (1,)] + [
        line(ids[i], (20 * i, 0), (20 * i, 50)) for i in range(1, 5)
    ]  # one horizontal run crossed by four vertical ones
    layout = Layout(canvas=LayoutCanvas(w=100, h=50), lanes=[], phases=[], nodes=[], edges=ladder)
    warnings = [w.message for w in run_lint(graph, layout).warnings]
    assert "The map has 4 line crossings; consider changing the lane order." in warnings
    fewer = layout.model_copy(update={"edges": ladder[:4]})
    assert not any("crossings" in w.message for w in run_lint(graph, fewer).warnings)
    # A rejected step's lines are not on the map, so they don't count.
    replace(graph, "check", review_status="rejected")  # ids[4] and ids[5] leave "check"
    assert not any("crossings" in w.message for w in run_lint(graph, layout).warnings)
    assert not any("crossings" in w.message for w in run_lint(clean()).warnings)  # no layout


# --- Each view on its own (PRD §3.12.11; B5) ----------------------------------------------------


def with_views(g: Graph, steps: dict[str, str], lines: list[GraphEdge]) -> Graph:
    """The clean map with view membership on some steps and some extra lines."""
    g.elements = [
        e.model_copy(update={"view_membership": steps.get(e.id, "both")}) for e in g.elements
    ]
    g.edges = [e.model_copy(update={"view_membership": "both"}) for e in g.edges] + lines
    return g


def viewed(a: str, b: str, view: str, kind: str = "sequence", label: str = "",
           basis: str = "explicit_order") -> GraphEdge:  # fmt: skip
    return GraphEdge(id=f"{a}>{b}:{view}", from_=a, to=b, kind=kind, label=label,
                     view_membership=view, sequence_basis=basis)  # fmt: skip


def two_views() -> Graph:
    """The approval is only in the documents; practice goes straight from plan to check."""
    g = with_views(clean(), {"approve": "documented_only"}, [viewed("plan", "check", "done_only")])
    g.edges = [
        e.model_copy(update={"view_membership": "documented_only"})
        if e.from_ == "plan" and e.to == "approve"
        else e
        for e in g.edges
    ]
    return g


def test_a_map_drafted_before_the_views_passes_in_both() -> None:
    report = run_view_checks(clean())  # no view membership: everything is in both views
    assert (report.failures, report.warnings) == ([], [])


def test_each_view_draws_only_its_steps_and_lines() -> None:
    g = two_views()
    done, documented = view_graph(g, "done"), view_graph(g, "documented")
    assert [e.id for e in done.elements] == ["start", "plan", "check", "issue", "end"]
    assert ("plan", "check") in {(e.from_, e.to) for e in done.edges}
    assert [e.id for e in documented.elements] == [
        "start", "plan", "approve", "check", "issue", "end",
    ]  # fmt: skip
    assert ("plan", "check") not in {(e.from_, e.to) for e in documented.edges}
    report = run_view_checks(g)
    assert (report.failures, report.warnings) == ([], [])


def test_each_view_must_pass_the_flow_checks_on_its_own() -> None:
    """Without practice's line from plan to check, As done is broken (the approval is only in
    the documents) though the map as one still connects."""
    g = two_views()
    g.edges = [e for e in g.edges if e.id != "plan>check:done_only"]
    assert run_lint(g).failures == []  # the map as one is fine
    report = run_view_checks(g)
    assert [(f.rule, f.element_id, f.view) for f in report.failures] == [
        ("L9", "plan", "done"),  # no way out in practice
        ("L9", "check", "done"),  # can't be reached in practice
        ("L9", "issue", "done"),
        ("L9", "end", "done"),
    ]
    assert report.failures[0].message == 'As done: Activity "Plan" has no way out (no outgoing ' \
        "connection)."  # fmt: skip


def test_an_exit_a_view_draws_must_be_labelled() -> None:
    g = with_views(clean(), {}, [viewed("check", "end", "documented_only", kind="exception")])
    report = run_view_checks(g)
    assert [(f.rule, f.element_id, f.view, f.message) for f in report.failures] == [
        ("L4", "check", "documented",
         'As documented: Decision "Check" has 1 unlabelled exit(s).'),
    ]  # fmt: skip


def test_not_described_connectors_and_narration_order_are_warnings() -> None:
    g = with_views(
        clean(),
        {},
        [viewed("plan", "issue", "done_only", kind="gap", label="Not described",
                basis="document_order"),
         viewed("issue", "end", "documented_only", basis="narration_order")],
    )  # fmt: skip
    report = run_view_checks(g)
    assert report.failures == []
    assert [(w.rule, w.element_id, w.view, w.message) for w in report.warnings] == [
        ("L12", None, "done",
         'As done: 1 "not described" connector(s): the interview doesn\'t say what happens '
         "there."),
        ("L12", "end", None,
         'The line from "Issue" to "End" rests only on the order the sources mention them.'),
    ]  # fmt: skip
