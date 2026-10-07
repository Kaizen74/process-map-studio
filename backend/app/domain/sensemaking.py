"""Models for the Work-Sense translation (PRD §3.12): the marker lexicon and its pre-tags."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

AccountType = Literal["official", "lived", "unclear"]

# Claim types of what else an interview tells (C1): stored with the claims and checked like them,
# but never grouped into steps by S2; S3c links them to the map's steps.
SENSE_CLAIM_TYPES = frozenset({"story", "know_how", "sme_term", "decision_info", "capability"})


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

View = Literal["done", "documented"]  # As done (default) · As documented
ViewMembership = Literal["both", "done_only", "documented_only"]
SequenceBasis = Literal["explicit_order", "document_order", "dependency", "narration_order"]


class StepPosition(BaseModel):
    """Where one of a step's verified claims sits in its source (the order of its passages)."""

    source_id: str
    seq: int
    lived: bool = False  # an interview claim giving the lived account
    explicit: bool = False  # it confirmed an explicit-order marker ("first", "then", "T-90")
    # The guide questions its passages answer (Step A), e.g. ["L2"]; rule 9 (K2) reads them.
    question_ids: list[str] = []


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
    added_by_owner: bool = False  # Eric put the step in the flow himself: its order is stated
    lane: str = ""
    phase: str = ""  # rule 9 (K2): a practice step nests under a landscape activity of its phase
    # Rule 8 (C3): the information the step passes on and the information it receives, in the
    # SME's terms, from the decision-information items linked to it (any interview).
    gives: list[str] = []
    takes: list[str] = []


class TranslationEdge(BaseModel):
    id: str | None = None  # None for a line translation adds
    from_id: str
    to_id: str
    kind: str
    label: str = ""


class TranslatedEdge(TranslationEdge):
    sequence_basis: SequenceBasis
    view_membership: ViewMembership
    information_payload: str | None = None  # rule 8: what passes across, in the SME's terms


class TranslationQuestion(BaseModel):
    element_id: str
    question: str
    reason: Literal["sequence", "not_described", "information"]


class Translation(BaseModel):
    element_views: dict[str, ViewMembership]
    edges: list[TranslatedEdge]  # the existing lines first, then the added ones
    questions: list[TranslationQuestion]


# --- Coverage report (§3.12.8; C4) -------------------------------------------------------------

CoverageStatus = Literal["covered", "thin", "missing"]


class CoverageDimension(BaseModel):
    status: CoverageStatus
    evidence_count: int
    note: str = ""  # what the count is made of, in plain words (step labels, never names)


class FollowUpQuestion(BaseModel):
    """A ready-to-ask question for a thin or missing dimension, word for word from the bank."""

    dimension: str
    question_id: str
    question: str
    about: str = ""  # the step (or lines) it is about


class ReflectiveProbe(BaseModel):
    """F2 (Appendix F): an SME's own verified words played back to them in a follow-up."""

    question_id: str
    question: str
    quote: str
    source_id: str
    anchor: str
    speaker_role: str


class CoverageReport(BaseModel):
    version_id: str
    dimensions: dict[str, CoverageDimension]
    follow_up_questions: list[FollowUpQuestion]
    probes: list[ReflectiveProbe] = []


# --- Validation session pack (Appendix F.7, criterion 75; C6) ----------------------------------


class PackStep(BaseModel):
    label: str
    role: str = ""


class PackContrast(BaseModel):
    """One step whose As done and As documented accounts differ, side by side, unjudged."""

    step: str
    done: str
    documented: str


class ValidationPackInput(BaseModel):
    """What the pack is made of, names already hidden by the caller."""

    process: str
    version_label: str
    steps: list[PackStep] = []  # the As done view, in process order
    gaps: list[tuple[str, str]] = []  # "not described" between these two steps
    contrasts: list[PackContrast] = []
    strengths: list[str] = []
    weaknesses: list[str] = []
    questions: list[tuple[str, str]] = []  # (the step it is about, or "", the question)
    stamp: str = ""


# --- Emerging themes (Appendix E tier 3, criterion 58; C7b) ----------------------------------


