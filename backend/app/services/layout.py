"""Layout engine (PRD §3.9): deterministic swimlane positions for a graph; no database.

`compute_layout(graph)` places every element of the graph (rejected ones too: the map shows them
faded) and routes every edge. The same graph always gives byte-identical layout JSON; the UI draws
exactly these numbers.

- Lanes: one per role that holds a step, in `lane_order` (then first appearance in process order).
  A lane holding only approvals and exception steps (steps reached only by a `no` or `reject`
  edge) sits directly above the lane of the step they approve or branch from. Start and end sit in
  the lane of the step they lead to or come from.
- Columns: the longest path from the start over forward edges. Back edges (`rework`; `reject`
  unless its target is reached no other way; any edge that closes a cycle) are left out of the
  ranking. A step reached only by a `no` or `reject` edge goes in its source's column when that
  cell and the cells between the two lanes are free (an exception step above or below its
  decision). At most one node per cell; a clash pushes the later node right, and everything
  after it follows.
- Phases span their steps' columns, contiguous and in order; flows side by side from one start
  each take their own columns, phase by phase (2026-10-28). Labels wrap to two lines.
- Edges are orthogonal: same lane straight across; another lane via the gutter between columns;
  an exception step straight up or down; back edges dashed along a track 14 px below the top of
  the upper lane, entering the target from the top (±14 px when two share a target).
"""

from __future__ import annotations

import heapq
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import pairwise

from app.domain.enums import EdgeKind, ElementKind
from app.domain.graph import Graph, GraphEdge, GraphElement
from app.domain.layout import (
    Layout,
    LayoutCanvas,
    LayoutEdge,
    LayoutLane,
    LayoutNode,
    LayoutPhase,
    Shape,
    TextPos,
)

# Geometry (px), PRD §3.9.
LABEL_COL = 120
COL_W = 124
LANE_H = 124
PHASE_BAND = 48
BACK_TRACK = 14
SHARED_OFFSET = 14
NODE_CY = 44  # every node's centre sits this far below its lane's top edge
LABEL_LINE = 15  # height of one line of a label under a decision
TEXT_GAP = 4  # between a decision and its label, and between that label and the lens line
LENS_GAP = 6  # between a box or circle and its lens line
LINE_CHARS = 16  # characters per label line before an ellipsis
EDGE_LABEL_GAP = 6
SIDE_TEXT = 8  # text left-aligned this far right of a line leaving or entering a node's bottom
LABEL_CHAR_W = 6  # average width of one character of an 11 px edge label
LABEL_PAD = 4
LABEL_CHIP_H = 16

BOXES: dict[str, tuple[Shape, int, int]] = {
    ElementKind.ACTIVITY.value: ("rounded_rect", 100, 44),
    ElementKind.APPROVAL.value: ("pill", 100, 44),
    ElementKind.DECISION.value: ("diamond", 52, 52),  # a 36 px square turned 45°
    ElementKind.START.value: ("circle", 16, 16),
    ElementKind.END.value: ("double_circle", 16, 16),
}
STEP_KINDS = {ElementKind.ACTIVITY.value, ElementKind.DECISION.value, ElementKind.APPROVAL.value}
STRUCTURAL = {ElementKind.START.value, ElementKind.END.value}
EXCEPTION_EXITS = {EdgeKind.NO.value, EdgeKind.REJECT.value}
NO_LANE = ""  # steps whose lane role is missing share one unnamed lane at the bottom

Point = tuple[int, int]


def wrap_label(label: str) -> list[str]:
    """Two lines at most, split at the word boundary that keeps the longer line shortest; a line
    longer than 16 characters ends in an ellipsis (PRD §3.9 rule 5)."""
    text = " ".join(label.split())
    if len(text) <= LINE_CHARS:
        return [text] if text else []
    words = text.split(" ")
    if len(words) == 1:
        return [_clip(text)]
    splits = [(" ".join(words[:i]), " ".join(words[i:])) for i in range(1, len(words))]
    first, second = min(splits, key=lambda s: max(len(s[0]), len(s[1])))
    return [_clip(first), _clip(second)]


def _clip(line: str) -> str:
    return line if len(line) <= LINE_CHARS else line[: LINE_CHARS - 1].rstrip() + "…"


