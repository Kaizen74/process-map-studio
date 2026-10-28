"""Layout engine (PRD §3.9): deterministic, the lane rule, no overlaps, labels, the four routes.

The sample is the Appendix A draft map as stored in the G1 golden baseline (illustrative fixture
data, not SATS data); small crafted graphs cover the rules the sample doesn't reach.
"""

from __future__ import annotations

import json
from itertools import combinations, pairwise
from pathlib import Path
from typing import Any

import pytest

from app.domain.graph import (
    CycleTime,
    Graph,
    GraphDecision,
    GraphEdge,
    GraphElement,
    GraphHandoff,
    GraphPhase,
    GraphProcess,
    GraphRole,
    GraphTime,
    GraphVersion,
)
from app.domain.layout import Layout, LayoutEdge, LayoutNode
from app.services import layout as engine
from app.services import views
from app.services.layout import compute_layout, count_crossings, label_rect, wrap_label

G1 = Path(__file__).resolve().parents[1] / "golden" / "G1_graph.json"
STEPS = {"activity", "decision", "approval"}


def sample() -> Graph:
    data: dict[str, Any] = json.loads(G1.read_text(encoding="utf-8"))
    for e in data["elements"]:
        e["handoff"]["in_"] = e["handoff"].pop("in")
    for e in data["edges"]:
        e["from_"] = e.pop("from")
    # The map as the layout draws it until V1 (without the lines added for one view).
    return views.combined(Graph.model_validate(data))


def element(
    key: str, kind: str = "activity", lane: str | None = "a", **extra: object
) -> GraphElement:
    fields: dict[str, object] = {
        "id": key, "stable_key": key, "kind": kind, "label": key.capitalize(),
        "lane_role_id": None if kind in {"start", "end"} else lane, "phase_id": None,
        "time": GraphTime(work_min=None, wait_min=None, text=""), "complexity": None, "kpi": "",
        "decision": GraphDecision(mechanism="none", decider_role_id=None, rule_or_threshold="",
                                  escalation=""),
        "handoff": GraphHandoff(in_="", out=""), "raci": [], "provenance": "O",
        "r_reference": "", "source_state": "corroborated", "divergence_types": [],
        "constraints": [], "k_risk": "", "ai_flag": None, "evidence": [], "confidence": None,
        "confidence_breakdown": [], "needs_check": False, "review_status": "draft",
    }  # fmt: skip
    fields.update(extra)
    return GraphElement.model_validate(fields)


def edge(a: str, b: str, kind: str = "sequence", label: str = "") -> GraphEdge:
    return GraphEdge(id=f"{a}>{b}", from_=a, to=b, kind=kind, label=label)


def graph(
    elements: list[GraphElement],
    edges: list[GraphEdge],
    roles: tuple[str, ...] = ("a", "b", "c"),
    phases: list[GraphPhase] | None = None,
) -> Graph:
    return Graph(
        version=GraphVersion(id="v", label="v0.1", state="draft"),
        process=GraphProcess(name="P", trigger="T", end_point="E", kpi="",
                             cycle_time=CycleTime(elapsed_min=0, work_min=0, incomplete_steps=0)),
        roles=[GraphRole(id=r, name=r.upper(), is_system=False, lane_order=i + 1)
               for i, r in enumerate(roles)],
        phases=phases or [], elements=elements, edges=edges,
    )  # fmt: skip


@pytest.fixture(scope="module")
def drawn() -> tuple[Graph, Layout]:
    g = sample()
    return g, compute_layout(g)


def nodes_by_label(g: Graph, lay: Layout) -> dict[str, LayoutNode]:
    labels = {e.id: e.label for e in g.elements}
    return {labels[n.id]: n for n in lay.nodes}


def edges_by_label(g: Graph, lay: Layout) -> dict[tuple[str, str], LayoutEdge]:
    labels = {e.id: e.label for e in g.elements}
    ends = {e.id: (labels[e.from_], labels[e.to]) for e in g.edges}
    return {ends[e.id]: e for e in lay.edges}


