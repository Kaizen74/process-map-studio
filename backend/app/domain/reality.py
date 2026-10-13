"""Models for the intent layer and the Reality views (PRD §3.16-3.18; phase P13)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class IntentRecord(BaseModel):
    """An `intent_statements` row as stored (§3.5)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    engagement_id: str
    scope: str
    element_stable_key: str | None
    phase_name: str | None
    kind: str
    origin: str
    text: str
    metric: str | None
    comparator: str | None
    target_value: float | None
    unit: str | None
    source_id: str | None
    segment_ids: list[str]
    quote: str
    owner_role_id: str | None
    stated_on: str | None
    verification_status: str
    rejection_guardrail: str | None
    status: str
    note: str
    created_at: str


class IntentView(BaseModel):
    """An intent statement as the API returns it (API_CONTRACT.md → Intent): names hidden."""

    id: str
    engagement_id: str
    scope: str
    element_stable_key: str | None
    element_label: str
    phase_name: str | None
    kind: str
    origin: str
    text: str
    metric: str | None
    comparator: str | None
    target_value: float | None
    unit: str | None
    source_id: str | None
    source_name: str
    anchor: str
    quote: str
    owner_role_id: str | None
    owner_role_name: str
    stated_on: str | None
    label: str
    verification_status: str
    rejection_guardrail: str | None
    status: str
    note: str
    created_at: str


class IntentFields(BaseModel):
    """What Eric may type or change on a statement (POST body, PATCH `edits`)."""

    model_config = ConfigDict(extra="forbid")

    scope: str | None = None
    element_stable_key: str | None = None
    phase_name: str | None = None
    kind: str | None = None
    text: str | None = None
    metric: str | None = None
    comparator: str | None = None
    target_value: float | None = None
    unit: str | None = None
    owner_role_id: str | None = None
    stated_on: str | None = None


class IntentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    note: str | None = None
    edits: IntentFields | None = None


class IntentConflictRecord(BaseModel):
    """An `intent_conflicts` row as stored (§3.5): a design gap proposed by `IX_compare`."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    version_id: str
    intent_id: str
    segment_ids: list[str]
    quote: str
    intent_quote: str
    conflict_text: str
    verifier_verdict: str
    verification_status: str
    rejection_guardrail: str | None
    status: str
    note: str
    created_at: str


class IntentConflictView(BaseModel):
    """A design-gap proposal as the API returns it (API_CONTRACT.md → Intent): names hidden."""

    id: str
    version_id: str
    intent_id: str
    intent_text: str
    intent_label: str
    intent_quote: str
    segment_ids: list[str]
    source_name: str
    anchor: str
    quote: str
    conflict_text: str
    verifier_verdict: str
    verification_status: str
    rejection_guardrail: str | None
    status: str
    note: str
    created_at: str


class ConflictPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    note: str | None = None


class IntentJobStarted(BaseModel):
    """`202` for the intent AI jobs: the job, and the engagement or version it works on."""

    job_id: str
    engagement_id: str | None = None
    version_id: str | None = None


class IntentEvaluationView(BaseModel):
    """A confirmed statement's evaluation on the done view (§3.16 "Evaluation")."""

    intent_id: str
    result: str  # met · not_met · unknown
    actual: float | None
    label: str | None  # B.50
    met_share: float | None
    cases: int | None
    documented: float | None
    documented_meets: bool | None


class DeltaView(BaseModel):
    value: float | None
    unit: str
    label: str  # B.50
    text: str


class DiscrepancyFound(BaseModel):
    """One detected discrepancy of one type at one location (§3.17.2), before codes and verdicts."""

    type: str  # B.48
    keys: list[str]
    element_ids: list[str]
    delta: DeltaView
    incidence: float | None
    cases: int | None
    control: bool
    shown: bool
    intent_ids: list[str]
    detail: dict[str, str]


class Detection(BaseModel):
    """Everything the engine found on a version, with the rule set that found it (G15)."""

    rules_version: str
    discrepancies: list[DiscrepancyFound]
    intents: list[IntentEvaluationView]


class DiscrepancyItemRecord(BaseModel):
    """A `discrepancy_items` row: a location's persistent code and Eric's verdict (§3.17.6)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    engagement_id: str
    code: str
    location_key: str
    title: str
    first_version_id: str | None
    verdict_decided: str | None
    verdict_note: str
    decision_owner_role_id: str | None
    retired: bool


class LocationView(BaseModel):
    kind: str  # step · run · activity · order · design · process
    keys: list[str]


class FigureDelta(BaseModel):
    value: float | None
    unit: str
    kind: str  # B.50
    label: str


class TypeDelta(FigureDelta):
    type: str


class VerdictView(BaseModel):
    suggested: str | None
    reason: str
    decided: str | None
    note: str
    decision_owner_role_id: str | None


class EvidenceCounts(BaseModel):
    documents: int
    interviews: int
    system_cases: int | None


class DiscrepancyView(BaseModel):
    """One location's discrepancies (API_CONTRACT.md → Discrepancies)."""

    item_id: str | None
    code: str | None
    status: str  # seen · not_seen
    types: list[str]
    location: LocationView
    title: str
    delta: FigureDelta | None
    deltas: list[TypeDelta]
    incidence: float | None
    cases: int | None
    hours_per_month: float
    shown: bool
    impact_class: str | None
    impact_note: str
    verdict: VerdictView | None
    evidence: EvidenceCounts
    element_ids: list[str]
    intent_ids: list[str]


class DiscrepanciesView(BaseModel):
    rules_version: str
    view: str
    items: list[DiscrepancyView]
    intents: list[IntentEvaluationView]


class VerdictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: str | None = None
    note: str = ""
    decision_owner_role_id: str | None = None


class VerdictDecided(BaseModel):
    item_id: str
    code: str
    verdict_decided: str | None
    verdict_note: str
    decision_owner_role_id: str | None
