"""Answer formats for the AI stages (PRD §3.3 `schemas_ai/`, §3.8 G2), as Pydantic models.

`ai_service.strict_schema` turns each model into the JSON schema sent as structured output, and
every answer is validated against the same model (constraint 14). Every field is required in the
answer; empty strings and lists stand for "nothing to say".
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ClaimType = Literal[
    "activity",
    "decision",
    "approval",
    "handoff",
    "raci",
    "duration",
    "kpi",
    "constraint",
    "trigger",
    "exception",
    "threshold",
]


class S1Claim(BaseModel):
    """One statement about the process, tied to the passages it comes from (G2)."""

    claim_type: ClaimType
    text: str = Field(description="The claim in one plain sentence, naming roles, never people")
    responsible_role: str = Field(description="Role that does the work, or empty")
    accountable_role: str = Field(description="Role that approves or answers for it, or empty")
    decider_role: str = Field(description="Role that makes the routing call, or empty")
    mechanism: Literal["rule_based", "judgment", "none"]
    duration_text: str = Field(description="Time as stated in the passages, or empty")
    threshold: str = Field(description="Rule or threshold as stated, or empty")
    segment_ids: list[str] = Field(description="IDs of the segments the claim comes from")
    quote: str = Field(description="Verbatim words copied from those segments, at most 40 words")
    provenance: Literal["O", "I"] = Field(description="O observed in the text, I inferred from it")
    basis: str = Field(description="For I: how it follows from the cited text; for O: empty")


class S1Unknown(BaseModel):
    """Something the process needs that the passages don't say (G8): becomes a question."""

    question: str
    segment_ids: list[str]


class S1Output(BaseModel):
    claims: list[S1Claim]
    unknowns: list[S1Unknown]


class S0OcrOutput(BaseModel):
    """S0_ocr_page: the words on one scanned page, transcribed verbatim in reading order."""

    lines: list[str]
