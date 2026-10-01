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


class S1MarkerReview(BaseModel):
    """A marker hint (§3.12.10 step B) the claim relies on or sets aside. A hint is never evidence:
    a confirmation counts only if its quote is found in the cited segments."""

    marker: str = Field(description="The hint as listed in the segment's markers attribute")
    confirmed: bool = Field(description="True if the cited words bear the hint out, else false")
    quote: str = Field(
        description="The words, copied exactly from the cited segments, that show it"
    )


class S1InterviewClaim(S1Claim):
    """An interview claim, with the account it gives (§3.12.3) and what translation needs
    (§3.12.10): stated reasons and variation conditions, in the SME's own words."""

    account_type: Literal["official", "lived", "unclear"] = Field(
        description="official: how it is meant to work; lived: what the SME does or did; "
        "unclear: neither is evident"
    )
    account_cue: str = Field(
        description="For official or lived: the cue words, copied exactly from the cited "
        "segments; for unclear: empty"
    )
    stated_reason: str = Field(
        description="The SME's own reason for working this way, copied exactly, or empty"
    )
    variation_condition: str = Field(
        description="For a variation: the condition it depends on, copied exactly (for example "
        "'on a busy wave'), or empty"
    )
    markers: list[S1MarkerReview] = Field(
        description="The marker hints on the cited segments that bear on this claim, each "
        "confirmed or set aside with a quote"
    )


class S1Unknown(BaseModel):
    """Something the process needs that the passages don't say (G8): becomes a question."""

    question: str
    segment_ids: list[str]


class S1Output(BaseModel):
    claims: list[S1Claim]
    unknowns: list[S1Unknown]


# --- What else an interview tells (PRD §3.12.2, §3.12.6, §3.12.10 rules 4 and 10; C1) -----------
# Each item is grounded like a claim (§3.12.9 rule 7): segment IDs and a verbatim quote; the SME's
# own words (signifiers, terms) must be found in the cited segments. `about` names the step or
# decision in plain words, so the items can be linked to the map's steps once they exist (S3c).


class S1Grounded(BaseModel):
    segment_ids: list[str] = Field(description="IDs of the segments it comes from")
    quote: str = Field(description="Verbatim words copied from those segments, at most 40 words")


class S1Story(S1Grounded):
    """A fragment: an anchored micro-narrative of a real case, kept even when told once."""

    label: str = Field(description="At most 12 words, in the SME's own wording where possible")
    fragment_type: Literal[
        "recent_case", "went_well", "went_badly", "surprise", "workaround", "other"
    ]
    signifiers: list[str] = Field(
        description="The SME's own words for the situation (for example how they classed it), "
        "each copied exactly from the cited segments"
    )
    frequency: str = Field(description="How often it happens, copied exactly, or empty")
    about: str = Field(description="The steps or decisions it concerns, in plain words")


class S1KnowHow(S1Grounded):
    """One ASHEN item at a knowledge disclosure point (a decision, approval or judgment)."""

    category: Literal["artefacts", "skills", "heuristics", "experience", "natural_talent"]
    text: str = Field(description="The item in one plain sentence, naming roles, never people")
    about: str = Field(description="The decision or step it is know-how for, in plain words")
    provenance: Literal["O", "I"]
    basis: str = Field(description="For I: how it follows from the cited text; for O: empty")


class S1Term(S1Grounded):
    """An SME term (glossary candidate): the word as the SME uses it and its plain meaning."""

    term: str = Field(description="The term, copied exactly from the cited segments")
    plain_meaning: str = Field(description="What it means, in plain words, from the segments")


class S1DecisionInfo(S1Grounded):
    """What a decision takes in and gives out (§3.12.10 rules 4 and 8), in the SME's terms."""

    about: str = Field(description="The decision, in plain words")
    cadence: Literal["daily", "weekly", "monthly", "annually", "exceptional", "none"] = Field(
        description="How often the decision is made, only if stated; otherwise none"
    )
    received: list[str] = Field(description="Information the decision receives")
    attended: list[str] = Field(description="Signals the decider pays attention to")
    wanted: list[str] = Field(description="Information the decider says they lack")
    communicated_via: list[str] = Field(description="How the decision is passed on")


