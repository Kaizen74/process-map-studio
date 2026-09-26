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
