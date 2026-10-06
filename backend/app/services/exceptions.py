"""Exceptions, rework and workarounds (API_CONTRACT.md → GET /versions/{vid}/exceptions; X2,
2026-10-06): how much of a view of the process is the usual route and how much is exception
handling, rework loops and workarounds, from the map's structure and the SME's own words.

Pure and deterministic: explicit inputs (one view's steps and lines, each step with the SME's
words from its verified lived claims, names already hidden), a report out. Never changes the map.

- A step is on the **usual route** when it is reached from the start over forward lines without
  taking an exception exit (`no`, `reject`, `exception`) or entering a variation step. A `no`
  exit counts as usual where the decision's other exit leads into a variation step: the
  variation is the condition and "No" is the normal case ("Busy wave?").
- A **variation step** is a lived alternative tied to a condition ("on a busy wave I walk
  down…"): a step whose lived claim states the condition and which is entered only from
  decisions (§3.12.10 rule 2 makes the condition a decision with the alternative as a branch).
  Steps reached only through one are variation steps too.
- Every other step is on an **exception route**.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Literal

from app.domain.sensemaking import (
    ExceptionEdgeInput,
    ExceptionQuestion,
    ExceptionReport,
    ExceptionRoute,
    ExceptionStep,
    ExceptionStepInput,
    ExceptionSummary,
    ReworkLoop,
    RouteExit,
    StepRoute,
    View,
    Workaround,
)

EXCEPTION_EXITS = {"no", "reject", "exception"}
STRUCTURAL = {"start", "end"}
FREQUENCY_QUESTION = "M5.s2"  # "How often does something like that happen?" (Appendix F)
EXIT_WORDS = {"no": "No", "reject": "Rejected", "exception": "Exception"}


def _reaches(out: dict[str, list[ExceptionEdgeInput]], start: str, goal: str) -> bool:
    seen = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            return True
        for e in out[node]:
            if e.to_id not in seen:
                seen.add(e.to_id)
                queue.append(e.to_id)
    return False


def loop_edges(edges: list[ExceptionEdgeInput]) -> list[ExceptionEdgeInput]:
    """Rework lines, and reject lines that go back to a step leading to them."""
    plain: dict[str, list[ExceptionEdgeInput]] = defaultdict(list)
    for e in edges:
        if e.kind not in ("rework", "reject"):
            plain[e.from_id].append(e)
    return [
        e for e in edges
        if e.kind == "rework" or (e.kind == "reject" and _reaches(plain, e.to_id, e.from_id))
    ]  # fmt: skip


def _first(values: list[str]) -> str:
    return next((v for v in values if v.strip()), "")


def analyse(
    steps: list[ExceptionStepInput],
    edges: list[ExceptionEdgeInput],
    view: View,
    ask: str,
) -> ExceptionReport:
    """The report for one view; `ask` is the bank's wording of M5.s2."""
    by_id = {s.element_id: s for s in steps}
    edges = [e for e in edges if e.from_id in by_id and e.to_id in by_id]
    loops = loop_edges(edges)
    looped = {id(e) for e in loops}
    forward = [e for e in edges if id(e) not in looped]
    out: dict[str, list[ExceptionEdgeInput]] = defaultdict(list)
    into: dict[str, list[ExceptionEdgeInput]] = defaultdict(list)
    for e in forward:
        out[e.from_id].append(e)
        into[e.to_id].append(e)

    deciding = {"decision", "approval"}
    seeds = {
        s.element_id for s in steps
        if s.kind not in STRUCTURAL | {"decision"} and s.condition.strip() and into[s.element_id]
        and all(by_id[e.from_id].kind in deciding for e in into[s.element_id])
    }  # fmt: skip

    starts = [s.element_id for s in steps if s.kind == "start"] or [
        s.element_id for s in steps if not into[s.element_id]
    ]
    usual: set[str] = set(starts)
    queue = deque(starts)
    while queue:
        node = queue.popleft()
        for e in out[node]:
            target = e.to_id
            if target in usual or target in seeds:
                continue
            if e.kind in EXCEPTION_EXITS:
                normal_no = e.kind == "no" and any(
                    x is not e and x.to_id in seeds for x in out[node]
                )
                if not normal_no:
                    continue
            usual.add(target)
            queue.append(target)

    variation: set[str] = set()
    queue = deque(seeds)
    while queue:
        node = queue.popleft()
        if node in variation or node in usual:
            continue
        variation.add(node)
        queue.extend(e.to_id for e in out[node])

    def route_of(element_id: str) -> StepRoute:
        if element_id in usual:
            return "usual"
        return "variation" if element_id in variation else "exception"

    routes: list[ExceptionRoute] = []
    entered: set[str] = set()
    for entry in forward:
        if entry.from_id not in usual or entry.to_id in usual or entry.to_id in entered:
            continue
        if by_id[entry.to_id].kind in STRUCTURAL:
            continue
        entered.add(entry.to_id)
        routes.append(_route(entry, by_id, out, loops, usual, route_of(entry.to_id)))

    in_route = {i: r for r in routes for i in r.element_ids}
    report_steps: list[ExceptionStep] = []
    workarounds: list[Workaround] = []
    for s in steps:
        if s.kind in STRUCTURAL:
            continue
        route = route_of(s.element_id)
        condition = s.condition if route == "variation" and s.condition else (
            in_route[s.element_id].condition if s.element_id in in_route else ""
        )  # fmt: skip
        found = _workaround(s, route, condition)
        if found:
            workarounds.append(found)
        report_steps.append(ExceptionStep(
            element_id=s.element_id, label=s.label, route=route, workaround=found is not None,
            condition=condition,
        ))  # fmt: skip

    questions = [
        ExceptionQuestion(question_id=FREQUENCY_QUESTION, wording=ask,
                          about=f"{r.from_label} → {r.condition}: {' → '.join(r.labels)}")
        for r in routes if not r.frequency
    ]  # fmt: skip
    asked = {i for r in routes if not r.frequency for i in r.element_ids}
    questions += [
        ExceptionQuestion(question_id=FREQUENCY_QUESTION, wording=ask,
                          about=f"the workaround at {w.label}")
        for w in workarounds if not w.frequency and w.element_id not in asked
    ]  # fmt: skip

    counted = [s.route for s in report_steps]
    off = sum(1 for r in counted if r != "usual")
    return ExceptionReport(
        view=view,
        summary=ExceptionSummary(
            steps=len(counted),
            usual_steps=counted.count("usual"),
            exception_steps=counted.count("exception"),
            variation_steps=counted.count("variation"),
            off_usual_share=round(off / len(counted), 2) if counted else 0.0,
            routes=len(routes),
            rework_loops=len(loops),
            workarounds=len(workarounds),
            extra_handoffs=sum(r.handoffs for r in routes),
            frequency_stated=sum(1 for r in routes if r.frequency),
        ),
        steps=report_steps,
        routes=routes,
        loops=[_loop(e, by_id) for e in loops],
        workarounds=workarounds,
        questions=questions,
    )


