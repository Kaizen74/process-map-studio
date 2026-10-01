"""Quality lint (PRD §3.7 lint rules L1-L12): deterministic checks over the graph, no database.

`run_lint` checks the map as one (both views' steps); `run_view_checks` checks each view on its
own (§3.12.11): every step reachable from the start, every step but the end with a way out, every
exit drawn labelled; "not described" connectors and lines resting only on the order of mentioning
are warnings (each also raises a validation question).

Rejected elements are not on the map: they and their edges are left out before checking, so a
step whose only connection was rejected shows up as an orphan (L9). Line crossings need the
layout (`services/layout.py`), so that warning is checked only when a layout is given.
"""

from __future__ import annotations

from collections import deque

from app.domain.enums import (
    AiBasis,
    DecisionMechanism,
    EdgeKind,
    ElementKind,
    Provenance,
    RaciLetter,
    ReviewStatus,
    Stance,
)
from app.domain.graph import Graph, GraphEdge, GraphElement, LintIssue, LintReport
from app.domain.layout import Layout
from app.services.layout import count_crossings
from app.services.views import NAMES, VIEWS, view_graph

MAX_STEPS = 25
MAX_LANES = 6
AI_FLAGS_RANGE = (3, 7)
MAX_CROSSINGS = 3
STEP_KINDS = {ElementKind.ACTIVITY.value, ElementKind.DECISION.value, ElementKind.APPROVAL.value}
TIMED_KINDS = {ElementKind.ACTIVITY.value, ElementKind.APPROVAL.value}
PROVENANCES = {p.value for p in Provenance}
EVIDENCED = {Provenance.OBSERVED.value, Provenance.INFERRED.value}
REJECT_EXITS = {EdgeKind.REJECT.value, EdgeKind.REWORK.value}


def _name(element: GraphElement) -> str:
    return f'{element.kind.capitalize()} "{element.label}"'


def _letters(element: GraphElement, letter: str) -> list[str]:
    return [r.role_id for r in element.raci if r.letter == letter]


def _reachable(start: str, edges: list[GraphEdge]) -> set[str]:
    seen = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for edge in edges:
            if edge.from_ == current and edge.to not in seen:
                seen.add(edge.to)
                queue.append(edge.to)
    return seen


