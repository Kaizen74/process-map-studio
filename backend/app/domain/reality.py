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
