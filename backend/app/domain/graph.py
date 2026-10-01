"""The map as stored (PRD §3.5) and as returned (the graph JSON, PRD §3.6).

Records mirror the map tables one to one and are what `repositories/elements.py` reads and
writes. `Graph` is the intermediate representation: the graph endpoint, the lint rules, the layout
(P5) and the exports (P7) all read it. It never carries images, verbatim quotes or names.
"""

from __future__ import annotations

from typing import Any

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
    # PRD v1.10 (§3.12; columns from migration 0009).
    work_type: str | None = None  # B.29
    constraint_type: str | None = None  # B.30
    work_type_basis: list[Any] | None = None
    sme_work_type_signifier: str | None = None
    work_type_status: str | None = None
    view_membership: str | None = None  # B.35
    variants: dict[str, Any] | None = None  # {"done": {owner, threshold, time, trigger}, ...}
    level: str | None = None  # B.39
    parent_element_id: str | None = None


class EdgeRecord(Record):
    from_element_id: str
    to_element_id: str
    kind: str  # B.8
    label: str = ""
    provenance: str = "O"
    # PRD v1.10 (§3.12.10, §3.12.11; columns from migration 0009).
    sequence_basis: str | None = None  # B.34
    typical: bool | None = None
    view_membership: str | None = None  # B.35
    information_payload: str | None = None


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


class AccountSummary(Out):
    """The accounts a step's interview claims give (§3.12.3, B.28)."""

    official: int = 0
    lived: int = 0
    unclear: int = 0


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
    # v1.10 (§3.12.3): the accounts its interview claims give; practice_described False marks
    # "Practice not described" (only the official account), None when the interview is silent.
    account_summary: AccountSummary = AccountSummary()
    practice_described: bool | None = None
    # §3.12.11: where the views differ on this step, both values (owner, threshold, time,
    # trigger): {"done": {...}, "documented": {...}}; null when they don't.
    variants: dict[str, dict[str, str]] | None = None
    # §3.12.11 (B.35): both · done_only · documented_only; null on maps drafted before v1.10.
    view_membership: str | None = None
    # §3.12.4 (B.29, B.30; C2): the kind of work, its constraint type, the quoted cues
    # [{segment_ids, quote}] and proposed · confirmed · not_classified; null before v1.10.
    work_type: str | None = None
    constraint_type: str | None = None
    work_type_basis: list[dict[str, Any]] = []
    work_type_status: str | None = None


class GraphEdge(Out):
    id: str
    from_: str = Field(serialization_alias="from", validation_alias=AliasChoices("from", "from_"))
    to: str
    kind: str
    label: str
    # §3.12.10-3.12.11 (B.34, B.35): why the line is there and which views draw it; null on maps
    # drafted before v1.10 and on lines Eric added.
    sequence_basis: str | None = None
    view_membership: str | None = None
    information_payload: str | None = None
    typical: bool | None = None
    provenance: str = "O"  # I: added by the translation for one view (§3.12.10 rules 1 and 7)


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
    view: str | None = None  # v1.10 §3.12.11: "done" or "documented" for a per-view check


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


class AnswerQuote(Out):
    """One interview answer behind a step: the quote, the account it gives and its cue, the SME's
    stated reason and variation condition, where it is, and the question that prompted it."""

    quote: str
    account_type: str
    account_cue: str
    stated_reason: str
    variation_condition: str
    source_id: str
    segment_id: str | None
    anchor: str
    question_id: str | None
    question: str


class AshenItem(Out):
    """One know-how item at a knowledge disclosure point, with the passage that shows it."""

    text: str
    quote: str
    role: str  # the speaker's role, never a person (§3.12.6: natural talent at role level only)
    source_id: str
    segment_id: str | None
    anchor: str


class KnowHow(Out):
    """§3.12.6 (C2b): the ASHEN profile of a knowledge disclosure point, its computed knowledge
    risk and why, and the decision's cadence and information in and out (§3.12.10 rule 4)."""

    kdp_type: str  # decision · judgment
    ashen: dict[str, list[AshenItem]]
    knowledge_risk: str  # high · medium · low · unknown
    risk_reason: str
    cadence: str | None = None
    received: list[str] = []
    attended: list[str] = []
    wanted: list[str] = []
    communicated_via: list[str] = []


class StoryCard(Out):
    """§3.12.2 (C2b): a fragment the SME told, with their own words for it; kept when told once."""

    label: str
    fragment_type: str
    signifiers: list[str]
    frequency: str
    single_account: bool
    quote: str
    source_id: str
    segment_id: str | None
    anchor: str


class CapabilityNote(Out):
    """Rule 10 (C3): a strength to preserve or a weakness to improve, as the SME named it."""

    kind: str  # strength (Preserve) · weakness (Improve)
    dimension: str  # B.36
    text: str
    cause_type: str | None
    steps: list[str]
    quote: str
    source_id: str
    segment_id: str | None
    anchor: str


class GlossaryEntry(Out):
    term: str
    plain_meaning: str
    steps: list[str]
    source_id: str
    segment_id: str | None
    anchor: str


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
    account_summary: AccountSummary = AccountSummary()
    practice_described: bool | None = None
    variants: dict[str, dict[str, str]] | None = None
    view_membership: str | None = None
    work_type: str | None = None
    constraint_type: str | None = None
    work_type_basis: list[dict[str, Any]] = []
    work_type_status: str | None = None
    # v1.10 (§3.12.10 rule 6, §5.7.7 4d; acceptance criterion 66): the interview answers the step
    # was translated from, each with the guide question that prompted it. App only, never exported.
    answers: list[AnswerQuote] = []
    know_how: KnowHow | None = None
    stories: list[StoryCard] = []


# --- Alignment matrix (PRD §4 Views, §5.4 Matrix; phase P9) ------------------------------------


class AlignmentRow(Out):
    """How each kind of source stands on one step: supports · contradicts · silent ·
    not_applicable (no source of that kind)."""

    element_id: str
    label: str
    kind: str
    sop: str
    interview: str
    jd: str
    artefact: str
    state: str
    divergence_types: list[str]
