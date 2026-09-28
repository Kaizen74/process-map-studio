"""The map as stored (PRD §3.5) and as returned (the graph JSON, PRD §3.6).

Records mirror the map tables one to one and are what `repositories/elements.py` reads and
writes. `Graph` is the intermediate representation: the graph endpoint, the lint rules, the layout
(P5) and the exports (P7) all read it. It never carries images, verbatim quotes or names.
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

# --- Stored records ----------------------------------------------------------------------------


class Record(BaseModel):
    """A stored row; `id` is empty until the repository has saved it."""

    model_config = ConfigDict(from_attributes=True)

    id: str = ""


class PhaseRecord(Record):
    name: str
    time_window: str = ""
    sort_order: int = 0


class ElementRecord(Record):
    stable_key: str
    kind: str  # B.2
    label: str
    lane_role_id: str | None = None
    phase_id: str | None = None
    work_min: float | None = None
    wait_min: float | None = None
    duration_text: str = ""
    complexity: str | None = None
    kpi: str = ""
    decision_mechanism: str = "none"  # B.6
    decider_role_id: str | None = None
    rule_or_threshold: str = ""
    escalation: str = ""
    handoff_in: str = ""
    handoff_out: str = ""
    provenance: str  # B.3
    r_reference: str = ""
    source_state: str = "not_assessed"  # B.4
    divergence_types: list[str] = []
    k_risk: str = ""
    confidence: float | None = None
    confidence_breakdown: list[dict[str, object]] = []
    needs_check: bool = False
    review_status: str = "draft"  # B.7


class EdgeRecord(Record):
    from_element_id: str
    to_element_id: str
    kind: str  # B.8
    label: str = ""
    provenance: str = "O"


class RaciRecord(Record):
    element_id: str
    role_id: str
    letter: str  # B.10
    contested: bool = False
    provenance: str = "O"


class EvidenceRecord(Record):
    element_id: str | None = None
    raci_id: str | None = None
    segment_id: str
    source_kind: str  # B.1
    stance: str  # B.14
    verified: bool = False
    quote: str = ""
    note: str = ""


class ConstraintRecord(Record):
    element_id: str
    text: str
    provenance: str
    cause_type: str | None = None  # B.9
    is_key: bool = False


class AiFlagRecord(Record):
    element_id: str
    component: str  # B.11
    input: str = ""
    output: str = ""
    handoff: str = ""
    basis: str  # B.12


class MergeGroup(BaseModel):
    """One step a merge proposal covers, as S2 drafted it."""

    label: str
    kind: str
    lane_role_id: str | None = None
    claim_ids: list[str]


class MergeProposalRecord(Record):
    claim_ids: list[str]
    proposed_label: str
    similarity: float
    decision: str = "pending"  # B.15
    decided_at: str | None = None
    claim_groups: list[MergeGroup] = []


class QuestionRecord(Record):
    element_id: str | None = None
    phase_id: str | None = None
    question: str
    reason: str
    origin_ref: str = ""
    status: str = "open"


class EvidencePassage(BaseModel):
    """An evidence link with what its passage needs for an anchor (read side only)."""

    evidence: EvidenceRecord
    source_id: str
    source_name: str
    source_format: str
    seq: int
    page: int | None
    section: str
    text: str
    start_ms: int | None


# --- The graph JSON (PRD §3.6) -----------------------------------------------------------------


class Out(BaseModel):
    """Graph parts: field names that are Python keywords are written with their JSON name, and
    read by either name (so an export or a stored graph can be read back)."""

    model_config = ConfigDict(
        serialize_by_alias=True, validate_by_name=True, validate_by_alias=True
    )


class GraphVersion(Out):
    id: str
    label: str
    state: str
    quality_card: dict[str, object] | None = None


class CycleTime(Out):
    elapsed_min: float
    work_min: float
    incomplete_steps: int


class GraphProcess(Out):
    name: str
    trigger: str
    end_point: str
    kpi: str
    cycle_time: CycleTime


class GraphRole(Out):
    id: str
    name: str
    is_system: bool
    lane_order: int | None


class GraphPhase(Out):
    id: str
    name: str
    time_window: str
    order: int


class GraphTime(Out):
    work_min: float | None
    wait_min: float | None
    text: str


class GraphDecision(Out):
    mechanism: str
    decider_role_id: str | None
    rule_or_threshold: str
    escalation: str


class GraphHandoff(Out):
    in_: str = Field(serialization_alias="in", validation_alias=AliasChoices("in", "in_"))
    out: str


class GraphRaci(Out):
    role_id: str
    letter: str
    contested: bool


class GraphConstraint(Out):
    text: str
    provenance: str
    cause_type: str | None
    is_key: bool


class GraphAiFlag(Out):
    component: str
    input: str
    output: str
    handoff: str
    basis: str


class GraphEvidence(Out):
    """One source's stance on the element. Silent sources have no passage (segment_id null)."""

    segment_id: str | None
    source_id: str
    source_kind: str
    stance: str
    anchor: str
    verified: bool
    note: str = ""