def back_edge_ids(elements: list[GraphElement], edges: list[GraphEdge]) -> set[str]:
    """Edges left out of the ranking: loops back and any edge that closes a cycle."""
    incoming: dict[str, int] = {}
    for e in edges:
        incoming[e.to] = incoming.get(e.to, 0) + 1
    back = {
        e.id
        for e in edges
        if e.kind == EdgeKind.REWORK.value
        or (e.kind == EdgeKind.REJECT.value and incoming.get(e.to, 0) > 1)
    }
    out: dict[str, list[GraphEdge]] = {}
    for e in edges:
        if e.id not in back:
            out.setdefault(e.from_, []).append(e)
    # Depth-first from the start (then from anything not yet seen), children in edge order.
    order = sorted(elements, key=lambda e: e.kind != ElementKind.START.value)
    state: dict[str, int] = {}  # 1 on the current path, 2 finished
    for root in order:
        if root.id in state:
            continue
        state[root.id] = 1
        stack: list[tuple[str, int]] = [(root.id, 0)]
        while stack:
            node, i = stack[-1]
            children = out.get(node, [])
            if i == len(children):
                state[node] = 2
                stack.pop()
                continue
            stack[-1] = (node, i + 1)
            edge = children[i]
            seen = state.get(edge.to)
            if seen == 1:
                back.add(edge.id)
            elif seen is None:
                state[edge.to] = 1
                stack.append((edge.to, 0))
    return back


@dataclass
class _Placement:
    lanes: list[str]  # role IDs top to bottom (NO_LANE for the unnamed lane)
    lane_of: dict[str, int]  # element ID → lane index
    column: dict[str, int] = field(default_factory=dict)
    cells: dict[tuple[int, int], str] = field(default_factory=dict)  # (lane, column) → node
    order: list[str] = field(default_factory=list)  # nodes in the order they were placed
    kept_clear: dict[str, list[tuple[int, int]]] = field(default_factory=dict)  # node → cells

    def free(self, lane: int, col: int) -> bool:
        return (lane, col) not in self.cells


def _element_lanes(
    elements: list[GraphElement], forward: list[GraphEdge], roles: set[str]
) -> dict[str, str]:
    """Each element's lane role; start and end borrow the lane of their neighbour."""
    lane: dict[str, str] = {}
    for e in elements:
        if e.kind not in STRUCTURAL:
            lane[e.id] = e.lane_role_id if e.lane_role_id in roles else NO_LANE
    for e in elements:
        if e.kind == ElementKind.START.value:
            nxt = [x.to for x in forward if x.from_ == e.id and x.to in lane]
            lane[e.id] = lane[nxt[0]] if nxt else ""
        elif e.kind == ElementKind.END.value:
            prev = [x.from_ for x in forward if x.to == e.id and x.from_ in lane]
            lane[e.id] = lane[prev[0]] if prev else ""
    return lane


def _lane_order(
    graph: Graph, elements: list[GraphElement], forward: list[GraphEdge], lane: dict[str, str]
) -> list[str]:
    steps = [e for e in elements if e.kind not in STRUCTURAL]
    used = list(dict.fromkeys(lane[e.id] for e in steps))
    first = {role: i for i, role in reversed(list(enumerate(lane[e.id] for e in steps)))}
    orders = {r.id: r.lane_order for r in graph.roles}

    def key(role: str) -> tuple[bool, int, int]:
        order = orders.get(role)
        return (role == NO_LANE or order is None, order or 0, first[role])

    lanes = sorted(used, key=key)
    into: dict[str, list[GraphEdge]] = {}
    for x in forward:
        into.setdefault(x.to, []).append(x)

    def branches(e: GraphElement) -> bool:
        reached = into.get(e.id, [])
        exception = len(reached) == 1 and reached[0].kind in EXCEPTION_EXITS
        return e.kind == ElementKind.APPROVAL.value or exception

    # A lane of approvals and exception steps sits directly above the lane they branch from.
    for role in list(lanes):
        mine = [e for e in steps if lane[e.id] == role]
        if role == NO_LANE or not all(branches(e) for e in mine):
            continue
        approved = next(
            (
                lane[x.from_]
                for x in into.get(mine[0].id, [])
                if lane.get(x.from_) not in (None, NO_LANE, role)
            ),
            None,
        )
        if approved is None:
            continue
        lanes.remove(role)
        lanes.insert(lanes.index(approved), role)
    if not lanes and elements:
        lanes = [NO_LANE]
    return lanes


