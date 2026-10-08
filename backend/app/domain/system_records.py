"""Models for the system records module (PRD §3.13, P10b): the data request template first."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ColumnSpec(BaseModel):
    """One column of the requested extract (§3.13.1, B.40)."""

    name: str
    required: bool
    meaning: str
    sample: str


class DataRequestDocument(BaseModel):
    """The data request template's content (§3.13.2), rendered as Word or Markdown."""

    title: str
    subtitle: str
    purpose: list[str]
    scope: list[str]
    window: list[str]
    columns: list[ColumnSpec]
    column_note: str
    privacy: list[str]
    format: list[str]
    approval_fields: list[str]
    retention: str


class LogEvent(BaseModel):
    """One event of an imported log (§3.13.1): never a user ID; the resource is already a role
    (or none) by the time an event exists (constraint 24)."""

    case_id: str
    activity: str
    start: str  # ISO 8601, UTC
    end: str | None = None
    role: str | None = None
    system: str = ""
    attributes: dict[str, str] = {}


class DroppedRows(BaseModel):
    unparseable_time: int = 0
    missing_case_or_activity: int = 0
    duplicate: int = 0


class ValidationReport(BaseModel):
    """The import's plain-language validation report (§3.13.3 step 4)."""

    rows_read: int
    rows_kept: int
    cases: int
    activities: int
    date_from: str | None
    date_to: str | None
    dropped: DroppedRows
    dropped_share: float
    single_event_cases: int
    unknown_role_events: int = 0
    outside_window: int
    timestamp_format: str
    missing_columns: list[str]
    refused: bool
    refusal: str


class ParsedLog(BaseModel):
    events: list[LogEvent]
    report: ValidationReport


class ResourceRow(BaseModel):
    """A user ID from the held file, for the role-mapping step: memory only, never stored."""

    value: str
    events: int
    suggested_role_id: str | None = None


class EventLogView(BaseModel):
    """A system log (API_CONTRACT.md → System records: event logs)."""

    id: str
    engagement_id: str
    name: str
    system: str
    timezone: str
    window_start: str | None
    window_end: str | None
    status: str
    column_map: dict[str, str | None]
    timestamp_format: str | None = None
    file_held: bool = False
    resources: list[ResourceRow] = []
    role_map: dict[str, str | None] = {}
    validation_report: ValidationReport | None = None
    approved_by_role: str
    approved_at: str | None
    created_at: str


class ColumnMapInput(BaseModel):
    columns: dict[str, str | None]
    timestamp_format: str | None = None
    timezone: str | None = None  # the wizard's time-zone step (R7); None keeps the log's


class RoleMapInput(BaseModel):
    roles: dict[str, str | None]


class ImportInput(BaseModel):
    approved_by_role: str = ""
    confirm_approval: bool = False


class ImportStarted(BaseModel):
    job_id: str
    log_id: str


class MetricRow(BaseModel):
    """One stored group of metrics (PRD §3.5 `mining_metrics`; §3.13.5)."""

    scope: str  # activity · transition · case · variant · role
    key: str
    label: str
    case_count: int
    metrics: dict[str, Any]


class MetricsView(BaseModel):
    """GET /event-logs/{lid}/metrics: only groups of at least `minimum_cases` cases."""

    log_id: str
    scope: str
    minimum_cases: int
    groups: list[MetricRow]
    too_few: int


class AlignmentRow(BaseModel):
    """One row of the alignment table (API_CONTRACT → Alignment of log activities to map steps)."""

    activity: str
    element_id: str | None
    element_label: str
    status: str  # B.43
    confirmed: bool
    proposed_by: str  # app · claude · eric
    reason: str
    events: int
    cases: int


class AlignmentSummary(BaseModel):
    activities: int
    matched: int
    hidden_work: int
    no_system_record: int
    waiting: int


class AlignmentView(BaseModel):
    log_id: str
    version_id: str
    rows: list[AlignmentRow]
    summary: AlignmentSummary


class AlignmentChoice(BaseModel):
    activity: str = ""
    element_id: str | None = None
    status: str


class AlignmentInput(BaseModel):
    rows: list[AlignmentChoice]


class AlignmentStored(BaseModel):
    """A stored decision or Claude suggestion, its step given by stable key (versions change)."""

    activity: str
    step_key: str | None
    status: str
    reason: str
    confirmed: bool


class SuggestStarted(BaseModel):
    job_id: str
    log_id: str


class TraceActivity(BaseModel):
    activity: str
    cases: int
    events: int
    work: dict[str, Any] | None
    wait_before: dict[str, Any] | None
    basis: str


class SystemTraceItem(BaseModel):
    """One step's system-trace evidence from one log (API_CONTRACT → system-traces)."""

    element_id: str
    label: str
    stance: str  # supports · contradicts
    log_id: str
    log_name: str
    system: str
    window_start: str | None
    window_end: str | None
    cases: int
    events: int
    cases_per_week: float
    rework_cases: int
    rework_share: float
    activities: list[TraceActivity]
    note: str
    # Step summary (R8; items frozen before R8 read these as empty).
    cases_per_month: float = 0.0
    main_activity: str = ""
    work: dict[str, Any] | None = None
    wait_before: dict[str, Any] | None = None
    basis: str = ""
    variants: int = 0
    variant_share: float = 0.0


# --- Variants through the map (R8; API_CONTRACT → system-variants) ------------------------------


class VariantStep(BaseModel):
    activity: str
    element_id: str | None
    label: str
    status: str  # matched · hidden_work · not_matched


class ViewFit(BaseModel):
    fits: bool
    notes: list[str]


class VariantView(BaseModel):
    rank: int
    cases: int
    share: float
    cumulative_share: float
    path: list[VariantStep]
    views: dict[str, ViewFit]  # done · documented


class HiddenWorkItem(BaseModel):
    activity: str
    cases: int
    share: float
    role_id: str | None
    after_element_id: str | None
    after_label: str
    before_element_id: str | None
    before_label: str


class LogVariants(BaseModel):
    log_id: str
    log_name: str
    cases: int
    too_few: int
    variants: list[VariantView]
    hidden_work: list[HiddenWorkItem]


class SystemVariants(BaseModel):
    logs: list[LogVariants]
    too_few_steps: list[str]