def run_lint(graph: Graph, layout: Layout | None = None) -> LintReport:
    elements = [e for e in graph.elements if e.review_status != ReviewStatus.REJECTED.value]
    ids = {e.id for e in elements}
    edges = [e for e in graph.edges if e.from_ in ids and e.to in ids]
    roles = {r.id: r.name for r in graph.roles}
    failures: list[LintIssue] = []
    warnings: list[LintIssue] = []

    def fail(rule: str, element: GraphElement | None, message: str) -> None:
        failures.append(LintIssue(rule=rule, element_id=element.id if element else None,
                                  message=message))  # fmt: skip

    def warn(rule: str, element: GraphElement | None, message: str) -> None:
        warnings.append(LintIssue(rule=rule, element_id=element.id if element else None,
                                  message=message))  # fmt: skip

    def role(role_id: str | None) -> str:
        return roles.get(role_id or "", "no role")

    starts = [e for e in elements if e.kind == ElementKind.START.value]
    for e in elements:
        outgoing = [edge for edge in edges if edge.from_ == e.id]
        step = e.kind in STEP_KINDS
        # L1-L3: provenance and its evidence or reference.
        if e.provenance not in PROVENANCES:
            fail("L1", e, f"{_name(e)} has no provenance (O, I or R).")
        if (
            step
            and e.provenance in EVIDENCED
            and not any(
                ev.verified and ev.segment_id and ev.stance != Stance.SILENT.value
                for ev in e.evidence
            )
        ):
            fail("L2", e, f"{_name(e)} has no verified evidence from a source.")
        if e.provenance == Provenance.RECOMMENDED.value and not e.r_reference.strip():
            fail("L3", e, f"{_name(e)} is a recommendation (R) without a reference.")
        # L4-L5: every exit labelled.
        if e.kind == ElementKind.DECISION.value:
            labelled = [edge for edge in outgoing if edge.label.strip()]
            if len(labelled) < 2:
                fail("L4", e, f"{_name(e)} needs at least two labelled exits; it has "
                              f"{len(labelled)}.")  # fmt: skip
        if e.kind == ElementKind.APPROVAL.value:
            kinds = {edge.kind for edge in outgoing}
            if EdgeKind.APPROVE.value not in kinds or not kinds & REJECT_EXITS:
                fail("L5", e, f"{_name(e)} needs an approve exit and a reject or rework exit.")
        # L6-L8: the lane rule.
        responsible, accountable = (
            _letters(e, RaciLetter.RESPONSIBLE.value),
            _letters(e, RaciLetter.ACCOUNTABLE.value),
        )
        if e.kind == ElementKind.ACTIVITY.value:
            if len(responsible) != 1:
                fail("L6", e, f"{_name(e)} needs exactly one Responsible role; it has "
                              f"{len(responsible)}.")  # fmt: skip
            elif e.lane_role_id != responsible[0]:
                fail("L6", e, f"{_name(e)} sits in the {role(e.lane_role_id)} lane but its "
                              f"Responsible role is {role(responsible[0])}.")  # fmt: skip
        if e.kind == ElementKind.APPROVAL.value:
            contested_a = [r.role_id for r in e.raci if r.letter == "A" and r.contested]
            if contested_a:
                if e.lane_role_id not in contested_a or "ownership" not in e.divergence_types:
                    fail("L7", e, f"{_name(e)} has contested accountability: it must sit in "
                                  "one of the competing lanes and be marked as an ownership "
                                  "divergence.")  # fmt: skip
            elif len(accountable) == 1 and e.lane_role_id != accountable[0]:
                fail("L7", e, f"{_name(e)} sits in the {role(e.lane_role_id)} lane but is "
                              f"approved by {role(accountable[0])}.")  # fmt: skip
        if e.kind == ElementKind.DECISION.value and e.lane_role_id != e.decision.decider_role_id:
            fail("L8", e, f"{_name(e)} sits in the {role(e.lane_role_id)} lane but the call is "
                          f"made by {role(e.decision.decider_role_id)}.")  # fmt: skip
        # L9 (outgoing half): every element except the end leads somewhere.
        if e.kind != ElementKind.END.value and not outgoing:
            fail("L9", e, f"{_name(e)} has no way out (no outgoing connection).")
        # L10: AI flags are complete and never automate a judgment.
        if e.ai_flag is not None:
            flag = e.ai_flag
            missing = [
                name
                for name, value in (("component", flag.component), ("input", flag.input),
                                    ("output", flag.output), ("handoff", flag.handoff),
                                    ("basis", flag.basis))
                if not value.strip()
            ]  # fmt: skip
            if missing:
                fail("L10", e, f"The AI flag on {_name(e)} is missing: {', '.join(missing)}.")
            if (
                flag.basis == AiBasis.RULE_BASED_AUTOMATE_CANDIDATE.value
                and e.decision.mechanism == DecisionMechanism.JUDGMENT.value
            ):
                fail("L10", e, f"{_name(e)} is a judgment step, so it can't be flagged for "
                               "automation.")  # fmt: skip
        # L11: exactly one Accountable, or several all marked contested.
        if step:
            contested = [r for r in e.raci if r.letter == "A" and r.contested]
            if len(accountable) == 0:
                fail("L11", e, f"{_name(e)} has no Accountable role.")
            elif len(accountable) > 1 and len(contested) != len(accountable):
                fail("L11", e, f"{_name(e)} has {len(accountable)} Accountable roles; only one "
                               "is allowed unless they are marked contested.")  # fmt: skip

    # L9 (reachable half): every element except start can be reached from the start.
    if len(starts) != 1:
        fail("L9", None, f"The map needs exactly one start; it has {len(starts)}.")
    else:
        reached = _reachable(starts[0].id, edges)
        for e in elements:
            if e.id not in reached:
                fail("L9", e, f"{_name(e)} can't be reached from the start.")

    # L12 warnings: size, time, KPIs, number of AI flags, line crossings.
    steps = [e for e in elements if e.kind in STEP_KINDS]
    lanes = {e.lane_role_id for e in steps if e.lane_role_id}
    if len(steps) > MAX_STEPS or len(lanes) > MAX_LANES:
        warn("L12", None, f"Large map ({len(steps)} steps, {len(lanes)} lanes): consider "
                          "splitting by phase.")  # fmt: skip
    for e in steps:
        if e.kind in TIMED_KINDS and e.time.work_min is None and e.time.wait_min is None:
            warn("L12", e, f"{_name(e)} has no time stated.")
    no_kpi = [e for e in steps if e.kind == ElementKind.ACTIVITY.value and not e.kpi.strip()]
    if no_kpi and graph.process.kpi.strip():
        warn("L12", None, f"{len(no_kpi)} activities have no KPI while the process has one.")
    flags = sum(1 for e in elements if e.ai_flag is not None)
    low, high = AI_FLAGS_RANGE
    if not low <= flags <= high:
        warn("L12", None, f"{flags} AI flags; aim for {low} to {high}.")
    if layout is not None:
        shown = {e.id for e in edges}
        crossings = count_crossings([e for e in layout.edges if e.id in shown])
        if crossings > MAX_CROSSINGS:
            warn("L12", None, f"The map has {crossings} line crossings; consider changing the "
                              "lane order.")  # fmt: skip
    return LintReport(failures=failures, warnings=warnings)