def _place(graph: Graph, back: set[str]) -> _Placement:
    elements = graph.elements
    index = {e.id: i for i, e in enumerate(elements)}
    forward = [e for e in graph.edges if e.id not in back]
    roles = {r.id for r in graph.roles}
    lane = _element_lanes(elements, forward, roles)
    lanes = _lane_order(graph, elements, forward, lane)
    position = {role: i for i, role in enumerate(lanes)}
    placement = _Placement(
        lanes=lanes, lane_of={e.id: position.get(lane[e.id], 0) for e in elements}
    )

    preds: dict[str, list[GraphEdge]] = {e.id: [] for e in elements}
    succs: dict[str, list[str]] = {e.id: [] for e in elements}
    for edge in forward:
        preds[edge.to].append(edge)
        succs[edge.from_].append(edge.to)
    # Topological order over forward edges; ties go to process order.
    waiting = {e.id: len(preds[e.id]) for e in elements}
    ready = [(index[e.id], e.id) for e in elements if waiting[e.id] == 0]
    heapq.heapify(ready)
    while ready:
        _, node = heapq.heappop(ready)
        _place_node(placement, node, preds[node])
        for nxt in succs[node]:
            waiting[nxt] -= 1
            if waiting[nxt] == 0:
                heapq.heappush(ready, (index[nxt], nxt))
    _separate_phases(graph, placement, preds)
    return placement


def _separate_phases(graph: Graph, p: _Placement, preds: dict[str, list[GraphEdge]]) -> None:
    """Each phase takes its own columns, in phase order (2026-10-28, Eric's cargo manual: flows
    side by side from one start all ranked from column 1, so phase headers overlapped). A phase
    that starts at or before the previous phase's last column moves right as a block; a node with
    no phase (the end) follows its predecessors. Maps whose phases already follow each other, or
    whose phases run against the flow, are left exactly as they were."""
    rank = {ph.id: i for i, ph in enumerate(sorted(graph.phases, key=lambda ph: ph.order))}
    phase_of = {e.id: rank[e.phase_id] for e in graph.elements if e.phase_id in rank}
    if any(phase_of.get(e.from_, -1) > r for node, r in phase_of.items() for e in preds[node]):
        return  # the phases run against the flow: moving them would send lines backwards
    spans: dict[int, list[int]] = {}
    for node, r in phase_of.items():
        spans.setdefault(r, []).append(p.column[node])
    shift: dict[int, int] = {}
    last = -1
    for r in sorted(spans):
        shift[r] = max(0, last + 1 - min(spans[r]))
        last = max(spans[r]) + shift[r]
    if not any(shift.values()):
        return
    column: dict[str, int] = {}
    cells: dict[tuple[int, int], str] = {}
    for node in p.order:
        lane, before = p.lane_of[node], p.column[node]
        if node in phase_of:
            col = before + shift[phase_of[node]]
        else:
            col = max((column[e.from_] + 1 for e in preds[node] if e.from_ in column),
                      default=before)  # fmt: skip
        while (lane, col) in cells:
            col += 1
        column[node] = col
        cells[(lane, col)] = node
        for x, c in p.kept_clear.get(node, []):
            cells.setdefault((x, c + col - before), "")
    p.column, p.cells = column, cells


def _place_node(p: _Placement, node: str, preds: list[GraphEdge]) -> None:
    lane = p.lane_of[node]
    col = max((p.column[e.from_] + 1 for e in preds), default=0)
    if len(preds) == 1 and preds[0].kind in EXCEPTION_EXITS:
        source = preds[0].from_
        beside, from_lane = p.column[source], p.lane_of[source]
        step = 1 if lane > from_lane else -1
        between = range(from_lane + step, lane, step)
        if lane != from_lane and p.free(lane, beside) and all(p.free(x, beside) for x in between):
            for x in between:  # keep the straight line clear of later nodes
                p.cells[(x, beside)] = ""
                p.kept_clear.setdefault(node, []).append((x, beside))
            col = beside
    while not p.free(lane, col):
        col += 1
    p.column[node] = col
    p.cells[(lane, col)] = node
    p.order.append(node)


