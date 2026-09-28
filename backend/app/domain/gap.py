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
