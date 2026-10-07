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
