"""Pydantic models shared by all layers (PRD §3.2). Domain models for §3.5 arrive in phase P1."""

from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr


class HealthInfo(BaseModel):
    """GET /api/health response (API_CONTRACT.md)."""

    status: str
    app_version: str
    prd_version: str


class SettingsView(BaseModel):
    """The Settings object (API_CONTRACT.md → Settings). Never contains the API key itself."""

    owner_name: str
    model: str
    effort: str
    verifier_enabled: bool
    web_research_enabled: bool
    system_records_enabled: bool
    gap_analysis_enabled: bool
    value_enabled: bool
    reality_views_enabled: bool
    currency: str
    default_timezone: str
    key_set: bool
    key_last4: str
    draft_cost_limit_usd: float | None = None  # the most one draft may cost (2026-10-19)


class ProfileUpdate(BaseModel):
    owner_name: str


class ApiKeyUpdate(BaseModel):
    # SecretStr keeps the key out of repr, str, logs and JSON dumps.
    anthropic_api_key: SecretStr


class ModelSummary(BaseModel):
    """What the app needs to know about one Claude model (from the Models API)."""

    id: str
    display_name: str
    pdf_input: bool
    structured_outputs: bool
    # Effort levels the model reports as supported, in order low → max.
    effort_levels: list[str]


class ConnectionCapabilities(BaseModel):
    pdf_input: bool
    structured_outputs: bool


class ConnectionTest(BaseModel):
    """POST /api/settings/test-connection response (API_CONTRACT.md)."""

    key_valid: bool
    model_available: bool
    capabilities: ConnectionCapabilities
    message: str


class ModelChoices(BaseModel):
    """GET /api/settings/models response (API_CONTRACT.md)."""

    models: list[ModelSummary]
    from_anthropic: bool
    message: str


class SpendingSettings(BaseModel):
    """PUT /settings/spending (2026-10-19): the most one draft or refresh may cost; null = none."""

    model_config = ConfigDict(extra="forbid")

    draft_cost_limit_usd: float | None


class DraftEstimate(BaseModel):
    """GET /engagements/{id}/draft/estimate (deep review item 5): what a draft would cost."""

    sources: int
    characters: int
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    basis: str  # "assumed" until a real draft has run on this computer, then "measured"
    drafts_measured: int
    model: str
    prices_checked_on: str
    limit_usd: float | None
    over_limit: bool


class ModelUpdate(BaseModel):
    model: str
    effort: str
    verifier_enabled: bool


# --- Engagements and roles (API_CONTRACT.md → Engagements and roles) -------------------------


class MappingConventions(BaseModel):
    """Codebook tier 2 conventions Eric sets per engagement (PRD Appendix E, §5.4 Setup; C7a)."""

    granularity: str = "standard"  # coarse (8-12 steps) · standard (12-20) · fine (20-25)
    label_style: str = "standard"  # standard wording · sme (the SME's own term)
    phase_naming: str = "sme"  # sme terms · standard terms


CONVENTION_CHOICES: dict[str, tuple[str, ...]] = {
    "granularity": ("coarse", "standard", "fine"),
    "label_style": ("standard", "sme"),
    "phase_naming": ("sme", "standard"),
}


class ScopeFields(BaseModel):
    """Process scope card fields (PRD §5.4 Setup). All optional so PATCH can send any subset."""

    name: str | None = None
    process_name: str | None = None
    trigger: str | None = None
    end_point: str | None = None
    in_scope_roles: list[str] | None = None
    out_of_scope: str | None = None
    process_kpi: str | None = None
    industry: str | None = None
    adjacent_industries: list[str] | None = None
    confidential_terms: list[str] | None = None
    conventions: dict[str, str] | None = None  # MappingConventions, checked by the action
    trigger_external: bool | None = None  # E1: the process starts outside the organisation
    end_point_external: bool | None = None  # E1: it ends outside the organisation


