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