class GraphElement(Out):
    id: str
    stable_key: str
    kind: str
    label: str
    lane_role_id: str | None
    phase_id: str | None
    time: GraphTime
    complexity: str | None
    kpi: str
    decision: GraphDecision
    handoff: GraphHandoff
    raci: list[GraphRaci]
    provenance: str
    r_reference: str
    source_state: str
    divergence_types: list[str]
    constraints: list[GraphConstraint]
    k_risk: str
    ai_flag: GraphAiFlag | None
    evidence: list[GraphEvidence]
    confidence: float | None
    confidence_breakdown: list[dict[str, object]]
    needs_check: bool
    review_status: str


class GraphEdge(Out):
    id: str
    from_: str = Field(serialization_alias="from", validation_alias=AliasChoices("from", "from_"))
    to: str
    kind: str
    label: str


class Graph(Out):
    version: GraphVersion
    process: GraphProcess
    roles: list[GraphRole]
    phases: list[GraphPhase]
    elements: list[GraphElement]
    edges: list[GraphEdge]


# --- Lint (PRD §3.7 lint rules) ----------------------------------------------------------------


class LintIssue(Out):
    rule: str  # L1 … L12
    element_id: str | None
    message: str


class LintReport(Out):
    """Hard failures block publishing; warnings are listed beneath the quality card."""

    failures: list[LintIssue]
    warnings: list[LintIssue]


# --- One element for the detail panel (PRD §4 element responses, §5.7.7) ------------------------


class EvidenceCard(Out):
    segment_id: str | None
    source_id: str
    source_name: str
    source_kind: str
    stance: str
    anchor: str
    verified: bool
    quote: str
    note: str


class RaciSource(Out):
    source_name: str
    source_kind: str
    anchor: str


class RaciDetail(Out):
    role_id: str
    role_name: str
    letter: str
    contested: bool
    sources: list[RaciSource]


class ElementDetail(Out):
    """The graph element, with names, quotes and source names for the panel (never exported)."""

    id: str
    version_id: str
    stable_key: str
    kind: str
    label: str
    lane_role_id: str | None
    lane_role_name: str
    phase_id: str | None
    phase_name: str
    time: GraphTime
    complexity: str | None
    kpi: str
    decision: GraphDecision
    decider_role_name: str
    handoff: GraphHandoff
    raci: list[RaciDetail]
    provenance: str
    r_reference: str
    source_state: str
    divergence_types: list[str]
    constraints: list[GraphConstraint]
    k_risk: str
    ai_flag: GraphAiFlag | None
    evidence: list[EvidenceCard]
    confidence: float | None
    confidence_breakdown: list[dict[str, object]]
    needs_check: bool
    review_status: str
    image_count: int
    gap_findings: list[dict[str, object]]