def column(n: LayoutNode) -> int:
    return (n.x + n.w // 2 - engine.LABEL_COL) // engine.COL_W


def rect(n: LayoutNode) -> tuple[int, int, int, int]:
    return (n.x, n.y, n.x + n.w, n.y + n.h)


def overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


# --- Determinism and the whole sample ------------------------------------------------------------


def test_the_same_graph_always_gives_byte_identical_json() -> None:
    first = compute_layout(sample()).model_dump_json()
    assert all(compute_layout(sample()).model_dump_json() == first for _ in range(5))


def test_every_element_and_edge_is_placed(drawn: tuple[Graph, Layout]) -> None:
    g, lay = drawn
    assert [n.id for n in lay.nodes] == [e.id for e in g.elements]
    assert [e.id for e in lay.edges] == [e.id for e in g.edges]
    assert lay.canvas.w == engine.LABEL_COL + 10 * engine.COL_W  # v1.10 A.5: ten columns
    assert lay.canvas.h == engine.PHASE_BAND + 5 * engine.LANE_H


def test_lanes_follow_lane_order_with_branch_lanes_above(drawn: tuple[Graph, Layout]) -> None:
    """Approval-only and exception-only lanes sit directly above the lane they branch from."""
    _, lay = drawn
    assert [(ln.label, ln.step_count) for ln in lay.lanes] == [
        ("Load control lead", 1),
        ("Airline ops", 1),
        ("Captain", 1),
        ("Load controller", 6),  # v1.10 A.5: + Busy wave? and Read report at aircraft
        ("Ramp", 1),
    ]
    assert [ln.y for ln in lay.lanes] == [48, 172, 296, 420, 544]


def test_every_step_sits_in_its_lane(drawn: tuple[Graph, Layout]) -> None:
    """Lane rule (constraint 5): the node is drawn inside the lane of its lane role."""
    g, lay = drawn
    lanes = {ln.role_id: ln for ln in lay.lanes}
    nodes = {n.id: n for n in lay.nodes}
    for e in g.elements:
        n = nodes[e.id]
        if e.kind in STEPS:
            lane = lanes[e.lane_role_id or ""]
            assert lane.y <= n.y and n.y + n.h <= lane.y + lane.h, e.label
    by = nodes_by_label(g, lay)
    # Start and end share the lane of the step they lead to or come from.
    assert by["Flight scheduled"].y + 8 == by["Draft load plan"].y + 22
    assert by["Final load sheet issued"].y + 8 == by["Issue load sheet"].y + 22


def test_no_two_nodes_overlap_or_share_a_cell(drawn: tuple[Graph, Layout]) -> None:
    _, lay = drawn
    for a, b in combinations(lay.nodes, 2):
        assert not overlaps(rect(a), rect(b)), (a.id, b.id)
    cells = [(column(n), n.y // engine.LANE_H) for n in lay.nodes]
    assert len(cells) == len(set(cells))


def test_columns_follow_the_longest_path(drawn: tuple[Graph, Layout]) -> None:
    g, lay = drawn
    by = nodes_by_label(g, lay)
    assert {label: column(n) for label, n in by.items()} == {
        "Flight scheduled": 0,
        "Draft load plan": 1,
        "Approve load plan": 2,
        "Special loads OK?": 3,
        "Resolve or offload": 3,  # exception step: beside its decision, one lane above
        "Load and return LIR": 4,
        "Busy wave?": 5,  # v1.10 A.5: the lived busy-wave variation and its branch
        "Read report at aircraft": 6,
        "Deviation in limits?": 7,
        "Approve deviation": 7,  # likewise
        "Issue load sheet": 8,
        "Final load sheet issued": 9,
    }


def test_phases_are_contiguous_ordered_and_cover_the_map(drawn: tuple[Graph, Layout]) -> None:
    _, lay = drawn
    assert [(p.label, p.time_window) for p in lay.phases] == [
        ("Plan", "T-120 to T-90"),
        ("Check and load", ""),
        ("Close out", "T-15 to T-10"),
    ]
    assert lay.phases[0].x == engine.LABEL_COL
    for a, b in pairwise(lay.phases):
        assert a.x + a.w == b.x
    assert lay.phases[-1].x + lay.phases[-1].w == lay.canvas.w


def test_every_step_has_its_label_on_one_or_two_short_lines(drawn: tuple[Graph, Layout]) -> None:
    g, lay = drawn
    by = nodes_by_label(g, lay)
    kinds = {e.label: e.kind for e in g.elements}
    for label, n in by.items():
        if kinds[label] in STEPS:
            assert 1 <= len(n.label_lines) <= 2 and all(len(x) <= 16 for x in n.label_lines)
            assert " ".join(n.label_lines) == label  # nothing in the sample needs an ellipsis
        else:
            assert n.label_lines == []  # start and end are named in the panel and for readers
    assert by["Load and return LIR"].label_lines == ["Load and", "return LIR"]
    assert by["Special loads OK?"].label_lines == ["Special", "loads OK?"]


@pytest.mark.parametrize(
    ("label", "lines"),
    [
        ("Draft load plan", ["Draft load plan"]),
        ("", []),
        ("  Issue   load sheet ", ["Issue load sheet"]),
        ("Deviation in limits?", ["Deviation", "in limits?"]),
        ("Reconcile the passenger and baggage figures", ["Reconcile the p…", "and baggage fig…"]),
        ("Supercalifragilisticexpialidocious", ["Supercalifragil…"]),
    ],
)
def test_labels_wrap_at_the_best_word_boundary(label: str, lines: list[str]) -> None:
    assert wrap_label(label) == lines


def test_shapes_and_sizes_follow_the_constants(drawn: tuple[Graph, Layout]) -> None:
    g, lay = drawn
    by = nodes_by_label(g, lay)
    assert (by["Draft load plan"].shape, by["Draft load plan"].w, by["Draft load plan"].h) == (
        "rounded_rect", 100, 44)  # fmt: skip
    assert (by["Approve load plan"].shape, by["Approve load plan"].h) == ("pill", 44)
    assert (by["Special loads OK?"].shape, by["Special loads OK?"].w) == ("diamond", 52)
    assert by["Flight scheduled"].shape == "circle"
    assert by["Final load sheet issued"].shape == "double_circle"


# --- Edges ---------------------------------------------------------------------------------------


def test_every_edge_is_orthogonal_and_touches_both_nodes(drawn: tuple[Graph, Layout]) -> None:
    g, lay = drawn
    nodes = {n.id: n for n in lay.nodes}
    for e, le in zip(g.edges, lay.edges, strict=True):
        for (x1, y1), (x2, y2) in pairwise(le.points):
            assert x1 == x2 or y1 == y2, le.id
        for node, (x, y) in ((nodes[e.from_], le.points[0]), (nodes[e.to], le.points[-1])):
            on_side = x in (node.x, node.x + node.w) and node.y <= y <= node.y + node.h
            on_edge = y in (node.y, node.y + node.h) and node.x <= x <= node.x + node.w
            assert on_side or on_edge, le.id


def test_the_four_routes(drawn: tuple[Graph, Layout]) -> None:
    g, lay = drawn
    by = nodes_by_label(g, lay)
    routes = edges_by_label(g, lay)
    # Same lane: straight across, right side to left side.
    same = routes[("Deviation in limits?", "Issue load sheet")]
    dev, issue = by["Deviation in limits?"], by["Issue load sheet"]
    assert same.points == [(dev.x + dev.w, dev.y + 26), (issue.x, issue.y + 22)]
    # Another lane: along, through the gutter before the next column, along.
    across = routes[("Draft load plan", "Approve load plan")]
    gutter = engine.LABEL_COL + 2 * engine.COL_W
    assert [x for x, _ in across.points] == [356, gutter, gutter, 380]
    # An exception step above its decision: straight up, top to bottom.
    up = routes[("Special loads OK?", "Resolve or offload")]
    special, resolve = by["Special loads OK?"], by["Resolve or offload"]
    assert up.points == [(special.x + 26, special.y), (resolve.x + 50, resolve.y + resolve.h)]
    assert not up.is_back_edge
    # Back edges: dashed along the track 14 px below the top of the upper lane, into the top.
    back = routes[("Approve deviation", "Load and return LIR")]
    assert back.is_back_edge and back.kind == "rework"
    captain_top = lay.lanes[2].y
    assert back.points[1][1] == back.points[2][1] == captain_top + engine.BACK_TRACK
    lir = by["Load and return LIR"]
    assert back.points[-1] == (lir.x + 50, lir.y)


def test_back_edges_sharing_a_target_are_offset(drawn: tuple[Graph, Layout]) -> None:
    g, lay = drawn
    routes = edges_by_label(g, lay)
    plan = nodes_by_label(g, lay)["Draft load plan"]
    rework = routes[("Approve load plan", "Draft load plan")]
    replan = routes[("Resolve or offload", "Draft load plan")]
    assert rework.is_back_edge and replan.is_back_edge
    assert rework.points[-1] == (plan.x + 50 - 14, plan.y)
    assert replan.points[-1] == (plan.x + 50 + 14, plan.y)
    assert sum(e.is_back_edge for e in lay.edges) == 3


def test_edge_labels_sit_on_no_node(drawn: tuple[Graph, Layout]) -> None:
    g, lay = drawn
    labelled = [e for e in lay.edges if e.label]
    assert len(labelled) == 11  # v1.10 A.5: + the Yes and No of Busy wave?
    for e in labelled:
        assert e.label_pos is not None
        chip = label_rect(e.label, e.label_pos)
        for n in lay.nodes:
            assert not overlaps(chip, rect(n)), (e.label, n.id)
    for a, b in combinations(labelled, 2):
        assert a.label_pos and b.label_pos
        assert not overlaps(label_rect(a.label, a.label_pos), label_rect(b.label, b.label_pos))
    assert all(e.label_pos is None for e in lay.edges if not e.label)
    back = edges_by_label(g, lay)[("Approve deviation", "Load and return LIR")]
    assert back.label_pos is not None and back.label_pos.align == "right"  # above the track


def test_text_under_a_node_moves_beside_a_line_entering_from_below(
    drawn: tuple[Graph, Layout],
) -> None:
    g, lay = drawn
    by = nodes_by_label(g, lay)
    resolve = by["Resolve or offload"]  # entered from below by the exception edge
    assert (resolve.lens_pos.x, resolve.lens_pos.align) == (resolve.x + 50 + 8, "left")
    plan = by["Draft load plan"]
    assert (plan.lens_pos.x, plan.lens_pos.align) == (plan.x + 50, "center")
    assert plan.lens_pos.y == plan.y + plan.h + engine.LENS_GAP
    special = by["Special loads OK?"]  # label lines under the diamond, then the lens line
    assert special.label_pos.y == special.y + special.h + engine.TEXT_GAP
    assert special.lens_pos.y == special.label_pos.y + 2 * engine.LABEL_LINE + engine.TEXT_GAP


def test_the_sample_has_two_crossings(drawn: tuple[Graph, Layout]) -> None:
    assert count_crossings(drawn[1].edges) == 2


# --- Crafted graphs ------------------------------------------------------------------------------


def test_a_cycle_without_a_loop_kind_is_still_a_back_edge() -> None:
    g = graph(
        [element("start", "start"), element("x"), element("y"), element("end", "end")],
        [edge("start", "x"), edge("x", "y"), edge("y", "x", "sequence", "Again"), edge("y", "end")],
    )
    lay = compute_layout(g)
    assert [e.is_back_edge for e in lay.edges] == [False, False, True, False]
    assert [column(n) for n in lay.nodes] == [0, 1, 2, 3]


def test_a_reject_to_a_new_exception_step_goes_beside_its_approval() -> None:
    g = graph(
        [element("start", "start"), element("ok", "approval"), element("fix", lane="b"),
         element("go"), element("end", "end")],
        [edge("start", "ok"), edge("ok", "fix", "reject", "Reject"),
         edge("ok", "go", "approve", "Approve"), edge("go", "end")],
    )  # fmt: skip
    lay = compute_layout(g)
    nodes = {n.id: n for n in lay.nodes}
    assert not any(e.is_back_edge for e in lay.edges)
    assert column(nodes["fix"]) == column(nodes["ok"]) == 1
    assert [ln.role_id for ln in lay.lanes] == ["b", "a"]  # the exception lane goes above
    assert lay.edges[1].points == [(nodes["ok"].x + 50, nodes["ok"].y), (nodes["fix"].x + 50,
                                   nodes["fix"].y + 44)]  # fmt: skip


def test_an_exception_below_leaves_the_bottom_and_moves_the_decision_text() -> None:
    """When the lane beside is taken, the exception lane can end up below its decision."""
    g = graph(
        [element("start", "start"), element("d", "decision"), element("x", lane="b"),
         element("y", lane="b"), element("end", "end")],
        [edge("start", "d"), edge("d", "y", "yes", "Yes"), edge("d", "x", "no", "No"),
         edge("y", "end")],
        roles=("a", "b"),
    )  # fmt: skip
    lay = compute_layout(g)
    nodes = {n.id: n for n in lay.nodes}
    d, x = nodes["d"], nodes["x"]
    assert column(x) == column(d) and x.y > d.y
    assert lay.edges[2].points == [(d.x + 26, d.y + 52), (x.x + 50, x.y)]
    assert d.label_pos.align == d.lens_pos.align == "left"
    assert lay.edges[2].label_pos is not None and lay.edges[2].label_pos.align == "right"


def test_a_clash_pushes_the_later_node_right_and_everything_after_it() -> None:
    g = graph(
        [element("start", "start"), element("p"), element("q"), element("r"), element("s"),
         element("end", "end")],
        [edge("start", "p"), edge("start", "q"), edge("p", "r"), edge("q", "r"), edge("r", "s"),
         edge("s", "end")],
    )  # fmt: skip
    cols = {n.id: column(n) for n in compute_layout(g).nodes}
    assert cols == {"start": 0, "p": 1, "q": 2, "r": 3, "s": 4, "end": 5}


def test_a_step_without_a_known_lane_goes_in_an_unnamed_lane_at_the_bottom() -> None:
    g = graph(
        [element("start", "start"), element("x"), element("y", lane="ghost"),
         element("end", "end")],
        [edge("start", "x"), edge("x", "y"), edge("y", "end")],
    )  # fmt: skip
    lay = compute_layout(g)
    assert [(ln.role_id, ln.label) for ln in lay.lanes] == [("a", "A"), ("", "")]


def test_an_empty_graph_gives_an_empty_canvas() -> None:
    lay = compute_layout(graph([], []))
    assert (lay.canvas.w, lay.canvas.h) == (engine.LABEL_COL, engine.PHASE_BAND)
    assert lay.lanes == lay.nodes == lay.edges == lay.phases == []


def test_phases_stay_contiguous_when_their_columns_overlap() -> None:
    phases = [GraphPhase(id="p1", name="One", time_window="", order=1),
              GraphPhase(id="p2", name="Two", time_window="", order=2),
              GraphPhase(id="p3", name="Empty", time_window="", order=3)]  # fmt: skip
    g = graph(
        [element("start", "start"), element("x", phase_id="p2"), element("y", phase_id="p1"),
         element("end", "end")],
        [edge("start", "x"), edge("x", "y"), edge("y", "end")],
        phases=phases,
    )  # fmt: skip
    lay = compute_layout(g)
    # "Two" starts first on the map, so "One" keeps one column and "Two" the rest; the empty
    # phase is left out.
    assert [(p.label, p.x, p.w) for p in lay.phases] == [
        ("One", engine.LABEL_COL, engine.COL_W),
        ("Two", engine.LABEL_COL + engine.COL_W, 3 * engine.COL_W),
    ]


def test_crossings_count_only_where_lines_really_cross() -> None:
    def line(eid: str, *points: tuple[int, int]) -> LayoutEdge:
        return LayoutEdge(id=eid, kind="sequence", is_back_edge=False, points=list(points),
                          label="", label_pos=None)  # fmt: skip

    across = line("h", (0, 50), (100, 50))
    down = line("v", (50, 0), (50, 100))
    touching = line("t", (100, 0), (100, 100))  # meets the end of `across`, doesn't cross it
    corner = line("c", (0, 50), (0, 90), (60, 90))  # shares a start point
    assert count_crossings([across, down]) == 1
    assert count_crossings([across, touching, corner]) == 0
    assert count_crossings([across, down, corner]) == 2  # `corner` runs across `down` too


def test_flows_side_by_side_get_one_phase_each_in_their_own_columns() -> None:
    """Eric's cargo manual (2026-10-28): several flows leave one start, each its own phase. Their
    steps all ranked from column 1, so the phase headers overlapped ("Inbound arrival and
    breakTranshipment") and a phase's steps sat under another's header. Each phase now takes its
    own columns, in phase order; the end comes after all of them."""
    phases = [GraphPhase(id=p, name=p.capitalize(), order=i, time_window="")
              for i, p in enumerate(("inbound", "transfer", "outbound"))]  # fmt: skip
    g = graph(
        [element("s", "start"),
         element("i1", phase_id="inbound"), element("i2", lane="b", phase_id="inbound"),
         element("t1", lane="b", phase_id="transfer"), element("t2", phase_id="transfer"),
         element("t3", lane="c", phase_id="transfer"),
         element("o1", lane="c", phase_id="outbound"),
         element("e", "end")],
        [edge("s", "i1"), edge("i1", "i2"), edge("i2", "e"),
         edge("s", "t1"), edge("t1", "t2"), edge("t2", "t3"), edge("t3", "e"),
         edge("s", "o1"), edge("o1", "e")],
        phases=phases,
    )  # fmt: skip
    lay = compute_layout(g)
    cols = {n.id: column(n) for n in lay.nodes}
    assert [cols[k] for k in ("i1", "i2", "t1", "t2", "t3", "o1")] == [1, 2, 3, 4, 5, 6]
    assert cols["s"] == 0 and cols["e"] == 7
    bands = [(p.label, (p.x - engine.LABEL_COL) // engine.COL_W, p.w // engine.COL_W)
             for p in lay.phases]  # fmt: skip
    assert bands == [("Inbound", 0, 3), ("Transfer", 3, 3), ("Outbound", 6, 2)]
    for a, b in combinations(lay.nodes, 2):
        assert not overlaps(rect(a), rect(b)), (a.id, b.id)
    assert compute_layout(g).model_dump_json() == lay.model_dump_json()
