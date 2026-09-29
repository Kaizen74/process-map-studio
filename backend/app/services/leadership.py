"""The leadership view (PRD §4 Views, §5.4 Leadership; phase P11), worked out from a version's
graph. Deterministic, no AI, no database. Only steps count (activities, decisions, approvals), never
rejected ones; every figure carries the IDs of the steps behind it.

- Facts, per phase: work and wait minutes; rework loops (lines of kind rework or reject leaving a
  step of the phase); cross-lane handoffs (lines between two steps in different lanes, counted in
  the phase of the step they leave); divergence counts by type.
- Interpretation, per cause type (B.9) on the steps' constraints: **systemic** when it constrains 2+
  steps that sit in different lanes or different phases (not one team's local issue), else
  **local**; evidence weight = sources supporting at least one of those steps, of all sources the
  version was drafted from; confidence = the average of those steps' own confidence.
- Recommendation: wait on steps constrained by a systemic cause (recoverable), all rework loops, up
  to three AI flags (rule-based decisions first, then by confidence) and one "Decision needed" line
  per systemic cause.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.domain.enums import (
    CauseType,
    DecisionMechanism,
    EdgeKind,
    ElementKind,
    ReviewStatus,
    Stance,
)
from app.domain.graph import Graph, GraphElement
from app.domain.leadership import (
    CauseConstraint,
    CauseSummary,
    DecisionNeeded,
    EvidenceWeight,
    Facts,
    Interpretation,
    LeadershipAiFlag,
    LeadershipVersion,
    LeadershipView,
    PhaseFacts,
    PhaseLinks,
    PhaseRef,
    Recommendation,
)

STEPS = {ElementKind.ACTIVITY.value, ElementKind.DECISION.value, ElementKind.APPROVAL.value}
LOOPS = {EdgeKind.REWORK.value, EdgeKind.REJECT.value}
CAUSE_ORDER = [c.value for c in CauseType]
NO_PHASE = "No phase"
TOP_AI_FLAGS = 3


def steps_of(graph: Graph) -> list[GraphElement]:
    return [
        e
        for e in graph.elements
        if e.kind in STEPS and e.review_status != ReviewStatus.REJECTED.value
    ]


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _facts(graph: Graph, steps: list[GraphElement]) -> Facts:
    by_id = {e.id: e for e in steps}
    ordered = sorted(graph.phases, key=lambda p: (p.order, p.name))
    keys: list[str | None] = [p.id for p in ordered]
    if any(e.phase_id not in {p.id for p in ordered} for e in steps):
        keys.append(None)
    names = {p.id: p.name for p in ordered}
    phases: list[PhaseFacts] = []
    for key in keys:
        mine = [e for e in steps if (e.phase_id if e.phase_id in names else None) == key]
        ids = {e.id for e in mine}
        loops = [
            x.from_ for x in graph.edges if x.kind in LOOPS and x.from_ in ids and x.to in by_id
        ]
        handoffs = [
            x.from_
            for x in graph.edges
            if x.from_ in ids
            and x.to in by_id
            and by_id[x.from_].lane_role_id != by_id[x.to].lane_role_id
        ]
        divergence: dict[str, list[str]] = {}
        for e in mine:
            for kind in e.divergence_types:
                divergence.setdefault(kind, []).append(e.id)
        phases.append(
            PhaseFacts(
                phase_id=key,
                name=names.get(key or "", NO_PHASE),
                work_min=sum(e.time.work_min or 0 for e in mine),
                wait_min=sum(e.time.wait_min or 0 for e in mine),
                rework_loops=len(loops),
                handoffs=len(handoffs),
                divergence_counts={k: len(v) for k, v in divergence.items()},
                links=PhaseLinks(
                    work=[e.id for e in mine if e.time.work_min],
                    wait=[e.id for e in mine if e.time.wait_min],
                    rework_loops=list(dict.fromkeys(loops)),
                    handoffs=list(dict.fromkeys(handoffs)),
                    divergence=divergence,
                ),
            )
        )
    sources = {ev.source_id for e in steps for ev in e.evidence}
    return Facts(phases=phases, sources=len(sources))


def _causes(graph: Graph, steps: list[GraphElement], sources: int) -> list[CauseSummary]:
    lanes = {r.id: r.name for r in graph.roles}
    phases = {p.id: p for p in graph.phases}
    found: dict[str, list[GraphElement]] = {}
    for e in steps:
        for c in e.constraints:
            if c.cause_type and e not in found.setdefault(c.cause_type, []):
                found[c.cause_type].append(e)
    out: list[CauseSummary] = []
    for cause in sorted(found, key=lambda c: (CAUSE_ORDER.index(c) if c in CAUSE_ORDER else 99, c)):
        mine = found[cause]
        lane_names = list(dict.fromkeys(lanes.get(e.lane_role_id or "", "") for e in mine))
        phase_ids = list(dict.fromkeys(e.phase_id for e in mine))
        systemic = len(mine) >= 2 and (len(lane_names) >= 2 or len(phase_ids) >= 2)
        where = (
            f"{len(lane_names)} lanes: {', '.join(n for n in lane_names if n)}"
            if len(lane_names) >= 2
            else f"{len(phase_ids)} phases"
        )
        reason = (
            f"On {_plural(len(mine), 'step')} in {where}."
            if systemic
            else f"On {_plural(len(mine), 'step')}"
            + (f" in one lane ({lane_names[0]})" if lane_names and lane_names[0] else "")
            + "."
        )
        supporting = {
            ev.source_id
            for e in mine
            for ev in e.evidence
            if ev.stance == Stance.SUPPORTS.value and ev.verified
        }
        known = [e.confidence for e in mine if e.confidence is not None]
        out.append(
            CauseSummary(
                cause_type=cause,
                systemic=systemic,
                reason=reason,
                phases=[
                    PhaseRef(phase_id=pid, name=phases[pid].name if pid in phases else NO_PHASE)
                    for pid in phase_ids
                ],
                lanes=[n for n in lane_names if n],
                evidence_weight=EvidenceWeight(supporting=len(supporting), sources=sources),
                confidence=round(sum(known) / len(known), 2) if known else None,
                constraints=[
                    CauseConstraint(element_id=e.id, label=e.label, text=c.text, is_key=c.is_key)
                    for e in mine
                    for c in e.constraints
                    if c.cause_type == cause
                ],
                element_ids=[e.id for e in mine],
            )
        )
    return out


def _ai_flags(graph: Graph, steps: list[GraphElement]) -> list[LeadershipAiFlag]:
    lanes = {r.id: r.name for r in graph.roles}
    flagged = [e for e in steps if e.ai_flag is not None]
    order = {e.id: n for n, e in enumerate(flagged)}
    flagged.sort(
        key=lambda e: (
            e.decision.mechanism != DecisionMechanism.RULE_BASED.value,
            -(e.confidence or 0),
            order[e.id],
        )
    )
    return [
        LeadershipAiFlag(
            element_id=e.id,
            label=e.label,
            lane=lanes.get(e.lane_role_id or "", ""),
            mechanism=e.decision.mechanism,
            component=e.ai_flag.component,
            input=e.ai_flag.input,
            output=e.ai_flag.output,
            handoff=e.ai_flag.handoff,
            basis=e.ai_flag.basis,
        )
        for e in flagged[:TOP_AI_FLAGS]
        if e.ai_flag is not None
    ]


def leadership_view(graph: Graph, decisions: Mapping[str, str]) -> LeadershipView:
    """The three parts for one version; `decisions` are Eric's saved lines by cause type."""
    steps = steps_of(graph)
    facts = _facts(graph, steps)
    causes = _causes(graph, steps, facts.sources)
    systemic = [c for c in causes if c.systemic]
    by_id = {e.id: e for e in steps}
    recoverable = list(
        dict.fromkeys(e for c in systemic for e in c.element_ids if by_id[e].time.wait_min)
    )
    loops = [x for p in facts.phases for x in p.links.rework_loops]
    return LeadershipView(
        version=LeadershipVersion(
            id=graph.version.id, label=graph.version.label, state=graph.version.state
        ),
        facts=facts,
        interpretation=Interpretation(causes=causes),
        recommendation=Recommendation(
            recoverable_wait_min=sum(by_id[e].time.wait_min or 0 for e in recoverable),
            recoverable_wait_element_ids=recoverable,
            rework_loops=sum(p.rework_loops for p in facts.phases),
            rework_element_ids=list(dict.fromkeys(loops)),
            ai_flags=_ai_flags(graph, steps),
            decisions_needed=[
                DecisionNeeded(cause_type=c.cause_type, text=decisions.get(c.cause_type, ""))
                for c in systemic
            ],
        ),
    )
