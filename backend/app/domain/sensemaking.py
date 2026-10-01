"""Models for the Work-Sense translation (PRD §3.12): the marker lexicon and its pre-tags."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

AccountType = Literal["official", "lived", "unclear"]


class LexiconFamily(BaseModel):
    pretag: str
    phrases: list[str]


class Lexicon(BaseModel):
    """`marker_lexicon.json` (§3.12.10 Step B), stamped with the codebook version."""

    version: str
    codebook_version: str
    families: dict[str, LexiconFamily]


class MarkerTag(BaseModel):
    """One pre-tag: a hint for the model to confirm or reject with a quote, never evidence."""

    family: str
    pretag: str
    phrase: str  # as it appears in the text
    start: int
    end: int


class SentenceAccount(BaseModel):
    """The account a sentence gives (§3.12.3): official, lived or unclear, with the cue found."""

    index: int
    text: str
    account_type: AccountType
    cue: str


# --- Translation into views (PRD §3.12.10 step C rules 1-7, §3.12.11) ---------------------------

ViewMembership = Literal["both", "done_only", "documented_only"]
SequenceBasis = Literal["explicit_order", "document_order", "dependency", "narration_order"]


class StepPosition(BaseModel):
    """Where one of a step's verified claims sits in its source (the order of its passages)."""

    source_id: str
    seq: int
    lived: bool = False  # an interview claim giving the lived account
    explicit: bool = False  # it confirmed an explicit-order marker ("first", "then", "T-90")


class TranslationStep(BaseModel):
    id: str
    kind: str
    label: str
    source_state: str
    provenance: str
    interview: list[StepPosition] = []
    documents: list[StepPosition] = []
    handoff_in: str = ""
    handoff_out: str = ""


class TranslationEdge(BaseModel):
    id: str | None = None  # None for a line translation adds
    from_id: str
    to_id: str
    kind: str
    label: str = ""


class TranslatedEdge(TranslationEdge):
    sequence_basis: SequenceBasis
    view_membership: ViewMembership


class TranslationQuestion(BaseModel):
    element_id: str
    question: str
    reason: Literal["sequence", "not_described"]


class Translation(BaseModel):
    element_views: dict[str, ViewMembership]
    edges: list[TranslatedEdge]  # the existing lines first, then the added ones
    questions: list[TranslationQuestion]