class ThemeFragment(BaseModel):
    claim_id: str
    text: str
    quote: str
    fragment_type: str
    source_id: str
    anchor: str


class ThemeView(BaseModel):
    id: str
    version_id: str | None
    theme: str
    basis: str
    status: str  # proposed · accepted · dismissed
    note: str
    fragments: list[ThemeFragment]
    created_at: str


class ThemeRecord(BaseModel):
    """A stored emerging theme (what the repository returns)."""

    model_config = {"from_attributes": True}

    id: str
    engagement_id: str
    version_id: str | None
    theme: str
    fragment_ids: list[str]
    basis: str
    status: str
    note: str
    created_at: str


class ThemeProposal(BaseModel):
    """A theme as S3c proposed it, before the app's checks: its name, the story claims behind
    it and the basis."""

    theme: str
    claim_ids: list[str]
    basis: str


class ThemePatch(BaseModel):
    model_config = {"extra": "forbid"}

    status: str
    theme: str | None = None
    note: str | None = None


class BoundaryClaim(BaseModel):
    """One checked claim behind a step, as the lane-boundary check reads it (C8): the guide
    question its passage answers, the role it names as doing the work, its words (names hidden)."""

    question_id: str = ""
    responsible: str = ""
    text: str = ""


class BoundaryStep(BaseModel):
    element_id: str
    label: str
    lane_role: str
    claims: list[BoundaryClaim]


class LaneBoundaryFinding(BaseModel):
    """Where the interviews describe teams' activities overlapping or falling between them
    (PRD F.4 L5, F.6 F1 and F4, criterion 76). Advisory: never changes the map."""

    element_id: str
    label: str
    kind: Literal["shared_delivery", "gap", "boundary"]
    responsible: str
    consulted: list[str]
    note: str
    question_ids: list[str]


# --- Exceptions, rework and workarounds (X2, 2026-10-06; API_CONTRACT.md → exceptions) ---

StepRoute = Literal["usual", "exception", "variation"]


class ExceptionStepInput(BaseModel):
    """One step of a view as the exceptions check reads it: its place on the map and the SME's
    own words from its verified lived claims (names already hidden by the caller)."""

    element_id: str
    label: str
    kind: str
    lane: str = ""
    condition: str = ""  # a variation condition ("on a busy wave")
    stated_reason: str = ""
    frequency: str = ""
    practiced_only: bool = False
    workaround_story: bool = False


class ExceptionEdgeInput(BaseModel):
    from_id: str
    to_id: str
    kind: str
    label: str = ""


class ExceptionStep(BaseModel):
    element_id: str
    label: str
    route: StepRoute
    workaround: bool
    condition: str


class RouteExit(BaseModel):
    kind: Literal["rejoins", "loops_back", "ends"]
    element_id: str
    label: str
    edge_label: str


class ExceptionRoute(BaseModel):
    id: str
    kind: Literal["exception", "variation"]
    from_element_id: str
    from_label: str
    condition: str
    element_ids: list[str]
    labels: list[str]
    lanes: list[str]
    exits: list[RouteExit]
    handoffs: int
    frequency: str
    stated_reason: str


class ReworkLoop(BaseModel):
    from_element_id: str
    from_label: str
    to_element_id: str
    to_label: str
    label: str


class Workaround(BaseModel):
    element_id: str
    label: str
    lane: str
    condition: str
    stated_reason: str
    frequency: str
    basis: Literal["stated_reason", "story"]


class ExceptionQuestion(BaseModel):
    question_id: str
    wording: str
    about: str


class ExceptionSummary(BaseModel):
    steps: int
    usual_steps: int
    exception_steps: int
    variation_steps: int
    off_usual_share: float
    routes: int
    rework_loops: int
    workarounds: int
    extra_handoffs: int
    frequency_stated: int


class ExceptionReport(BaseModel):
    view: View
    summary: ExceptionSummary
    steps: list[ExceptionStep]
    routes: list[ExceptionRoute]
    loops: list[ReworkLoop]
    workarounds: list[Workaround]
    questions: list[ExceptionQuestion]
