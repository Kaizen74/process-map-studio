"""Registers (PRD §4 Views, §5.4 Registers; API_CONTRACT.md → GET /versions/{vid}/registers).

One payload for the Registers screen: knowledge risk, AI flags, constraints grouped by cause type,
external practice (R steps), validation questions and rejected claims. Read from the version's
graph (names already hidden) and the existing question and rejected-claim views; rejected steps
are left out. Facts only: nothing here is worked out by AI.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import draft as draft_action
from app.actions import questions as questions_action
from app.actions import versions as versions_action
from app.db import session_scope
from app.domain.enums import CauseType, ElementKind, Provenance, ReviewStatus
from app.domain.graph import Graph, GraphElement
from app.domain.models import (
    AiFlagItem,
    ConstraintGroup,
    ConstraintItem,
    ExternalPracticeItem,
    KRiskItem,
    Registers,
)
from app.domain.result import Err, ErrorKind, Ok, Result

Sessions = sessionmaker[Session]

STEPS = {ElementKind.ACTIVITY.value, ElementKind.DECISION.value, ElementKind.APPROVAL.value}
CAUSE_ORDER = [c.value for c in CauseType]


def _steps(graph: Graph) -> list[GraphElement]:
    return [
        e
        for e in graph.elements
        if e.kind in STEPS and e.review_status != ReviewStatus.REJECTED.value
    ]


def _constraints_by_cause(steps: list[GraphElement]) -> list[ConstraintGroup]:
    groups: dict[str | None, list[ConstraintItem]] = {}
    for step in steps:
        for c in step.constraints:
            item = ConstraintItem(
                element_id=step.id,
                label=step.label,
                text=c.text,
                is_key=c.is_key,
                provenance=c.provenance,
            )
            groups.setdefault(c.cause_type or None, []).append(item)
    order = [*CAUSE_ORDER, *sorted(k for k in groups if k and k not in CAUSE_ORDER), None]
    return [
        # Key constraints first; otherwise process order (a stable sort keeps it).
        ConstraintGroup(cause_type=k, constraints=sorted(groups[k], key=lambda i: not i.is_key))
        for k in order
        if k in groups
    ]


RegisterLists = tuple[
    list[KRiskItem], list[AiFlagItem], list[ConstraintGroup], list[ExternalPracticeItem]
]


def build_registers(graph: Graph) -> RegisterLists:
    """The four registers read from the graph: K-RISK, AI flags, constraints, external practice."""
    lanes = {r.id: r.name for r in graph.roles}
    steps = _steps(graph)
    k_risk = [
        KRiskItem(
            element_id=s.id,
            label=s.label,
            lane=lanes.get(s.lane_role_id or "", ""),
            k_risk=s.k_risk,
        )
        for s in steps
        if s.k_risk.strip()
    ]
    flags = [
        AiFlagItem(
            element_id=s.id,
            label=s.label,
            lane=lanes.get(s.lane_role_id or "", ""),
            mechanism=s.decision.mechanism,
            **s.ai_flag.model_dump(),
        )
        for s in steps
        if s.ai_flag is not None
    ]
    external = [
        ExternalPracticeItem(element_id=s.id, label=s.label, r_reference=s.r_reference)
        for s in steps
        if s.provenance == Provenance.RECOMMENDED.value
    ]
    return k_risk, flags, _constraints_by_cause(steps), external


def get_registers(sessions: Sessions, version_id: str) -> Result[Registers]:
    with session_scope(sessions) as session:
        graph = versions_action.build_graph(session, version_id)
    if graph is None:
        return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
    match questions_action.list_questions(sessions, version_id):
        case Err() as err:
            return err
        case Ok(value=questions):
            pass
    match draft_action.rejected_claims(sessions, version_id):
        case Err() as err:
            return err
        case Ok(value=rejected):
            pass
    k_risk, flags, constraints, external = build_registers(graph)
    return Ok(
        Registers(
            k_risk=k_risk,
            ai_flags=flags,
            constraints_by_cause=constraints,
            external_practice=external,
            questions=questions,
            rejected_claims=rejected,
        )
    )
