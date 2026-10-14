"""The leadership view (PRD §4 Views, §5.4 Leadership; phase P11): where the process jams and why,
kept in three separate parts (constraint 9). Every figure carries the steps behind it."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.reality import RealityFigures


class PhaseLinks(BaseModel):
    """The steps behind each figure of a phase."""

    work: list[str] = Field(default_factory=list)
    wait: list[str] = Field(default_factory=list)
    rework_loops: list[str] = Field(default_factory=list)
    handoffs: list[str] = Field(default_factory=list)
    divergence: dict[str, list[str]] = Field(default_factory=dict)


class PhaseFacts(BaseModel):
    phase_id: str | None
    name: str
    work_min: float
    wait_min: float
    rework_loops: int
    handoffs: int
    divergence_counts: dict[str, int]
    links: PhaseLinks


class Facts(BaseModel):
    phases: list[PhaseFacts]
    sources: int


class PhaseRef(BaseModel):
    phase_id: str | None
    name: str


class EvidenceWeight(BaseModel):
    supporting: int
    sources: int


class CauseConstraint(BaseModel):
    element_id: str
    label: str
    text: str
    is_key: bool


class CauseSummary(BaseModel):
    cause_type: str
    systemic: bool
    reason: str
    phases: list[PhaseRef]
    lanes: list[str]
    evidence_weight: EvidenceWeight
    confidence: float | None
    constraints: list[CauseConstraint]
    element_ids: list[str]


class Interpretation(BaseModel):
    causes: list[CauseSummary]


class LeadershipAiFlag(BaseModel):
    element_id: str
    label: str
    lane: str
    mechanism: str
    component: str
    input: str
    output: str
    handoff: str
    basis: str


class DecisionNeeded(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cause_type: str
    text: str = ""


class Recommendation(BaseModel):
    recoverable_wait_min: float
    recoverable_wait_element_ids: list[str]
    rework_loops: int
    rework_element_ids: list[str]
    ai_flags: list[LeadershipAiFlag]
    decisions_needed: list[DecisionNeeded]


class LeadershipVersion(BaseModel):
    id: str
    label: str
    state: str


class LeadershipView(BaseModel):
    version: LeadershipVersion
    facts: Facts
    interpretation: Interpretation
    recommendation: Recommendation
    # P13b (G17): while the Reality views switch is on, the figures Leadership shares with them,
    # read from the version's frozen Reality snapshot.
    reality: RealityFigures | None = None
