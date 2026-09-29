"""What the export renderers read (PRD §7.3, `services/exports.py`): the graph of the version plus
the few facts the graph doesn't carry. Everything here has already had names on the redaction list
replaced by roles; none of it is a verbatim quote or an image."""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.graph import Graph
from app.domain.quality import QualityCard


class SourceEntry(BaseModel):
    """One row of the source registry: what it is, never what it says."""

    id: str
    name: str
    kind: str  # B.1
    version_date: str
    owner: str
    controlled_copy: bool


class ExportQuestion(BaseModel):
    question: str
    phase_name: str
    element_label: str
    reason: str


class ExportCause(BaseModel):
    """A cause-library entry pending validation, on one of the map's steps (PRD §7.3 section 3)."""

    element_label: str
    divergence_type: str
    pattern: str  # observed [O]
    inferred_cause: str  # [I]; empty when not known yet


class ExportGapReport(BaseModel):
    """A finalised gap analysis of the version (PRD §7.3 section 3)."""

    mode: str  # internal · external
    finalised_at: str
    accepted: list[str]  # titles of findings added as a question, cause or step


class ExportInput(BaseModel):
    graph: Graph
    sources: list[SourceEntry]
    #: ISO date and time the version was published ("" while it is a draft).
    published_at: str
    #: The owner's name from Settings, shown as the validator.
    validated_by: str
    #: Open validation questions, for the offline SME session.
    open_questions: list[ExportQuestion]
    #: None while the card has not been worked out (the renderers say so).
    quality_card: QualityCard | None = None
    #: Pending cause-library entries for the map's steps, and finalised gap reports (phase P10).
    causes: list[ExportCause] = []
    gap_reports: list[ExportGapReport] = []
