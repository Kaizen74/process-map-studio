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


# --- S2 Canonicalise (PRD §3.7) -----------------------------------------------------------------


class S2Step(BaseModel):
    """One canonical step: the verified claims from any source that describe it."""

    ref: str = Field(description="A short ID for this step, e.g. st1, unique in the answer")
    kind: Literal["activity", "decision", "approval"]
    label: str = Field(description="Short verb phrase in sentence case, at most 32 characters")
    lane_role: str = Field(
        description="Activity: the role that does it; approval: the role that approves; "
        "decision: the role that makes the routing call"
    )
    claim_refs: list[str] = Field(description="IDs of the claims that describe this step")


class S2Role(BaseModel):
    """A role the claims name that is not in the supplied role list yet."""

    name: str
    aliases: list[str]


class S2Merge(BaseModel):
    """Steps that may be the same step described differently; Eric decides below 0.80."""

    step_refs: list[str] = Field(description="Two or more step refs from this answer")
    proposed_label: str = Field(description="Label for the merged step, at most 32 characters")
    similarity: float = Field(description="How likely they are the same step, from 0 to 1")


class S2Output(BaseModel):
    steps: list[S2Step]
    new_roles: list[S2Role]
    merge_proposals: list[S2Merge]


# --- S3 Calibrate (PRD §3.7) --------------------------------------------------------------------


class S3Stance(BaseModel):
    """What the supplied part of one source says about one step (G2: cited and quoted)."""

    step_ref: str = Field(description="The step's ID from the <steps> list")
    stance: Literal["supports", "contradicts"]
    segment_ids: list[str] = Field(description="IDs of the segments that address the step")
    quote: str = Field(description="Verbatim words copied from those segments, at most 40 words")
    divergence_type: Literal[
        "sequence", "ownership", "threshold", "trigger", "exception", "omission", "none"
    ]
    divergence_note: str = Field(
        description="For a disagreement: one sentence saying what differs, or empty"
    )


class S3Output(BaseModel):
    stances: list[S3Stance]


# --- S3b Verify (PRD §3.8 G6) -------------------------------------------------------------------


class S3bVerdict(BaseModel):
    claim_ref: str = Field(description="The claim's ID from the <claim> list")
    verdict: Literal["supported", "partial", "not_supported"]
    reason: str = Field(description="One sentence: what the passages do or do not say")


class S3bOutput(BaseModel):
    verdicts: list[S3bVerdict]
