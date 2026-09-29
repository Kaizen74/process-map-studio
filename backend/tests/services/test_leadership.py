"""The leadership view (PRD §4 Views, §5.4 Leadership; phase P11) on the sample map's graph (the G1
baseline): the per-phase facts, the systemic-or-local rule, evidence weight and confidence, and the
recommendation, each figure with the steps behind it. The expected values are worked out by hand
from the sample map (PRD Appendix A.5)."""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.graph import Graph, GraphConstraint
from app.services import leadership

G1 = Path(__file__).resolve().parents[1] / "golden" / "G1_graph.json"


def sample() -> Graph:
    return Graph.model_validate(json.loads(G1.read_text(encoding="utf-8")))


def ids(graph: Graph) -> dict[str, str]:
    return {e.label: e.id for e in graph.elements}


def test_facts_per_phase_with_the_steps_behind_each_figure() -> None:
    graph = sample()
    n = ids(graph)
    view = leadership.leadership_view(graph, {})
    got = [
        (p.name, p.work_min, p.wait_min, p.rework_loops, p.handoffs, p.divergence_counts)
        for p in view.facts.phases
    ]
    assert got == [
        # Draft → Approve, Approve → Special loads (approve), Approve → Draft (reject: a loop too)
        ("Plan", 20, 0, 1, 3, {}),
        # Special → LIR, Special → Resolve, Resolve → Draft (rework), LIR → Deviation
        ("Check and load", 80, 15, 1, 4, {"threshold": 1}),
        # Deviation → Approve deviation, Approve deviation → Issue, → LIR (rework)
        ("Close out", 15, 0, 1, 3, {"ownership": 1}),
    ]
    check = view.facts.phases[1].links
    assert check.work == [n["Resolve or offload"], n["Load and return LIR"]]
    assert check.wait == [n["Load and return LIR"]]
    assert check.rework_loops == [n["Resolve or offload"]]
    assert check.handoffs == [
        n["Special loads OK?"],
        n["Resolve or offload"],
        n["Load and return LIR"],
    ]
    assert check.divergence == {"threshold": [n["Load and return LIR"]]}
    assert view.facts.sources == 5
    # A line to the end (Issue load sheet → end) is not a handoff between steps.
    assert n["Issue load sheet"] not in view.facts.phases[2].links.handoffs


def test_systemic_or_local_by_the_written_rule() -> None:
    graph = sample()
    n = ids(graph)
    causes = leadership.leadership_view(graph, {}).interpretation.causes
    summary = [(c.cause_type, c.systemic, c.reason) for c in causes]
    assert summary == [
        # B.9 order. System fragmentation constrains two steps in two lanes: not one team's issue.
        ("system_fragmentation", True, "On 2 steps in 2 lanes: Load controller, Ramp."),
        ("single_point_knowledge", False, "On 1 step in one lane (Load controller)."),
        ("capacity_mismatch", False, "On 1 step in one lane (Ramp)."),
    ]
    fragmentation = causes[0]
    assert fragmentation.element_ids == [n["Special loads OK?"], n["Load and return LIR"]]
    assert [p.name for p in fragmentation.phases] == ["Check and load"]
    assert fragmentation.lanes == ["Load controller", "Ramp"]
    # Interview, SOP LC-07 and the Load controller's JD support at least one of the two steps.
    assert (fragmentation.evidence_weight.supporting, fragmentation.evidence_weight.sources) == (
        3,
        5,
    )
    assert fragmentation.confidence == round((0.85 + 0.6) / 2, 2)
    assert [(c.label, c.is_key) for c in fragmentation.constraints] == [
        ("Special loads OK?", True),
        ("Load and return LIR", True),
    ]


def policy_constraint() -> GraphConstraint:
    return GraphConstraint(
        text="Rules differ by airline", provenance="O", cause_type="policy_control", is_key=False
    )


def test_two_steps_in_one_lane_and_one_phase_stay_local() -> None:
    graph = sample()
    n = ids(graph)
    # Give "Issue load sheet" (Load controller, Close out) the same cause as "Deviation in limits?"
    # (Load controller, Close out): 2 steps, one lane, one phase → local.
    for e in graph.elements:
        if e.id in {n["Issue load sheet"], n["Deviation in limits?"]}:
            e.constraints = [policy_constraint()]
    policy = next(
        c
        for c in leadership.leadership_view(graph, {}).interpretation.causes
        if c.cause_type == "policy_control"
    )
    assert (policy.systemic, policy.reason) == (False, "On 2 steps in one lane (Load controller).")
    # The same cause across two phases (Plan and Close out) is systemic even in one lane.
    for e in graph.elements:
        if e.id == n["Draft load plan"]:
            e.constraints.append(policy_constraint())
    policy = next(
        c
        for c in leadership.leadership_view(graph, {}).interpretation.causes
        if c.cause_type == "policy_control"
    )
    assert (policy.systemic, policy.reason) == (True, "On 3 steps in 2 phases.")


def test_recommendation_and_saved_decisions() -> None:
    graph = sample()
    n = ids(graph)
    rec = leadership.leadership_view(
        graph, {"system_fragmentation": "Fund one digital loading report", "capacity_mismatch": "x"}
    ).recommendation
    # Waiting on steps constrained by a systemic cause: LIR's 15 minutes.
    assert (rec.recoverable_wait_min, rec.recoverable_wait_element_ids) == (
        15,
        [n["Load and return LIR"]],
    )
    assert rec.rework_loops == 3
    assert rec.rework_element_ids == [
        n["Approve load plan"], n["Resolve or offload"], n["Approve deviation"],
    ]  # fmt: skip
    # Rule-based decisions first (automation candidates), then by confidence.
    assert [(f.label, f.mechanism, f.lane) for f in rec.ai_flags] == [
        ("Special loads OK?", "rule_based", "Load controller"),
        ("Issue load sheet", "none", "Load controller"),
        ("Load and return LIR", "none", "Ramp"),
    ]
    # One line per systemic cause only; a saved line for a local cause is not shown.
    assert [(d.cause_type, d.text) for d in rec.decisions_needed] == [
        ("system_fragmentation", "Fund one digital loading report")
    ]


def test_rejected_steps_and_structural_elements_never_count() -> None:
    graph = sample()
    n = ids(graph)
    for e in graph.elements:
        if e.id == n["Load and return LIR"]:
            e.review_status = "rejected"
    view = leadership.leadership_view(graph, {})
    check = view.facts.phases[1]
    assert (check.work_min, check.wait_min, check.divergence_counts) == (40, 0, {})
    fragmentation = view.interpretation.causes[0]
    assert (fragmentation.systemic, fragmentation.element_ids) == (False, [n["Special loads OK?"]])
    assert view.recommendation.recoverable_wait_min == 0
    assert all(c.cause_type != "capacity_mismatch" for c in view.interpretation.causes)


def test_a_map_without_phases_or_causes_says_so_in_numbers() -> None:
    graph = sample()
    graph.phases = []
    for e in graph.elements:
        e.constraints = []
    view = leadership.leadership_view(graph, {})
    [only] = view.facts.phases
    assert (only.phase_id, only.name, only.work_min) == (None, "No phase", 115)
    assert view.interpretation.causes == []
    assert view.recommendation.decisions_needed == []
