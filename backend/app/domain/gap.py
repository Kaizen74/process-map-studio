"""Gap analysis data shapes (PRD §3.11, §3.5 gap_analyses/gap_findings/external_sources; P10)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import CheckOutcome


class BriefInput(BaseModel):
    """The generic facts a brief is drafted from (never quotes, times or passages)."""

    process_name: str
    industry: str
    adjacent_industries: list[str]
    step_labels: list[str]
    confidential_terms: list[str]
    hidden_names: list[str]


class Brief(BaseModel):
    """The research brief Eric edits and approves (PRD §3.11.2 step 1)."""

    model_config = ConfigDict(extra="forbid")

    process_name: str = Field(max_length=200)
    industry: str = Field(default="", max_length=200)
    adjacent_industries: list[str] = Field(default_factory=list, max_length=10)
    region: str = Field(default="", max_length=120)
    steps: list[str] = Field(default_factory=list, max_length=40)
    questions: list[str] = Field(default_factory=list, max_length=10)
    max_searches: int = Field(default=10, ge=3, le=20)
    allowed_domains: list[str] = Field(default_factory=list, max_length=64)
    blocked_domains: list[str] = Field(default_factory=list, max_length=64)
    recency_years: int = Field(default=5, ge=1, le=30)


class ScanHit(BaseModel):
    """One confidentiality-scan hit: the exact text to remove and why."""

    text: str
    reason: str


class CitedSource(BaseModel):
    """A citation captured from the research answer, with the app-assigned ID the structuring
    call must use (it can't introduce URLs or text of its own)."""

    id: str
    url: str
    title: str
    cited_text: str
    page_age: str = ""


class CitationCheck(BaseModel):
    """GX1-GX6 for one external finding: pass or the failing guardrail, plus the flags that keep
    a finding but lower its weight."""

    outcome: CheckOutcome
    weak: bool = False  # GX4: vendor or unknown sources only
    dated: bool = False  # GX5: every cited source older than the recency limit
    tiers_by_domain: dict[str, str] = Field(default_factory=dict)
    element_ids: list[str] = Field(default_factory=list)  # GX6: the references that exist
    dropped_element_ids: list[str] = Field(default_factory=list)


# --- Reports (API_CONTRACT → Gap analysis) -----------------------------------------------------


class GapEvidence(BaseModel):
    """One side of a comparison: a passage with its quote, or a source that is silent."""

    side: str  # documents · practice
    source_kind: str
    source_name: str
    stance: str
    segment_id: str | None = None
    anchor: str = ""
    quote: str = ""
    # External evidence only (Analysis B): side "external", source_kind the tier (B.24).
    url: str = ""
    tier: str = ""
    page_age: str = ""
    citation_id: str = ""


class GapElementRef(BaseModel):
    id: str
    label: str


class GapFindingView(BaseModel):
    id: str
    section: str  # fact · interpretation · recommendation
    finding_type: str  # B.22 or B.23
    title: str
    text: str
    element_ids: list[str]
    elements: list[GapElementRef]
    evidence: list[GapEvidence]
    basis: str
    provenance: str  # O · I · R, or empty for a question
    severity: str | None
    evidence_strength: str
    comparison: str | None
    verification_status: str
    rejection_guardrail: str
    rejection_reason: str
    verifier_verdict: str
    needs_check: bool
    question: str
    notes: list[str]
    disposition: str
    disposition_note: str
    created_item_ref: str


class GapCounts(BaseModel):
    kept: int = 0
    rejected: int = 0
    open: int = 0
    needs_check: int = 0


class GapAnalysisView(BaseModel):
    id: str
    version_id: str
    version_label: str
    mode: str  # B.21
    status: str  # B.27
    job_id: str | None
    error: str
    created_at: str
    completed_at: str | None
    finalised_at: str | None
    notes: list[str]
    counts: GapCounts


class GapUsage(BaseModel):
    calls: int
    input_tokens: int
    output_tokens: int


class ScanResult(BaseModel):
    hits: list[ScanHit]


class BriefState(BaseModel):
    """The research brief, exactly what would be sent, whether Eric ticked "This brief contains no
    confidential information", and the confidentiality scan of the text."""

    brief: Brief
    text: str
    confirmed: bool
    scan: ScanResult


class GapBriefView(BaseModel):
    analysis: GapAnalysisView
    brief: BriefState


class BriefPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief: Brief
    confirmed: bool


class GapSourceView(BaseModel):
    id: str
    url: str
    title: str
    domain: str
    page_age: str
    tier: str
    returned_in_results: bool


class GapReport(BaseModel):
    analysis: GapAnalysisView
    findings: list[GapFindingView]
    rejected: list[GapFindingView]
    questions: list[GapFindingView]
    sources: list[GapSourceView]
    brief: BriefState | None
    usage: GapUsage | None
    search_count: int


class GapStarted(BaseModel):
    analysis_id: str
    job_id: str


class NewGapFinding(BaseModel):
    """A finding as a pipeline stores it (the repository adds the ID)."""

    section: str
    finding_type: str
    title: str
    text: str
    element_ids: list[str] = Field(default_factory=list)
    evidence: list[GapEvidence] = Field(default_factory=list)
    basis: str = ""
    provenance: str = ""
    severity: str | None = None
    evidence_strength: str = "strong"
    comparison: str | None = None
    verification_status: str = "verified"
    rejection_guardrail: str = ""
    rejection_reason: str = ""
    verifier_verdict: str = "not_run"
    question: str = ""
    notes: list[str] = Field(default_factory=list)


class StoredGapFinding(NewGapFinding):
    id: str
    disposition: str = "open"
    disposition_note: str = ""
    created_item_ref: str = ""


class GapAnalysisRecord(BaseModel):
    id: str
    version_id: str
    mode: str
    status: str
    model: str = ""
    search_count: int = 0
    created_at: str
    completed_at: str | None = None
    finalised_at: str | None = None
    brief: dict[str, object] | None = None
    brief_confirmed: bool = False
    brief_scan: dict[str, object] | None = None
    notes: list[str] = Field(default_factory=list)


class NewExternalSource(BaseModel):
    url: str
    title: str
    domain: str
    page_age: str
    tier: str
    returned_in_results: bool