class S1Capability(S1Grounded):
    """A strength or weakness the SME names (rule 10): Preserve or Improve."""

    kind: Literal["strength", "weakness"]
    dimension: Literal["skillset", "ways_of_working", "systems", "process", "structure"]
    text: str = Field(description="The note in one plain sentence, naming roles, never people")
    cause_type: Literal[
        "decision_rights", "system_fragmentation", "single_point_knowledge",
        "capacity_mismatch", "policy_control", "capability_gap", "none",
    ] = Field(description="For a weakness: its cause type (B.9); otherwise none")  # fmt: skip


class S1InterviewOutput(BaseModel):
    claims: list[S1InterviewClaim]
    unknowns: list[S1Unknown]
    stories: list[S1Story] = []
    know_how: list[S1KnowHow] = []
    terms: list[S1Term] = []
    decision_info: list[S1DecisionInfo] = []
    capability_notes: list[S1Capability] = []


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


# --- S4 Assemble (PRD §3.7) ---------------------------------------------------------------------

CauseType = Literal[
    "decision_rights",
    "system_fragmentation",
    "single_point_knowledge",
    "capacity_mismatch",
    "policy_control",
    "capability_gap",
    "none",
]


class S4Raci(BaseModel):
    role: str
    letter: Literal["R", "A", "C", "I"]


class S4Constraint(BaseModel):
    text: str = Field(description="The challenge or constraint in one sentence")
    cause_type: CauseType
    is_key: bool = Field(description="True for the one or two constraints that matter most")
    claim_refs: list[str] = Field(description="IDs of the claims that state it")


class S4AiFlag(BaseModel):
    component: Literal[
        "perception", "knowledge_base", "reasoning", "learning", "communication", "action"
    ]
    input: str
    output: str
    handoff: str
    basis: Literal["rule_based_automate_candidate", "judgment_support_only"]


class S4Variant(BaseModel):
    """How one version of the work does this step (§3.12.11 variant attributes), as the sources
    state it; empty strings where that version says nothing different."""

    owner: str = Field(description="The role that does or decides it in this version, or empty")
    threshold: str = Field(description="The rule or threshold as this version states it, or empty")
    time: str = Field(description="The time or deadline as this version states it, or empty")
    trigger: str = Field(description="What starts it in this version, or empty")


class S4Step(BaseModel):
    step_ref: str = Field(description="The step's ID from the <steps> list")
    claim_refs: list[str] = Field(description="Further claims this step's details come from")
    decision_mechanism: Literal["rule_based", "judgment", "none"]
    decider_role: str = Field(description="Decisions: the role that makes the call; else empty")
    rule_or_threshold: str
    escalation: str
    work_min: float | None = Field(description="Minutes of work as stated, or null")
    wait_min: float | None = Field(description="Minutes of waiting as stated, or null")
    duration_text: str = Field(description="Time as the sources state it, or empty")
    complexity: Literal["L", "M", "H", ""]
    kpi: str
    handoff_in: str
    handoff_out: str
    raci: list[S4Raci]
    k_risk: str = Field(description="Knowledge risk the claims show, or empty")
    constraints: list[S4Constraint]
    ai_flags: list[S4AiFlag] = Field(description="At most one")
    variant_done: S4Variant = Field(
        description="Where practice differs from the documents: the values the lived account gives"
    )
    variant_documented: S4Variant = Field(
        description="Where practice differs from the documents: the values the documents give"
    )


class S4Edge(BaseModel):
    from_ref: str = Field(description="start, a step ID, or end")
    to_ref: str = Field(description="start, a step ID, or end")
    kind: Literal["sequence", "yes", "no", "approve", "reject", "rework", "exception"]
    label: str = Field(description="Required on every exit of a decision or approval")