class EngagementCreate(ScopeFields):
    name: str


class EngagementView(BaseModel):
    id: str
    name: str
    process_name: str
    trigger: str
    end_point: str
    in_scope_roles: list[str]
    out_of_scope: str
    process_kpi: str
    industry: str
    adjacent_industries: list[str]
    confidential_terms: list[str]
    conventions: MappingConventions = MappingConventions()
    trigger_external: bool = False
    end_point_external: bool = False
    status: str
    created_at: str
    updated_at: str


class VersionLabel(BaseModel):
    label: str
    state: str


class ReviewProgress(BaseModel):
    reviewed: int
    total: int


class DraftAcceptance(BaseModel):
    """How much of Claude's draft Eric kept (deep review item 4): `drafted` = `confirmed` +
    `edited` + `rejected` + `unreviewed`; `added` counts the steps Eric added himself."""

    drafted: int
    confirmed: int
    edited: int
    rejected: int
    unreviewed: int
    added: int


class EngagementSummary(EngagementView):
    latest_version: VersionLabel | None
    review_progress: ReviewProgress
    sources_count: int


class RoleCreate(BaseModel):
    name: str
    aliases: list[str] = []
    is_system: bool = False


class RolePatch(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None
    is_system: bool | None = None
    lane_order: int | None = None


class RoleView(BaseModel):
    id: str
    engagement_id: str
    name: str
    aliases: list[str]
    is_system: bool
    lane_order: int | None


# --- Parsed documents (services/parsing.py) ---------------------------------------------------


class ParsedSegment(BaseModel):
    """One anchored passage of a source, before it is stored as a source_segments row."""

    seq: int
    text: str
    page: int | None = None
    section: str = ""
    speaker_label: str = ""
    start_ms: int | None = None
    end_ms: int | None = None
    instruction_like: bool = False


class ParsedDocument(BaseModel):
    segments: list[ParsedSegment]
    # PDF pages with under 50 characters of text: sent to OCR (S0) from phase P3.
    ocr_pages: list[int] = []
    page_count: int | None = None
    # Names and addresses from an email's headers (R11): added to the redaction terms on reading.
    hidden_names: list[str] = []


class ExtractedImage(BaseModel):
    """An image found inside a PDF: offered to Eric as a suggestion, never used automatically."""

    page: int
    name: str
    extension: str
    data: bytes
    width: int
    height: int


# --- Sources (API_CONTRACT.md → Sources) -----------------------------------------------------


class SourceView(BaseModel):
    id: str
    engagement_id: str
    kind: str
    filename: str
    format: str
    mime: str
    version_date: str
    owner: str
    controlled_copy: bool
    text_status: str
    error: str
    segment_count: int
    ocr_pages: list[int]
    suggested_images: int
    created_at: str
    # G11 (P9): the share of the source's passages the current map cites; None without a map
    # made from this source.
    coverage_pct: float | None = None
    # Only on the upload response: the background job reading the file.
    job_id: str | None = None


class SourceReadInfo(BaseModel):
    """What the reading job needs to know about a source."""

    id: str
    engagement_id: str
    filename: str
    kind: str
    format: str
    stored_path: str


class SourcePatch(BaseModel):
    kind: str | None = None
    version_date: str | None = None
    owner: str | None = None
    controlled_copy: bool | None = None


class SegmentView(BaseModel):
    id: str
    seq: int
    anchor: str
    page: int | None
    section: str
    speaker_role: str | None
    text: str
    cited: bool
    instruction_like: bool
    # Only with raw=1 (owner-only correction editor): the speaker label as written in the file.
    speaker_label: str | None = None
    corrected: bool = False
    # Interviews: the guide question this turn asks or answers (§3.12.10 step A), once drafted.
    question_id: str | None = None


class SegmentPatch(BaseModel):
    text: str


class SpeakerView(BaseModel):
    label: str
    segment_count: int
    role_id: str | None
    is_interviewer: bool


class SegmentPage(BaseModel):
    segments: list[SegmentView]
    total: int
    page: int
    pages: int
    coverage_pct: float | None


# --- Readiness (guided navigation) -----------------------------------------------------------


class SourceFacts(BaseModel):
    """What readiness needs to know about one source."""

    id: str
    filename: str
    kind: str
    text_status: str
    unmapped_speakers: int


class ReadinessFacts(BaseModel):
    """Stored facts about an engagement that the readiness rules read (no rules here)."""

    trigger: str
    end_point: str
    sources: list[SourceFacts]
    version_count: int
    published: bool
    latest_progress: ReviewProgress
    gap_finalised: bool
    exported: bool = False


class SignalStrength(BaseModel):
    """How much independent evidence a map rests on, from the kinds of its sources (P12)."""

    level: Literal["strong", "moderate", "limited"]
    label: str  # Strong · Moderate · Limited
    score: int  # 3 · 2 · 1 (the meter shown next to the label)
    detail: str


class Readiness(BaseModel):
    key_set: bool
    transcripts_ready: bool
    documents_ready: bool
    speakers_unmapped: int
    draft_exists: bool
    blockers_count: int
    nav: dict[str, str]
    nav_counts: dict[str, int]
    next_step: str | None
    missing: list[str]
    recommended: list[str] = []
    signal: SignalStrength | None = None
    ready_to_draft: bool


# --- Redaction (PRD §3.8 G10) -------------------------------------------------------------------


class NameReplacement(BaseModel):
    """A term to hide and what to show instead (a role name, "Interviewer" or "[name]")."""

    term: str
    replacement: str = "[name]"


class Redacted(BaseModel):
    text: str
    hits: int


# --- Jobs (PRD §4 Pipeline) ---------------------------------------------------------------------


class JobStage(BaseModel):
    """One stage of a draft job, for the stage stepper (API_CONTRACT.md → Jobs)."""

    id: str
    name: str
    status: str  # waiting · running · done · failed · later
    started_at: str | None = None
    finished_at: str | None = None


class JobClaims(BaseModel):
    verified: int = 0
    rejected: int = 0


class JobView(BaseModel):
    id: str
    engagement_id: str | None
    type: str
    target_id: str | None
    status: str
    stage: str
    progress: float
    message: str
    error: str
    usage: dict[str, int] | None = None
    claims: JobClaims = JobClaims()
    stages: list[JobStage] = []
    created_at: str


class RedactionTermCreate(BaseModel):
    term: str
    replacement: str = ""


class RedactionTermView(BaseModel):
    id: str
    engagement_id: str
    term: str
    replacement: str
    origin: str


# --- AI calls (PRD §3.7 call_claude, §3.4 AI usage) ------------------------------------------


class AiCallRecord(BaseModel):
    """One Messages API call, for the ai_calls table. Never holds prompt or document text."""

    stage_id: str
    prompt_version: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    status: str  # ok · repaired · invalid · refused · truncated · error · mock
    input_hash: str


class AiAnswer(BaseModel):
    """A validated answer from a stage call, plus the calls it took (the first and any repair)."""

    data: dict[str, object]
    calls: list[AiCallRecord]


class CheckOutcome(BaseModel):
    """The result of one grounding check (PRD §3.8): passed, or which guardrail failed and why."""

    passed: bool
    guardrail: str = ""  # B.20: G3, G4, G5 …
    reason: str = ""


class PromptSegment(BaseModel):
    """One passage as it is sent to Claude: a call-local ID, its anchor, the speaker's role (never a
    name) and the text with names already hidden. `segment_id` is the stored passage's real ID."""

    ref: str
    segment_id: str
    seq: int
    anchor: str
    text: str
    speaker_role: str = ""
    page: int | None = None
    start_ms: int | None = None
    # Interviews (§3.12.10 steps A and B): the guide question of the answer block, and the marker
    # pre-tags as hints ("explicit_order: First thing").
    question_id: str = ""
    markers: list[str] = []


class Prompt(BaseModel):
    name: str
    version: str
    text: str


# --- Versions and claims (PRD §3.5) ----------------------------------------------------------


class VersionView(BaseModel):
    id: str
    engagement_id: str
    label: str
    state: str
    created_at: str


class ClaimRecord(BaseModel):
    """A claim as stored after the grounding gate (verified or rejected, with guardrail)."""

    source_id: str
    stage: str
    claim_type: str
    payload: dict[str, object]
    segment_ids: list[str]
    quote: str
    provenance: str
    basis: str
    verification_status: str
    rejection_reason: str = ""
    rejection_guardrail: str = ""
    account_type: str | None = None  # interview claims (B.28): official · lived · unclear


class UnknownRecord(BaseModel):
    source_id: str
    question: str
    segment_ids: list[str]


class StoredSegment(BaseModel):
    """A stored passage with what a stage needs to send it (names not yet hidden)."""

    id: str
    seq: int
    page: int | None
    section: str
    start_ms: int | None
    text: str
    speaker_label: str
    speaker_role: str | None
    is_interviewer: bool
    instruction_like: bool


class DraftSummary(BaseModel):
    steps: int
    needs_check: int
    verified: int
    rejected: int
    open_questions: int
    scrubbed: int


class StepRename(BaseModel):
    before: str
    after: str


class RefreshChanges(BaseModel):
    """What a refresh changed among the steps Eric hadn't reviewed (anti-drift)."""

    kept: int
    new_steps: list[str] = []
    no_longer_drafted: list[str] = []
    renamed: list[StepRename] = []


class DraftState(BaseModel):
    """GET /engagements/{id}/draft: the latest draft job and the current draft."""

    job: JobView | None
    version: VersionView | None
    summary: DraftSummary | None
    last_refresh: RefreshChanges | None = None


class DraftStarted(BaseModel):
    job_id: str


class RunRecord(BaseModel):
    """How a draft or refresh was made (API_CONTRACT → Run record; anti-drift)."""

    model: str
    effort: str | None
    verifier: bool
    instructions: dict[str, str]  # prompt or question-bank name → version
    app_version: str


class RefreshCheck(BaseModel):
    """What a refresh would do differently from the run that made the version (warn, not block)."""

    made_with: RunRecord | None
    now: RunRecord
    changes: list[str]


class RejectedClaim(BaseModel):
    id: str
    claim_text: str
    source_id: str
    source_name: str
    anchor: str
    reason: str
    guardrail: str
    stage: str
    passage_available: bool
    segment_id: str | None


class RejectedClaims(BaseModel):
    items: list[RejectedClaim]
    total: int
    scrub_count: int
    instruction_like_count: int


class AiUsageRow(BaseModel):
    id: str
    created_at: str
    job_id: str | None
    stage_id: str
    prompt_version: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    status: str


class AiUsage(BaseModel):
    items: list[AiUsageRow]
    totals: dict[str, int]


# --- Calibration (PRD §3.7 S3, §3.8 G7) --------------------------------------------------------


class StanceFact(BaseModel):
    """What one source says about one element: supports, contradicts or silent (B.14)."""

    source_id: str
    source_kind: str  # B.1
    stance: str  # B.14


class AccountableFact(BaseModel):
    """The Accountable role one source gives an element (for the JD accountability test)."""

    source_id: str
    source_kind: str  # B.1
    role: str


class AccountabilityTest(BaseModel):
    """Result of the JD accountability test: the competing A roles, if the sources disagree."""

    contested: bool
    roles: list[str]  # every A role named, in first-seen order
    sources_by_role: dict[str, list[str]]  # role → source IDs that name it


class ConfidenceTerm(BaseModel):
    label: str
    delta: float


class Confidence(BaseModel):
    """G7 confidence: the value and the terms it is made of (the terms sum to the value)."""

    value: float
    breakdown: list[ConfidenceTerm]


class AuditEntry(BaseModel):
    """One row of a version's audit log (PRD §5.7.10 Audit tab); names hidden in the label."""

    id: str
    at: str
    actor: str
    action: str
    target_type: str
    target_id: str
    target_label: str
    before: object = None
    after: object = None


# --- Editing a step (API_CONTRACT.md → Review: PATCH /elements/{eid}) ---------------------------


class DecisionInput(BaseModel):
    mechanism: str
    decider_role_id: str | None = None
    rule_or_threshold: str = ""
    escalation: str = ""


class HandoffInput(BaseModel):
    in_: str = Field(default="", validation_alias=AliasChoices("in", "in_"))
    out: str = ""


class ConstraintInput(BaseModel):
    text: str
    cause_type: str | None = None
    is_key: bool = False
    provenance: str = "O"


class AiFlagInput(BaseModel):
    component: str
    input: str
    output: str
    handoff: str
    basis: str


class RaciInput(BaseModel):
    role_id: str
    letter: str
    contested: bool = False


class ElementPatch(BaseModel):
    """Only the fields sent change (`model_fields_set`); `ai_flag: null` removes the flag."""

    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    kind: str | None = None
    lane_role_id: str | None = None
    work_min: float | None = None
    wait_min: float | None = None
    duration_text: str | None = None
    complexity: str | None = None
    kpi: str | None = None
    decision: DecisionInput | None = None
    handoff: HandoffInput | None = None
    constraints: list[ConstraintInput] | None = None
    k_risk: str | None = None
    ai_flag: AiFlagInput | None = None
    raci: list[RaciInput] | None = None


class WorkTypeInput(BaseModel):
    """Confirm or change a step's work type (API_CONTRACT.md → Review: PUT …/work-type).
    `constraint_type` left out follows the work type; sent as `null` it clears it."""

    model_config = ConfigDict(extra="forbid")

    work_type: str
    constraint_type: str | None = None
    confirm: bool = False


class SystemActivityRef(BaseModel):
    """A log's activity (R8: Add as step from hidden work)."""

    model_config = ConfigDict(extra="forbid")

    log_id: str
    activity: str


class NewStep(BaseModel):
    """Eric's own step (API_CONTRACT.md → Review: POST /versions/{vid}/elements)."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    label: str
    lane_role_id: str
    after_element_id: str
    provenance: str
    segment_ids: list[str] = []
    r_reference: str = ""
    mechanism: str = "judgment"
    #: R8: an activity Eric confirmed as hidden work; its system trace is the step's evidence.
    system_activity: SystemActivityRef | None = None


class EdgeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_: str = Field(validation_alias=AliasChoices("from", "from_"))
    to: str
    kind: str
    label: str = ""


class EdgePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_: str | None = Field(default=None, validation_alias=AliasChoices("from", "from_"))
    to: str | None = None
    kind: str | None = None
    label: str | None = None


class QuestionView(BaseModel):
    id: str
    element_id: str | None
    element_label: str
    phase_id: str | None
    phase_name: str
    question: str
    reason: str
    status: str


class QuestionStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class MergeDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str


class MergeClaimView(BaseModel):
    text: str
    source_name: str
    anchor: str
    quote: str


class MergeGroupView(BaseModel):
    label: str
    kind: str
    lane_role_name: str
    element_id: str | None
    claims: list[MergeClaimView]


class MergeProposalView(BaseModel):
    id: str
    proposed_label: str
    similarity: float
    decision: str
    decided_at: str | None
    element_id: str | None
    groups: list[MergeGroupView]


# --- Versions, publish and exports (API_CONTRACT.md → Versions, publish and exports; P7) --------


class VersionSummary(BaseModel):
    id: str
    engagement_id: str
    label: str
    state: str
    created_at: str
    published_at: str | None
    published_by: str | None
    parent_version_id: str | None
    signal: SignalStrength | None = None
    codebook_version: str | None = None  # Appendix E: the codebook the draft was made with


class ChangeEntry(BaseModel):
    """What was done to a step while the version was the draft."""

    change: str  # confirmed · edited · rejected · added
    step: str
    stable_key: str


class VersionDetail(VersionSummary):
    review: ReviewProgress
    acceptance: DraftAcceptance
    change_log: list[ChangeEntry]
    quality_card: dict[str, object] | None


class PublishBlocker(BaseModel):
    #: unreviewed_element · needs_check · pending_merge · suggested_image · lint_failure ·
    #: quality_check
    type: str
    id: str
    element_id: str | None
    message: str


class ExportFile(BaseModel):
    filename: str
    media_type: str
    content: str


# --- Images (API_CONTRACT.md → Images; phase P8) -----------------------------------------------


class ImageRecord(BaseModel):
    """An image row as stored."""

    model_config = ConfigDict(from_attributes=True)

    id: str = ""
    element_id: str | None = None
    stored_path: str
    caption: str = ""
    image_type: str | None = None
    origin: str  # uploaded · extracted
    status: str = "suggested"  # B.17
    redaction_confirmed: bool = False
    source_id: str | None = None
    page: int | None = None
    created_at: str = ""


class ImageView(BaseModel):
    id: str
    element_id: str | None
    caption: str
    image_type: str | None
    origin: str
    status: str
    redaction_confirmed: bool
    source_name: str
    page: int | None
    created_at: str


class ImagePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    caption: str | None = None
    image_type: str | None = None
    redaction_confirmed: bool | None = None


# --- Registers and cause library (PRD §4 Views, §5.4 Registers, §3.5 cause_library; P9) --------


class KRiskItem(BaseModel):
    element_id: str
    label: str
    lane: str
    k_risk: str


class AiFlagItem(BaseModel):
    element_id: str
    label: str
    lane: str
    mechanism: str  # B.6: a judgment step's flag is support only
    component: str
    input: str
    output: str
    handoff: str
    basis: str


class ConstraintItem(BaseModel):
    element_id: str
    label: str
    text: str
    is_key: bool
    provenance: str


class ConstraintGroup(BaseModel):
    cause_type: str | None  # B.9, or None when no cause type was recorded
    constraints: list[ConstraintItem]


class ExternalPracticeItem(BaseModel):
    element_id: str
    label: str
    r_reference: str


class Registers(BaseModel):
    k_risk: list[KRiskItem]
    ai_flags: list[AiFlagItem]
    constraints_by_cause: list[ConstraintGroup]
    external_practice: list[ExternalPracticeItem]
    questions: list[QuestionView]
    rejected_claims: RejectedClaims


class CauseRecord(BaseModel):
    """A cause-library row as stored."""

    model_config = ConfigDict(from_attributes=True)

    id: str = ""
    engagement_id: str
    element_stable_key: str
    divergence_type: str
    pattern: str
    inferred_cause: str = ""
    cause_type: str = ""
    provenance: str
    validation_result: str = "pending"
    created_at: str = ""


class CauseView(BaseModel):
    id: str
    element_stable_key: str
    element_id: str | None  # the step with that key on the current map, if it is still there
    element_label: str
    divergence_type: str
    pattern: str
    inferred_cause: str
    cause_type: str | None
    provenance: str
    validation_result: str
    created_at: str


class CausePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_result: str


# --- Web research (PRD §3.11.2 step 2; phase P10) ----------------------------------------------


class ResearchCitation(BaseModel):
    """A citation Anthropic attached to the answer text: the source and the words it cites."""

    url: str
    title: str
    cited_text: str


class ResearchPassage(BaseModel):
    """One piece of the answer text with the citations attached to it (none for connecting text)."""

    text: str
    citations: list[ResearchCitation]


class SearchResult(BaseModel):
    """A page the web search returned in this request (never its encrypted content)."""

    url: str
    title: str
    page_age: str


class ResearchAnswer(BaseModel):
    """What a web research call produced: the cited answer, every search result, tool errors
    (kept as partial results), searches used, and the calls made (one per continuation)."""

    passages: list[ResearchPassage]
    results: list[SearchResult]
    tool_errors: list[str]
    search_count: int
    stop_reason: str
    calls: list[AiCallRecord]


class WebSearchTest(BaseModel):
    available: bool
    message: str


class ResearchSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    web_research_enabled: bool


class ModuleSettings(BaseModel):
    """PUT /settings/modules: a field left out keeps its value (R10 adds more modules)."""

    model_config = ConfigDict(extra="forbid")

    system_records_enabled: bool | None = None
    gap_analysis_enabled: bool | None = None
    value_enabled: bool | None = None
    reality_views_enabled: bool | None = None


class RegionalSettings(BaseModel):
    """PUT /settings/regional (R10): a field left out keeps its value."""

    model_config = ConfigDict(extra="forbid")

    currency: str | None = None
    default_timezone: str | None = None


# --- Step disposition (R9a; API_CONTRACT.md → Step disposition) --------------------------------


class DispositionInput(BaseModel):
    """Eric's choice for a step (PUT /elements/{eid}/disposition)."""

    model_config = ConfigDict(extra="forbid")

    disposition: str | None
    note: str = ""
    risk_flag: str | None = None


class RefusedDisposition(BaseModel):
    """A disposition Eric can't choose for a step, and why (R10b)."""

    disposition: str  # B.41
    reason: str


class DispositionView(BaseModel):
    """A step's suggested disposition with its reason, and Eric's choice."""

    element_id: str
    label: str
    kind: str
    suggested: str  # B.41
    reason: str
    disposition: str | None  # Eric's choice, or None
    note: str
    risk_flag: str
    allowed: list[str]
    not_allowed: list[RefusedDisposition]


# --- Value calculator (R9b; API_CONTRACT.md → Value calculator) ---------------------------------


class RoleCostRow(BaseModel):
    role_id: str
    role_name: str = ""
    hourly_cost: float | None = None
    note: str = ""


class RoleCostsView(BaseModel):
    currency: str
    rows: list[RoleCostRow]


class RoleCostsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[RoleCostRow]


class AssumptionRow(BaseModel):
    disposition: str
    reduction_pct: float
    note: str = ""
    default: bool = False


class AssumptionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[AssumptionRow]


class ValueOverrideInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_min: float | None = None
    volume_month: float | None = None
    note: str = ""


class ValueFigure(BaseModel):
    value: float
    label: str  # B.42
    source: str


class StepValueView(BaseModel):
    element_id: str
    label: str
    phase_id: str | None
    phase_name: str
    role_name: str
    time: ValueFigure | None
    volume: ValueFigure | None
    hours_per_month: float | None
    cost_per_month: float | None
    evidence: str | None
    missing: list[str]
    disposition: str
    chosen: bool
    reduction_pct: float
    hours_released: float | None
    cost_released: float | None


class ValueTotalView(BaseModel):
    phase_id: str | None = None
    name: str = ""
    hours_per_month: float
    cost_per_month: float
    evidence: str | None
    steps_counted: int
    steps_missing: int
    steps_without_cost: int


class ScenarioView(BaseModel):
    disposition: str
    reduction_pct: float
    steps: int
    hours_per_month: float
    hours_released: float
    cost_released: float


class ValueView(BaseModel):
    currency: str
    view: str
    potential: str
    steps: list[StepValueView]
    phases: list[ValueTotalView]
    totals: ValueTotalView
    scenarios: list[ScenarioView]
