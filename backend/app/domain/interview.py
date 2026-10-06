"""Interview question bank and standard templates (PRD v1.10 Appendix F, §3.12.8).

`backend/app/prompts/question_bank.json` is the single source of the questions; these models read
it. A template is built from the bank only (no AI, no engagement data), so it is the same for
every interviewer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.enums import InterviewType

Priority = Literal["core", "standard"]


class BankQuestion(BaseModel):
    """One question of Appendix F. `wording` is what the interviewer says (the transcript matcher
    compares against it); `lead_in` is the cue before it ("Read-back:") and `note` a label
    ("the standard question"), kept apart from the spoken words."""

    id: str
    movement: str
    wording: str
    lead_in: str = ""
    note: str = ""
    probes: list[str] = []
    targets: list[str] = []
    translation: str = ""
    built_from: str = ""  # F-series: what the reflective probe is generated from
    priority: Priority = "standard"


class Movement(BaseModel):
    id: str
    name: str
    minutes: int | None = None


class TemplateSection(BaseModel):
    """One row of the F.9 minute plan and the questions asked in it."""

    label: str
    minutes: int
    rows: list[str] = []
    blank_rows: int = 0
    stories: list[str] = []  # story questions, each followed by the signifiers
    signifiers: list[str] = []
    note: str = ""


class TemplateSpec(BaseModel):
    title: str
    minutes: int
    who: str
    purpose: str
    sections: list[TemplateSection]


class Opener(BaseModel):
    record: str
    text: str
    follow_up: str
    note: str


class QuestionBank(BaseModel):
    version: str
    source: str
    note: str = ""
    principles: list[str]
    opener: Opener
    movements: list[Movement]
    questions: list[BankQuestion]
    templates: dict[InterviewType, TemplateSpec]
    header_fields: list[str]
    coverage_checklist: list[str]
    close_items: list[str]
    footer: str

    def question(self, question_id: str) -> BankQuestion:
        return next(q for q in self.questions if q.id == question_id)

    def template_ids(self, kind: InterviewType) -> list[str]:
        """Every question ID a template of this type asks, in order."""
        ids: list[str] = []
        for section in self.templates[kind].sections:
            ids += section.rows
            ids += [x for story in section.stories for x in (story, *section.signifiers)]
        return list(dict.fromkeys(ids))


class TemplatePlanRow(BaseModel):
    label: str
    minutes: int


class TemplateSummary(BaseModel):
    """What the home screen and the Interview screen show about each template (no file)."""

    type: InterviewType
    title: str
    minutes: int
    who: str
    purpose: str
    plan: list[TemplatePlanRow]
    question_count: int = Field(description="Question IDs the template asks")
    bank_version: str


# --- A generated interview document (standard template now; tailored guides from P4c) ------


class DocumentRow(BaseModel):
    """One row of a movement table: ID · Question · Probes · Minutes · Notes (notes left blank)."""

    id: str = ""  # blank for rows the interviewer fills in (role module, reflective probes)
    lead_in: str = ""
    wording: str = ""
    note: str = ""
    probes: list[str] = []
    minutes: str  # "2", "1½", "½", or "in story" for a signifier asked within a story
    signifier: bool = False
    # F.8 rule 9: what the guide stores for every question, for the editor and the matcher. Not
    # printed in the files (the F.9 layout has no column for them).
    movement: str = ""
    targets: list[str] = []
    priority: str = ""
    # SOP-derived probes (F.8 rule 5), only ever on M6.5: printed after the probes, shown in the
    # editor as "held back to avoid anchoring the SME".
    held_back: list[str] = []


class DocumentTable(BaseModel):
    label: str
    minutes: int
    note: str = ""
    rows: list[DocumentRow]


class InterviewDocument(BaseModel):
    """Everything a template (or a tailored guide) prints, in the F.9 layout order."""

    kind: InterviewType
    title: str  # item 1
    stamp: str  # item 1: question bank version · Process Map Studio
    header_fields: list[str]  # item 2
    # A tailored guide's filled-in header entries (G1); empty for the standard templates.
    header_values: dict[str, str] = {}
    record: str  # item 3
    opener: list[str]
    opener_note: str
    minutes: int  # item 4
    plan: list[TemplatePlanRow]
    principles: list[str]  # item 5
    tables: list[DocumentTable]  # item 6
    coverage_checklist: list[str]  # item 7
    close_items: list[str]  # item 8
    footer: str  # item 9
    # A tailored guide only: why the role-module rows were left blank, in plain words (C5b); not
    # printed in the files.
    generation_note: str = ""


class TemplateFile(BaseModel):
    """A template ready to download (Word bytes or Markdown encoded as UTF-8)."""

    filename: str
    media_type: str
    content: bytes


class QuestionMatch(BaseModel):
    """Which question an interviewer turn asks (§3.12.10 step A)."""

    question_id: str
    method: Literal["tag", "wording"]
    score: float


class Turn(BaseModel):
    """One transcript turn as step A sees it."""

    seq: int
    is_interviewer: bool
    text: str


class AnsweredTurn(BaseModel):
    """A turn's place in the question-anchored segmentation (§3.12.10 step A): an interviewer turn
    carries the question it asks (`asked`); each SME turn carries the question of the answer block
    it belongs to; `None` before the first matched question."""

    seq: int
    question_id: str | None
    asked: bool
    match: QuestionMatch | None = None


# --- Interviewee profiles (API_CONTRACT.md → Interviewee profiles; F.8 rule 1; C5a) ------------


class ProfileInput(BaseModel):
    """A new interviewee profile: a role or stakeholder group, never a person (constraint 10)."""

    model_config = {"extra": "forbid"}

    role_id: str | None = None
    stakeholder_group: str = ""
    interview_type: str
    referred_by_role: str = ""
    previous_profile_id: str | None = None


class ProfilePatch(BaseModel):
    """Only the fields sent change."""

    model_config = {"extra": "forbid"}

    role_id: str | None = None
    stakeholder_group: str | None = None
    interview_type: str | None = None
    referred_by_role: str | None = None
    previous_profile_id: str | None = None


class ProfileView(BaseModel):
    id: str
    engagement_id: str
    role_id: str | None
    role_name: str
    stakeholder_group: str
    interview_type: str
    referred_by_role: str
    previous_profile_id: str | None
    created_at: str


# --- Tailored guides (API_CONTRACT.md → Tailored interview guides; F.8; G1) --------------------


class FollowUp(BaseModel):
    """One question for a Follow-up guide's blank rows: a bank ID (F2, F5, F6 or the M-question
    of a thin dimension), its wording, and the step it is about ("" if none)."""

    question_id: str
    wording: str
    about: str = ""


class GuideContext(BaseModel):
    """What a guide is tailored from (F.8 rules 1, 2, 5, 7), names already hidden by the caller.
    Every text is filled in only if it passes the wording and hidden-name checks."""

    interview_type: InterviewType
    who: str  # "Ramp agent · Ramp": the profile's role and stakeholder group
    process: str = ""
    scope: str = ""  # "the Load control process, from Flight scheduled to Final load sheet issued"
    business: str = ""
    area: str = ""
    referrer_role: str = ""
    role: str = ""
    stakeholder_group: str = ""
    topics: str = ""  # follow-up: what the earlier interview covered
    sop_steps: list[str] = []  # practice M6.5: steps only the documents describe, process order
    follow_ups: list[FollowUp] = []  # follow-up: the rows to fill, in order (rule 7)
    hidden_terms: list[str] = []


class RoleQuestion(BaseModel):
    """One role-module question as Claude proposed it (IG_generate), before the app's checks."""

    based_on: str
    wording: str
    probes: list[str] = []


class RoleModuleCheck(BaseModel):
    """The role-module questions kept (as guide rows) and why the others were left out."""

    kept: list[DocumentRow]
    left_out: list[tuple[str, str]] = []  # (wording, reason in plain words)


class RowEdit(BaseModel):
    model_config = {"extra": "forbid"}

    id: str = ""
    wording: str = ""
    probes: list[str] = []
    held_back: list[str] = []


class TableEdit(BaseModel):
    model_config = {"extra": "forbid"}

    label: str
    rows: list[RowEdit]


class GuideEdit(BaseModel):
    """Eric's edits to a guide (C5c): every section and row, in order."""

    model_config = {"extra": "forbid"}

    tables: list[TableEdit]


class GuideStarted(BaseModel):
    job_id: str
    profile_id: str


class GuideInput(BaseModel):
    model_config = {"extra": "forbid"}

    profile_id: str


class GuideSummary(BaseModel):
    """The latest guide of one interviewee, without its content (the Interviewees list)."""

    id: str
    profile_id: str | None
    interview_type: str
    version: int
    created_at: str


class GuideView(BaseModel):
    id: str
    engagement_id: str
    profile_id: str | None
    interview_type: str
    version: int
    edited: bool
    created_at: str
    document: InterviewDocument
