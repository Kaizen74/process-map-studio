"""The shared language with Eric's other apps (2026-11-12, DECISIONS 95): the Capability Compass
hand-off this app reads and the "What we are testing" items it keeps. IDs are stored exactly as
received; this app never mints an ID with a prefix it doesn't own."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

HANDOFF_FORMAT = "compass-handoff"
VERDICTS = ("open", "supported", "refuted")


class CompassLink(BaseModel):
    """What an engagement keeps of the hand-off it started from."""

    key: str
    pilot_ref: str
    cluster_ref: str
    cluster_name: str = ""
    cell_refs: list[str] = []
    interview_prompts: list[str] = []  # suggested probes only: never a claim, step or source
    ready: bool = True
    generated_at: str = ""


class HandoffPilot(BaseModel):
    ref: str
    cluster_ref: str
    cluster_name: str
    name: str
    process_name: str
    process_kpi: str
    industry: str
    in_scope_roles: list[str]
    interview_prompts: list[str]
    cell_refs: list[str]


class HandoffPrinciple(BaseModel):
    ref: str
    text: str
    refuted_by: str = ""


class HandoffPreview(BaseModel):
    key: str
    organisation: str
    generated_at: str
    ready: bool
    verdict: str
    open: list[str]
    pilots: list[HandoffPilot]
    principles: list[HandoffPrinciple]


class HandoffIn(BaseModel):
    handoff: Any = None


class CompassStart(BaseModel):
    """On POST /engagements: the file again and the pilot Eric chose."""

    handoff: Any = None
    pilot_ref: str = ""


class GradeView(BaseModel):
    """The shared grade of a finding (DECISIONS 96): the one in force, the one the rules
    suggest, and whether Eric chose it himself."""

    grade: str  # confirmed · indicated · hypothesis
    suggested: str
    chosen_by_owner: bool
    rules_version: str


class GradeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grade: str | None = None  # null: back to the suggested grade


class GradeChosen(BaseModel):
    """A discrepancy after Eric chose its grade (null: the suggested grade stands)."""

    item_id: str
    code: str
    grade_chosen: str | None


class TestingItem(BaseModel):
    id: str
    ref: str
    text: str
    refuted_by: str
    origin: str  # compass · owner
    verdict: str  # open · supported · refuted
    evidence_refs: list[str]
    note: str


class TestingCreate(BaseModel):
    ref: str = ""
    text: str = ""
    refuted_by: str = ""


class TestingPatch(BaseModel):
    verdict: str | None = None
    evidence_refs: list[str] | None = None
    note: str | None = None
    text: str | None = None
    refuted_by: str | None = None
