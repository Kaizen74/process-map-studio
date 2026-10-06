"""What the export renderers read (PRD §7.3, `services/exports.py`): the graph of the version plus
the few facts the graph doesn't carry. Everything here has already had names on the redaction list
replaced by roles; none of it is a verbatim quote or an image."""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.graph import Graph
from app.domain.quality import QualityCard
from app.domain.sensemaking import ExceptionReport


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


class ExportStory(BaseModel):
    """A story fragment as the SME labelled it (§7.3 section 1): never the verbatim quote."""

    label: str
    fragment_type: str  # B.31
    steps: list[str]
    where: str  # "<source name> <anchor>"


class ExportCapability(BaseModel):
    """A strength to preserve or a weakness to improve, by capability dimension (B.36)."""

    kind: str  # strength · weakness
    dimension: str
    text: str
    steps: list[str]


class ExportTerm(BaseModel):
    term: str
    plain_meaning: str
    steps: list[str]


class ExportKnowHow(BaseModel):
    """One line per decision point (§7.3 section 2): knowledge risk and the dominant ASHEN
    category (the one with most items; "none described" when every category is empty)."""

    element_id: str
    knowledge_risk: str
    dominant: str


class ExportRealityGap(BaseModel):
    """A reality-gap finding of a finalised documents-vs-practice analysis (§3.12.7)."""

    gap_class: str  # B.32 (unexplained when no reason was stated)
    title: str
    stated_reason: str


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
    # PRD v1.10-1.11 §7.3 (K3, 2026-10-06): the sensemaking content, both views and the optional
    # modules. Graphs per view ("done", "documented") carry their own lines and "not described"
    # connectors; empty for maps drafted before v1.10.
    view_graphs: dict[str, Graph] = {}
    stories: list[ExportStory] = []
    capabilities: list[ExportCapability] = []
    glossary: list[ExportTerm] = []
    know_how: list[ExportKnowHow] = []
    reality_gaps: list[ExportRealityGap] = []
    #: Exceptions, rework and workarounds of the As done view (X6, 2026-10-06, Eric's decision).
    exceptions: ExceptionReport | None = None
    #: Optional modules in use (§3.13-3.15; decision A: off until Eric turns them on in P10b).
    value_calculator_on: bool = False
    system_records_on: bool = False
