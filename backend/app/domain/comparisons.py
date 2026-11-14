"""Comparing countries (API_CONTRACT.md → Comparing countries; PRD §3.19; DECISIONS 98)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.domain.compass import GradeView


class ComparisonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_engagement_id: str
    other_engagement_id: str
    reference_version_id: str | None = None
    other_version_id: str | None = None


class PairDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_key: str | None = None
    other_key: str | None = None
    decision: str  # confirmed · only_reference · only_other · clear


class DifferenceDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str  # class · keep · dismiss · reopen
    reason_class: str | None = None
    reason_note: str = ""
    grade: str | None = None
    note: str = ""


class Candidate(BaseModel):
    """An engagement mapping the same process, offered for a comparison."""

    engagement_id: str
    name: str
    country: str
    process_name: str
    why: str
    published_version_id: str | None
    published_label: str | None


class SideView(BaseModel):
    engagement_id: str
    name: str
    country: str
    version_id: str
    version_label: str
    newer_version_label: str | None


class StepView(BaseModel):
    key: str
    code: str
    label: str
    kind: str
    lane: str
    phase: str
    order: int


class PairView(BaseModel):
    reference_key: str | None
    other_key: str | None
    status: str  # B.54
    why: str


class DifferenceView(BaseModel):
    key: str
    kind: str  # B.53
    topic: str  # B.52
    title: str
    reference_value: str
    other_value: str
    figure: str
    reference_key: str | None
    other_key: str | None
    status: str  # B.55
    code: str | None
    reason_class: str | None
    reason_note: str
    note: str
    grade: GradeView
    grade_reason: str


class DifferenceCounts(BaseModel):
    open: int = 0
    kept: int = 0
    classed: int = 0
    dismissed: int = 0


class SuggestJob(BaseModel):
    job_id: str
    status: str


class ComparisonView(BaseModel):
    id: str
    rules_version: str
    reference: SideView
    other: SideView
    same_process: str
    steps: dict[str, list[StepView]]  # reference, other
    pairs: list[PairView]
    differences: list[DifferenceView]
    no_longer_found: list[DifferenceView]
    counts: DifferenceCounts
    suggest_job: SuggestJob | None


class ComparisonSummary(BaseModel):
    id: str
    reference: SideView
    other: SideView
    differences: DifferenceCounts


class SuggestStarted(BaseModel):
    job_id: str
    comparison_id: str


# --- Stored rows (repository) ---------------------------------------------------------------


class ComparisonRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reference_engagement_id: str
    other_engagement_id: str
    reference_version_id: str
    other_version_id: str
    suggest_job_id: str | None


class PairRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reference_key: str | None
    other_key: str | None
    status: str
    why: str


class DifferenceRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    diff_key: str
    title: str
    status: str
    reason_class: str | None
    reason_note: str
    grade: str | None
    note: str