DECIDING = {ElementKind.DECISION.value, ElementKind.APPROVAL.value}


def run_view_checks(graph: Graph) -> LintReport:
    """The flow checks of each view (§3.12.11) on the graph with every line. A decision or
    approval keeps its at-least-two-exits rule on the whole map (L4, L5): a view may leave out an
    exit whose next step is only in the other view, but every exit it draws must be labelled."""
    failures: list[LintIssue] = []
    warnings: list[LintIssue] = []
    for view in VIEWS:
        shown = view_graph(graph, view)
        elements = [e for e in shown.elements if e.review_status != ReviewStatus.REJECTED.value]
        ids = {e.id for e in elements}
        edges = [e for e in shown.edges if e.from_ in ids and e.to in ids]
        name = NAMES[view]

        def fail(
            rule: str,
            element: GraphElement | None,
            message: str,
            name: str = name,
            view: str = view,
        ) -> None:
            failures.append(LintIssue(rule=rule, element_id=element.id if element else None,
                                      message=f"{name}: {message}", view=view))  # fmt: skip

        starts = [e for e in elements if e.kind == ElementKind.START.value]
        if len(starts) != 1:
            continue  # the start is in both views; the map as one already reports it (L9)
        reached = _reachable(starts[0].id, edges)
        for e in elements:
            outgoing = [edge for edge in edges if edge.from_ == e.id]
            if e.id not in reached:
                fail("L9", e, f"{_name(e)} can't be reached from the start.")
            if e.kind != ElementKind.END.value and not outgoing:
                fail("L9", e, f"{_name(e)} has no way out (no outgoing connection).")
            if e.kind in DECIDING:
                unlabelled = [edge for edge in outgoing if not edge.label.strip()]
                if unlabelled:
                    fail("L4" if e.kind == ElementKind.DECISION.value else "L5", e,
                         f"{_name(e)} has {len(unlabelled)} unlabelled exit(s).")  # fmt: skip
        gaps = [edge for edge in edges if edge.kind == EdgeKind.GAP.value]
        if gaps:
            warnings.append(LintIssue(rule="L12", element_id=None, view=view,
                                      message=f"{name}: {len(gaps)} \"not described\" "
                                      "connector(s): the interview doesn't say what happens "
                                      "there."))  # fmt: skip
    labels = {e.id: e.label for e in graph.elements}
    for edge in graph.edges:
        if edge.sequence_basis == "narration_order":
            warnings.append(LintIssue(
                rule="L12", element_id=edge.to,
                message=f'The line from "{labels.get(edge.from_, "")}" to '
                f'"{labels.get(edge.to, "")}" rests only on the order the sources mention them.',
            ))  # fmt: skip
    return LintReport(failures=failures, warnings=warnings)
