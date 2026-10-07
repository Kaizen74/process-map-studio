"""Models for the system records module (PRD §3.13, P10b): the data request template first."""

from __future__ import annotations

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
    outside_window: int
    timestamp_format: str
    missing_columns: list[str]
    refused: bool
    refusal: str


class ParsedLog(BaseModel):
    events: list[LogEvent]
    report: ValidationReport