def _phases(graph: Graph, p: _Placement, columns: int) -> list[LayoutPhase]:
    spans: dict[str, list[int]] = {}
    for e in graph.elements:
        if e.phase_id:
            spans.setdefault(e.phase_id, []).append(p.column[e.id])
    ordered = [ph for ph in sorted(graph.phases, key=lambda ph: ph.order) if ph.id in spans]
    out: list[LayoutPhase] = []
    start = 0
    for i, phase in enumerate(ordered):
        nxt = ordered[i + 1].id if i + 1 < len(ordered) else None
        end = min(max(start + 1, min(spans[nxt])) if nxt else columns, columns)
        if end > start:
            out.append(
                LayoutPhase(phase_id=phase.id, label=phase.name, time_window=phase.time_window,
                            x=LABEL_COL + start * COL_W, w=(end - start) * COL_W)
            )  # fmt: skip
        start = end
    return out


def _col_x(col: int) -> int:
    return LABEL_COL + col * COL_W


def _lane_y(lane: int) -> int:
    return PHASE_BAND + lane * LANE_H


@dataclass(frozen=True)
class _Box:
    x: int
    y: int
    w: int
    h: int

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2

    @property
    def left(self) -> Point:
        return (self.x, self.cy)

    @property
    def right(self) -> Point:
        return (self.x + self.w, self.cy)

    @property
    def top(self) -> Point:
        return (self.cx, self.y)

    @property
    def bottom(self) -> Point:
        return (self.cx, self.y + self.h)


