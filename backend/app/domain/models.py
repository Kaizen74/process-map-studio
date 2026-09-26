"""Pydantic models shared by all layers (PRD §3.2). Domain models for §3.5 arrive in phase P1."""

from __future__ import annotations

from pydantic import BaseModel, SecretStr


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
    key_set: bool
    key_last4: str


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


class ModelUpdate(BaseModel):
    model: str
    effort: str
    verifier_enabled: bool


# --- Engagements and roles (API_CONTRACT.md → Engagements and roles) -------------------------


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
    status: str
    created_at: str
    updated_at: str


class VersionLabel(BaseModel):
    label: str
    state: str


class ReviewProgress(BaseModel):
    reviewed: int
    total: int


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


class ParsedDocument(BaseModel):
    segments: list[ParsedSegment]
    # PDF pages with under 50 characters of text: sent to OCR (S0) from phase P3.
    ocr_pages: list[int] = []
    page_count: int | None = None


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
    ready_to_draft: bool


# --- Redaction (PRD §3.8 G10) -------------------------------------------------------------------


class NameReplacement(BaseModel):
    """A term to hide and what to show instead (a role name, "Interviewer" or "[name]")."""

    term: str
    replacement: str = "[name]"


class Redacted(BaseModel):
    text: str
    hits: int