class S4Phase(BaseModel):
    name: str
    time_window: str = Field(description="As the sources state it, or empty")
    step_refs: list[str]


class S4Output(BaseModel):
    phases: list[S4Phase]
    steps: list[S4Step]
    edges: list[S4Edge]


# --- S5 Questions (PRD §3.7) --------------------------------------------------------------------


class S5Question(BaseModel):
    ref: str = Field(description="The item's ID from the <needed> list")
    question: str = Field(description="One question for the subject-matter expert")


class S5Output(BaseModel):
    questions: list[S5Question]


# --- Gap analysis A: documents vs practice (PRD §3.11.1; phase P10) ----------------------------

InternalFindingType = Literal[
    "dead_control_candidate",
    "undocumented_work",
    "ownership_mismatch",
    "threshold_gap",
    "sequence_gap",
    "trigger_gap",
    "exception_gap",
    "stale_documentation",
    "documentation_update",
]


class GAEvidence(BaseModel):
    segment_id: str = Field(description="ID of one <segment> the finding rests on")
    quote: str = Field(description="Verbatim words copied from that segment, at most 40 words")


class GAFinding(BaseModel):
    """One difference between the documents and practice, a pattern or likely cause behind
    differences, or a documentation update, tied to the passages of every side it compares."""

    finding_type: InternalFindingType
    section: Literal["fact", "interpretation", "recommendation"] = Field(
        description="fact: a difference; interpretation: a pattern or likely cause; "
        "recommendation: a documentation update"
    )
    title: str = Field(description="Short title in sentence case, naming roles, never people")
    text: str = Field(description="Plain-language description, one to three sentences")
    step_refs: list[str] = Field(description="IDs of the <divergence> items it is about")
    evidence: list[GAEvidence]
    basis: str = Field(
        description="For interpretation: how the SME passages show it; otherwise empty"
    )
    basis_segment_ids: list[str] = Field(
        description="For interpretation: the interview segments the basis cites; otherwise empty"
    )


class GAUnknown(BaseModel):
    """A cause the passages don't explain: a question for the SMEs, never a guess."""

    finding_type: InternalFindingType = Field(description="The kind of difference it is about")
    step_refs: list[str]
    question: str = Field(description="One short question an SME can answer")


class GAInternalOutput(BaseModel):
    findings: list[GAFinding]
    unknowns: list[GAUnknown]


class GAVerdict(BaseModel):
    finding_ref: str = Field(description="The finding's ID from the <finding> list")
    verdict: Literal["supported", "partial", "not_supported"]
    reason: str = Field(description="One sentence: what the passages do or do not say")


class GAVerifyOutput(BaseModel):
    verdicts: list[GAVerdict]


# --- Gap analysis B: external best practice (PRD §3.11.2; phase P10) ---------------------------

ExternalFindingType = Literal[
    "missing_step",
    "missing_control",
    "sequence_difference",
    "decision_rights_difference",
    "time_or_threshold_benchmark",
    "kpi_practice",
    "technology_enabler",
    "other_difference",
]


class GBFinding(BaseModel):
    """One practice the cited answer describes, compared with the current map. It may cite only the
    citation IDs it was given; it can't introduce URLs or text of its own."""

    finding_type: ExternalFindingType
    title: str = Field(description="Short title in sentence case")
    claim: str = Field(description="What the cited sources say, in one or two plain sentences")
    quote: str = Field(description="Verbatim words copied from the cited text, at most 40 words")
    citation_ids: list[str] = Field(description="IDs of the <citation> items that support it")
    step_refs: list[str] = Field(description="IDs of the map <step> items it concerns, or empty")
    comparison: Literal["absent", "different", "aligned"] = Field(
        description="absent: the map lacks it; different: the map does it differently; "
        "aligned: the map already does it"
    )


class GBStructureOutput(BaseModel):
    findings: list[GBFinding]