def _box(kind: str, lane: int, col: int) -> tuple[Shape, _Box]:
    shape, w, h = BOXES.get(kind, BOXES[ElementKind.ACTIVITY.value])
    cx, cy = _col_x(col) + COL_W // 2, _lane_y(lane) + NODE_CY
    return shape, _Box(cx - w // 2, cy - h // 2, w, h)


def _dedupe(points: Iterable[Point]) -> list[Point]:
    out: list[Point] = []
    for pt in points:
        if not out or out[-1] != pt:
            out.append(pt)
    return out


def _route(
    edge: GraphEdge,
    is_back: bool,
    p: _Placement,
    boxes: dict[str, _Box],
    offset: int,
) -> tuple[list[Point], list[TextPos]]:
    """The line's corners, and where its label may go, best first."""
    s, t = boxes[edge.from_], boxes[edge.to]
    ls, lt = p.lane_of[edge.from_], p.lane_of[edge.to]
    cs, ct = p.column[edge.from_], p.column[edge.to]
    gap = EDGE_LABEL_GAP

    if is_back or ct < cs or (ct == cs and ls == lt):
        # Along the track below the top of the upper lane, into the target from the top.
        # The label sits above the track, right-aligned to where the line starts.
        track = _lane_y(min(ls, lt)) + BACK_TRACK
        (sx, sy), (tx, ty) = s.top, t.top
        tx += offset
        points = [(sx, sy), (sx, track), (tx, track), (tx, ty)]
        spots = [TextPos(x=sx - gap, y=track - 9, align="right"),
                 TextPos(x=sx + gap, y=track - 9, align="left"),
                 TextPos(x=sx - gap, y=track + 9, align="right")]  # fmt: skip
    elif ct == cs:
        # An exception step straight above or below.
        if lt < ls:
            points = [s.top, t.bottom]
            y = s.y - 10
        else:
            points = [s.bottom, t.top]
            y = s.y + s.h + 10
        spots = [TextPos(x=s.cx - gap, y=y, align="right"),
                 TextPos(x=s.cx + gap, y=y, align="left")]  # fmt: skip
    elif ls == lt:
        points = [s.right, t.left]
        x = s.x + s.w + gap
        spots = [TextPos(x=x, y=s.cy - 9, align="left"),
                 TextPos(x=x, y=s.cy + 9, align="left"),
                 TextPos(x=x, y=min(s.y, t.y) - 10, align="left")]  # fmt: skip
    else:
        # Across lanes: along the source lane, down or up a gutter, along the target lane.
        # The first gutter whose runs pass no node; else the one just before the target.
        gutter = ct
        for k in range(cs + 1, ct + 1):
            if all(p.free(ls, c) for c in range(cs + 1, k)) and all(
                p.free(lt, c) for c in range(k, ct)
            ):
                gutter = k
                break
        gx = _col_x(gutter)
        points = [s.right, (gx, s.cy), (gx, t.cy), t.left]
        x = s.x + s.w + gap
        away = 9 if t.cy < s.cy else -9  # the label sits on the side the line doesn't turn to
        spots = [TextPos(x=x, y=s.cy + away, align="left"),
                 TextPos(x=x, y=s.y - 10, align="left")]  # fmt: skip
    return _dedupe(points), spots


Rect = tuple[int, int, int, int]  # left, top, right, bottom


def label_rect(label: str, pos: TextPos) -> Rect:
    """The chip an edge label is drawn on (11 px text), estimated from its length."""
    w = len(label) * LABEL_CHAR_W + 2 * LABEL_PAD
    left = {"left": pos.x, "center": pos.x - w // 2, "right": pos.x - w}[pos.align]
    return (left, pos.y - LABEL_CHIP_H // 2, left + w, pos.y + LABEL_CHIP_H // 2)


def _overlaps(a: Rect, b: Rect) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _hits_line(r: Rect, points: list[Point]) -> bool:
    for (x1, y1), (x2, y2) in pairwise(points):
        seg = (min(x1, x2), min(y1, y2), max(x1, x2) + 1, max(y1, y2) + 1)
        if _overlaps(r, seg):
            return True
    return False


def _extra_spots(points: list[Point], spots: list[TextPos]) -> list[TextPos]:
    """Where a label may go when its usual spots are all taken (2026-10-28, Eric's cargo
    overview: five lines left the start, two exits shared one line): by the step the line leads
    to, then stacked just above or below each usual spot."""
    out: list[TextPos] = []
    if len(points) >= 2:
        (px, py), (tx, ty) = points[-2], points[-1]
        if py == ty and px < tx:  # the line enters its step from the left
            out += [TextPos(x=tx - EDGE_LABEL_GAP, y=ty - 9, align="right"),
                    TextPos(x=tx - EDGE_LABEL_GAP, y=ty + 9, align="right")]  # fmt: skip
    step = LABEL_CHIP_H + 2
    for k in (1, 2):
        out += [pos.model_copy(update={"y": pos.y - k * step}) for pos in spots]
        out += [pos.model_copy(update={"y": pos.y + k * step}) for pos in spots]
    return out


def _inside(r: Rect, bounds: Rect) -> bool:
    return bounds[0] <= r[0] and bounds[1] <= r[1] and r[2] <= bounds[2] and r[3] <= bounds[3]


def _place_labels(
    edges: list[GraphEdge],
    routes: list[tuple[list[Point], list[TextPos]]],
    nodes: list[Rect],
    bounds: Rect,
) -> list[TextPos | None]:
    """Each label at its first spot that touches no node, no other line and no earlier label.
    When every usual spot covers a step or another label, the first extra spot inside the map
    that covers neither (`_extra_spots`); failing that, the least bad usual spot: crossing a thin
    line is better than covering a label, and covering a label is better than covering a step."""
    placed: list[Rect] = []
    out: list[TextPos | None] = []
    for i, edge in enumerate(edges):
        text = edge.label.strip()
        if not text:
            out.append(None)
            continue
        points, spots = routes[i]
        others = [pts for j, (pts, _) in enumerate(routes) if j != i]

        def cost(pos: TextPos, text: str = text, others: list[list[Point]] = others) -> int:
            r = label_rect(text, pos)
            return (
                100 * sum(_overlaps(r, n) for n in nodes)
                + 10 * sum(_overlaps(r, q) for q in placed)
                + sum(_hits_line(r, pts) for pts in others)
            )

        pos = min(spots, key=cost)  # the first of equals: spots are listed best first
        if cost(pos) >= 10:
            extra = [x for x in _extra_spots(points, spots) if _inside(label_rect(text, x), bounds)]
            better = min(extra, key=cost, default=None)
            if better is not None and cost(better) < 10:
                pos = better
        placed.append(label_rect(text, pos))
        out.append(pos)
    return out


def count_crossings(edges: list[LayoutEdge]) -> int:
    """Places where a horizontal run of one edge crosses a vertical run of another."""
    runs: list[tuple[int, str, int, int, int]] = []  # (edge, "h"/"v", fixed, lo, hi)
    for i, edge in enumerate(edges):
        for (x1, y1), (x2, y2) in pairwise(edge.points):
            if y1 == y2:
                runs.append((i, "h", y1, min(x1, x2), max(x1, x2)))
            elif x1 == x2:
                runs.append((i, "v", x1, min(y1, y2), max(y1, y2)))
    horizontal = [r for r in runs if r[1] == "h"]
    vertical = [r for r in runs if r[1] == "v"]
    return sum(
        1
        for hi, _, y, x_lo, x_hi in horizontal
        for vi, _, x, y_lo, y_hi in vertical
        if hi != vi and x_lo < x < x_hi and y_lo < y < y_hi
    )


def compute_layout(graph: Graph) -> Layout:
    ids = {e.id for e in graph.elements}
    edges = [e for e in graph.edges if e.from_ in ids and e.to in ids]
    graph = graph.model_copy(update={"edges": edges})
    back = back_edge_ids(graph.elements, edges)
    p = _place(graph, back)
    columns = max(p.column.values(), default=-1) + 1

    shapes: dict[str, Shape] = {}
    boxes: dict[str, _Box] = {}
    for e in graph.elements:
        shapes[e.id], boxes[e.id] = _box(e.kind, p.lane_of[e.id], p.column[e.id])

    # Back edges sharing a target enter it side by side.
    sharing: dict[str, list[str]] = {}
    for edge in edges:
        if edge.id in back:
            sharing.setdefault(edge.to, []).append(edge.id)
    offsets = {
        eid: (2 * i - (len(group) - 1)) * SHARED_OFFSET
        for group in sharing.values()
        for i, eid in enumerate(group)
    }
    routes = [_route(e, e.id in back, p, boxes, offsets.get(e.id, 0)) for e in edges]
    node_rects = [(b.x, b.y, b.x + b.w, b.y + b.h) for b in boxes.values()]
    bounds = (LABEL_COL, PHASE_BAND, _col_x(columns), _lane_y(len(p.lanes)))
    texts = _place_labels(edges, routes, node_rects, bounds)
    layout_edges = [
        LayoutEdge(id=e.id, kind=e.kind, is_back_edge=e.id in back, points=points,
                   label=e.label, label_pos=text)
        for e, (points, _), text in zip(edges, routes, texts, strict=True)
    ]  # fmt: skip

    # Text under a node moves right of a line that leaves or enters the node's bottom.
    bottoms = {
        node
        for edge, le in zip(edges, layout_edges, strict=True)
        for node, pt in ((edge.from_, le.points[0]), (edge.to, le.points[-1]))
        if pt == boxes[node].bottom
    }
    nodes: list[LayoutNode] = []
    for e in graph.elements:
        b = boxes[e.id]
        lines = [] if e.kind in STRUCTURAL else wrap_label(e.label)
        side = e.id in bottoms
        under = TextPos(x=b.cx + SIDE_TEXT, y=0, align="left") if side else None
        if e.kind == ElementKind.DECISION.value:
            label_y = b.y + b.h + TEXT_GAP
            label_pos = (under or TextPos(x=b.cx, y=0, align="center")).model_copy(
                update={"y": label_y}
            )
            lens_y = label_y + len(lines) * LABEL_LINE + TEXT_GAP
        else:
            label_pos = TextPos(x=b.cx, y=b.cy - len(lines) * LABEL_LINE // 2, align="center")
            lens_y = b.y + b.h + LENS_GAP
        lens_pos = (under or TextPos(x=b.cx, y=0, align="center")).model_copy(update={"y": lens_y})
        nodes.append(
            LayoutNode(id=e.id, shape=shapes[e.id], x=b.x, y=b.y, w=b.w, h=b.h,
                       label_lines=lines, label_pos=label_pos, lens_pos=lens_pos)
        )  # fmt: skip

    names = {r.id: r.name for r in graph.roles}
    lanes = [
        LayoutLane(
            role_id=role,
            label=names.get(role, ""),
            step_count=sum(
                1 for e in graph.elements if e.kind in STEP_KINDS and p.lane_of[e.id] == i
            ),
            y=_lane_y(i),
            h=LANE_H,
        )
        for i, role in enumerate(p.lanes)
    ]
    return Layout(
        canvas=LayoutCanvas(w=_col_x(columns), h=_lane_y(len(p.lanes))),
        lanes=lanes,
        phases=_phases(graph, p, columns),
        nodes=nodes,
        edges=layout_edges,
    )
