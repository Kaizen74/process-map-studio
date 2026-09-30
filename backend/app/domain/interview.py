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
