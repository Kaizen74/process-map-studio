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


# --- The Reality snapshot (API_CONTRACT.md → Reality snapshot; PRD §3.18, §5.12; P13b) ----------


class Figure(BaseModel):
    """One figure, with the ID it has everywhere it appears (RQ9, G17)."""

    id: str
    value: float | None
    unit: str  # pct · min · h · x · count · ""
    text: str
    label: str  # B.50, or the value calculator's measured · estimated · mixed
    percent_type: str | None = None  # variant_share · incidence · prevalence


class Tile(BaseModel):
    figure: Figure
    caption: str


class EvidenceSummary(BaseModel):
    documents: int
    interviews: int
    cases: int | None
    text: str


class Column(BaseModel):
    id: str
    name: str
    kind: str  # phase · step · process
    step_keys: list[str]


class Chips(BaseModel):
    documents: bool
    interviews: bool
    system: bool


class CodeEvidence(BaseModel):
    documents: int
    interviews: int
    system_cases: int | None
    chips: Chips
    sentence: str


class CodeVerdict(BaseModel):
    suggested: str | None
    decided: str | None
    shown: str | None
    status: str  # suggested · confirmed
    reason: str
    note: str


class CodeView(BaseModel):
    """An X code's identity: the same in every view, the panel, Leadership and the pack (RQ4)."""

    code: str
    item_id: str
    title: str
    types: list[str]
    impact_class: str
    impact_word: str
    glyph: str  # triangle · clock · bars · dotted_square
    impact_note: str
    location: LocationView
    element_ids: list[str]
    column_id: str | None
    delta: Figure
    minutes: Figure | None
    hours: Figure | None  # None without system records (nothing can be measured)
    verdict: CodeVerdict | None
    evidence: CodeEvidence
    control: bool
    shown: bool
    rank: int


class Callout(BaseModel):
    code: str | None
    impact_class: str | None
    lines: list[str]


class Availability(BaseModel):
    state: str  # ready · partial · missing
    message: str
    action: str | None  # add_intent · upload_documents · import_log · draft


class ViewTable(BaseModel):
    columns: list[str]
    rows: list[list[str]]


class Route(BaseModel):
    id: str
    name: str
    documented: bool
    share: Figure
    codes: list[str]
    impact_class: str | None
    other_count: int


class GlanceModel(BaseModel):
    basis: str  # cases · steps
    routes: list[Route]


class Trunk(BaseModel):
    x1: float
    x2: float
    y: float
    width: float


class Ribbon(BaseModel):
    route_id: str
    path: str
    width: float
    style: str  # solid · dashed · dotted · double
    label_x: float
    label_y: float


class GlanceGeometry(BaseModel):
    width: float
    height: float
    trunk: Trunk
    ribbons: list[Ribbon]
    scale_note: str


class StackItem(BaseModel):
    kind: str  # intent · belief · documented_step · done_step · branch · minutes · hours
    key: str | None
    label: str
    figure: Figure | None
    code: str | None
    impact_class: str | None
    result: str | None  # intent: met · not_met · unknown
    note: str


class StackCell(BaseModel):
    column_id: str
    items: list[StackItem]


class Band(BaseModel):
    id: str  # promise · belief · documented · done · consequence
    name: str
    evidence: str
    state: str  # ready · partial · missing
    message: str
    cells: list[StackCell]


class Lens(BaseModel):
    column_id: str
    label: str


class StackModel(BaseModel):
    bands: list[Band]
    lens: Lens | None
    highlighted: list[str]
    listed: list[str]


class Box(BaseModel):
    id: str
    x: float
    y: float
    width: float
    height: float


class Mark(BaseModel):
    kind: str  # as StackItem.kind
    band_id: str
    column_id: str
    x: float
    y: float
    width: float
    height: float
    lines: list[str]
    code: str | None
    key: str | None
    impact_class: str | None
    style: str  # solid · dashed · dotted · double


class Label(BaseModel):
    """A text label placed by the backend (one or more lines)."""

    id: str
    x: float
    y: float
    lines: list[str]


class LensBox(BaseModel):
    x: float
    y: float
    width: float
    height: float
    label_x: float
    label_y: float


class StackGeometry(BaseModel):
    width: float
    height: float
    columns: list[Box]
    bands: list[Box]
    marks: list[Mark]
    lens: LensBox | None
    column_labels: list[Label]
    band_labels: list[Label]


class Quadrant(BaseModel):
    id: str  # as_designed · codify · rewrite · correct · ask
    name: str
    meaning: str


class Placed(BaseModel):
    code: str
    zone: str


class FixModel(BaseModel):
    quadrants: list[Quadrant]
    circles: list[Placed]
    ask: list[str]
    decide_first: list[str]
    limit: int
    note: str


class Zone(BaseModel):
    id: str
    x: float
    y: float
    width: float
    height: float
    label_x: float
    label_y: float


class Circle(BaseModel):
    code: str
    cx: float
    cy: float
    r: float


class FixGeometry(BaseModel):
    width: float
    height: float
    zones: list[Zone]
    circles: list[Circle]
    labels: list[Label]
    scale_note: str


class ViewBase(BaseModel):
    id: str
    title: str
    headline: str
    callouts: list[Callout]
    availability: Availability
    table: ViewTable


class GlanceView(ViewBase):
    glance: GlanceModel
    geometry: GlanceGeometry


class StackView(ViewBase):
    stack: StackModel
    geometry: StackGeometry


class FixView(ViewBase):
    fix: FixModel
    geometry: FixGeometry


class RealityViews(BaseModel):
    rv1: GlanceView
    rv2: StackView
    rv3: FixView


class LegendImpact(BaseModel):
    impact_class: str
    word: str
    glyph: str


class LegendLine(BaseModel):
    style: str
    meaning: str


class Legend(BaseModel):
    impacts: list[LegendImpact]
    lines: list[LegendLine]
    scales: list[str]
    data_label: str


class SnapshotIntent(BaseModel):
    """A confirmed statement as the snapshot evaluated it."""

    id: str
    kind: str
    text: str
    scope: str
    step_keys: list[str]
    result: str  # met · not_met · unknown
    target: str


class RealitySnapshot(BaseModel):
    """One version's Reality views (API_CONTRACT.md → Reality snapshot)."""

    version_id: str
    rules_version: str
    copy_version: str
    layout_version: str
    app_version: str
    inputs_hash: str
    frozen: bool
    draft: bool
    process_name: str
    data_label: str
    evidence: EvidenceSummary
    figures: dict[str, Figure]
    tiles: list[Tile]
    columns: list[Column]
    columns_note: str
    codes: list[CodeView]
    intents: list[SnapshotIntent]
    views: RealityViews
    legend: Legend


class RealityFigures(BaseModel):
    """What Leadership shares with the Reality views (G17)."""

    data_label: str
    tiles: list[Tile]