def _loop(e: ExceptionEdgeInput, by_id: dict[str, ExceptionStepInput]) -> ReworkLoop:
    return ReworkLoop(
        from_element_id=e.from_id, from_label=by_id[e.from_id].label,
        to_element_id=e.to_id, to_label=by_id[e.to_id].label, label=e.label,
    )  # fmt: skip


def _route(
    entry: ExceptionEdgeInput,
    by_id: dict[str, ExceptionStepInput],
    out: dict[str, list[ExceptionEdgeInput]],
    loops: list[ExceptionEdgeInput],
    usual: set[str],
    kind: StepRoute,
) -> ExceptionRoute:
    """The steps reached from an entry before the usual route again, in order, and its exits."""
    order: list[str] = []
    queue = deque([entry.to_id])
    while queue:
        node = queue.popleft()
        if node in order or node in usual or by_id[node].kind in STRUCTURAL:
            continue
        order.append(node)
        queue.extend(e.to_id for e in out[node])
    members = set(order)
    exits: list[RouteExit] = []
    lanes = [by_id[entry.from_id].lane]
    handoffs = 0
    leaves = 0  # each case takes one exit: leaving counts once if any exit changes lane

    def change(a: str, b: str) -> int:
        return 1 if a and b and a != b else 0

    handoffs += change(by_id[entry.from_id].lane, by_id[entry.to_id].lane)
    for node in order:
        here = by_id[node]
        lanes.append(here.lane)
        for e in out[node]:
            target = by_id[e.to_id]
            if e.to_id in members:
                handoffs += change(here.lane, target.lane)
                continue
            ending = target.kind == "end"
            if ending or e.to_id in usual:
                exits.append(RouteExit(kind="ends" if ending else "rejoins", element_id=e.to_id,
                                       label=target.label, edge_label=e.label))  # fmt: skip
                leaves = max(leaves, 0 if ending else change(here.lane, target.lane))
        for e in loops:
            if e.from_id == node:
                exits.append(RouteExit(kind="loops_back", element_id=e.to_id,
                                       label=by_id[e.to_id].label, edge_label=e.label))  # fmt: skip
                leaves = max(leaves, change(here.lane, by_id[e.to_id].lane))
    steps = [by_id[i] for i in order]
    condition = (
        (_first([s.condition for s in steps]) if kind == "variation" else "")
        or entry.label
        or EXIT_WORDS.get(entry.kind, entry.kind)
    )
    return ExceptionRoute(
        id=f"{entry.from_id}>{entry.to_id}",
        kind="variation" if kind == "variation" else "exception",
        from_element_id=entry.from_id,
        from_label=by_id[entry.from_id].label,
        condition=condition,
        element_ids=order,
        labels=[s.label for s in steps],
        lanes=list(dict.fromkeys(x for x in lanes[1:] if x)),
        exits=exits,
        handoffs=handoffs + leaves,
        frequency=_first([s.frequency for s in steps]),
        stated_reason=_first([s.stated_reason for s in steps]),
    )


def _workaround(step: ExceptionStepInput, route: StepRoute, condition: str) -> Workaround | None:
    """A workaround: the SME's own reason for working this way on a variation or practised-only
    step, or a story of type workaround told about the step. A decision is never one: it is the
    routing call, and the work done another way is the step it leads to."""
    basis: Literal["stated_reason", "story"]
    if step.kind == "decision":  # the routing call, not the work done another way
        return None
    if step.stated_reason.strip() and (route == "variation" or step.practiced_only):
        basis = "stated_reason"
    elif step.workaround_story:
        basis = "story"
    else:
        return None
    return Workaround(
        element_id=step.element_id, label=step.label, lane=step.lane, condition=condition,
        stated_reason=step.stated_reason, frequency=step.frequency, basis=basis,
    )  # fmt: skip
