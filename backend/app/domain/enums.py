"""Controlled vocabularies (PRD Appendix B). Generated from the PRD table; values are exact.

Member names spell out single-letter codes (Provenance.OBSERVED == "O") for readability."""

from __future__ import annotations

from enum import StrEnum


class SourceKind(StrEnum):
    """B.1 source kind."""

    INTERVIEW_TRANSCRIPT = "interview_transcript"
    SOP = "sop"
    MANUAL = "manual"
    JOB_DESCRIPTION = "job_description"
    EXECUTED_ARTEFACT = "executed_artefact"
    WORKING_SPREADSHEET = "working_spreadsheet"
    EMAIL_THREAD = "email_thread"
    POLICY_OR_CHARTER = "policy_or_charter"  # intent sources (§3.16, P13a): never drafted from
    OTHER = "other"


class ElementKind(StrEnum):
    """B.2 element kind."""

    ACTIVITY = "activity"
    DECISION = "decision"
    APPROVAL = "approval"
    START = "start"
    END = "end"


class Provenance(StrEnum):
    """B.3 provenance."""

    OBSERVED = "O"
    INFERRED = "I"
    RECOMMENDED = "R"


class SourceState(StrEnum):
    """B.4 source state."""

    CORROBORATED = "corroborated"
    DOCUMENTED_ONLY = "documented_only"
    PRACTICED_ONLY = "practiced_only"
    CONTESTED = "contested"
    TRACE_CONTRADICTED = "trace_contradicted"
    NOT_ASSESSED = "not_assessed"


class DivergenceType(StrEnum):
    """B.5 divergence type."""

    SEQUENCE = "sequence"
    OWNERSHIP = "ownership"
    THRESHOLD = "threshold"
    TRIGGER = "trigger"
    EXCEPTION = "exception"
    OMISSION = "omission"


class DecisionMechanism(StrEnum):
    """B.6 decision mechanism."""

    RULE_BASED = "rule_based"
    JUDGMENT = "judgment"
    NONE = "none"


class ReviewStatus(StrEnum):
    """B.7 review status."""

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    EDITED = "edited"
    REJECTED = "rejected"
    ADDED = "added"


class EdgeKind(StrEnum):
    """B.8 edge kind."""

    SEQUENCE = "sequence"
    YES = "yes"
    NO = "no"
    APPROVE = "approve"
    REJECT = "reject"
    REWORK = "rework"
    EXCEPTION = "exception"
    GAP = "gap"  # v1.10: a "not described" connector, As done view only (§3.12.10 rule 7)


class CauseType(StrEnum):
    """B.9 cause type."""

    DECISION_RIGHTS = "decision_rights"
    SYSTEM_FRAGMENTATION = "system_fragmentation"
    SINGLE_POINT_KNOWLEDGE = "single_point_knowledge"
    CAPACITY_MISMATCH = "capacity_mismatch"
    POLICY_CONTROL = "policy_control"
    CAPABILITY_GAP = "capability_gap"


class RaciLetter(StrEnum):
    """B.10 RACI letter."""

    RESPONSIBLE = "R"
    ACCOUNTABLE = "A"
    CONSULTED = "C"
    INFORMED = "I"


class AiComponent(StrEnum):
    """B.11 AI component."""

    PERCEPTION = "perception"
    KNOWLEDGE_BASE = "knowledge_base"
    REASONING = "reasoning"
    LEARNING = "learning"
    COMMUNICATION = "communication"
    ACTION = "action"


class AiBasis(StrEnum):
    """B.12 AI basis."""

    RULE_BASED_AUTOMATE_CANDIDATE = "rule_based_automate_candidate"
    JUDGMENT_SUPPORT_ONLY = "judgment_support_only"


class VersionState(StrEnum):
    """B.13 version state."""

    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class Stance(StrEnum):
    """B.14 evidence stance."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    SILENT = "silent"


class MergeDecision(StrEnum):
    """B.15 merge decision."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    SPLIT = "split"
    REJECTED = "rejected"


class ImageType(StrEnum):
    """B.16 image type."""

    WORKPLACE_PHOTO = "workplace_photo"
    SYSTEM_SCREENSHOT = "system_screenshot"
    EXECUTED_ARTEFACT = "executed_artefact"
    ILLUSTRATIVE_DIAGRAM = "illustrative_diagram"
    DOCUMENT_EXTRACT = "document_extract"


class ImageStatus(StrEnum):
    """B.17 image status."""

    SUGGESTED = "suggested"
    KEPT = "kept"
    DISCARDED = "discarded"


class VerificationStatus(StrEnum):
    """B.18 claim verification status."""

    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    OUTSIDE_FLOW = "outside_flow"  # passed the checks, about another flow (DECISIONS 81)


class VerifierVerdict(StrEnum):
    """B.19 verifier verdict."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    NOT_SUPPORTED = "not_supported"
    NOT_RUN = "not_run"


class Guardrail(StrEnum):
    """B.20 rejection guardrail."""

    G3 = "G3"
    G4 = "G4"
    G5 = "G5"
    G6 = "G6"
    G10 = "G10"
    GX1 = "GX1"
    GX2 = "GX2"
    GX3 = "GX3"
    GAV = "GAV"
    IX1 = "IX1"  # a design gap without both quotes, or over 25 words (P13a)
    IXV = "IXV"  # the intent verifier (IX_verify) turned it down (P13a)


class GapMode(StrEnum):
    """B.21 gap analysis mode."""

    INTERNAL = "internal"
    EXTERNAL = "external"


class InternalFindingType(StrEnum):
    """B.22 internal finding type."""

    # v1.11 system-record findings (§3.13.6; R6): made by the app from system logs, never by AI.
    HIDDEN_WORK = "hidden_work"
    OFFLINE_WORK = "offline_work"
    SEQUENCE_DRIFT = "sequence_drift"
    ESTIMATE_GAP = "estimate_gap"
    MEASURED_REWORK = "measured_rework"
    DEAD_CONTROL_CANDIDATE = "dead_control_candidate"
    UNDOCUMENTED_WORK = "undocumented_work"
    OWNERSHIP_MISMATCH = "ownership_mismatch"
    THRESHOLD_GAP = "threshold_gap"
    SEQUENCE_GAP = "sequence_gap"
    TRIGGER_GAP = "trigger_gap"
    EXCEPTION_GAP = "exception_gap"
    STALE_DOCUMENTATION = "stale_documentation"
    DOCUMENTATION_UPDATE = "documentation_update"
    # v1.10 reality gaps (§3.12.7)
    KNOWN_ADAPTATION = "known_adaptation"
    UNKNOWN_RULE = "unknown_rule"
    DISCLOSURE_GAP = "disclosure_gap"
    CONTROL_GAP = "control_gap"
    CONSTRAINT_MISMATCH = "constraint_mismatch"


class ExternalFindingType(StrEnum):
    """B.23 external finding type."""

    MISSING_STEP = "missing_step"
    MISSING_CONTROL = "missing_control"
    SEQUENCE_DIFFERENCE = "sequence_difference"
    DECISION_RIGHTS_DIFFERENCE = "decision_rights_difference"
    TIME_OR_THRESHOLD_BENCHMARK = "time_or_threshold_benchmark"
    KPI_PRACTICE = "kpi_practice"
    TECHNOLOGY_ENABLER = "technology_enabler"
    OTHER_DIFFERENCE = "other_difference"


class SourceTier(StrEnum):
    """B.24 external source tier."""

    STANDARDS_BODY = "standards_body"
    REGULATOR = "regulator"
    INDUSTRY_ASSOCIATION = "industry_association"
    ACADEMIC = "academic"
    PEER_OPERATOR = "peer_operator"
    CONSULTANCY = "consultancy"
    VENDOR = "vendor"
    NEWS = "news"
    OTHER = "other"


class Disposition(StrEnum):
    """B.25 finding disposition."""

    OPEN = "open"
    ADDED_QUESTION = "added_question"
    ADDED_CAUSE = "added_cause"
    ADDED_STEP = "added_step"
    DISMISSED = "dismissed"


class Severity(StrEnum):
    """B.26 severity."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GapStatus(StrEnum):
    """B.27 gap analysis status."""

    BRIEF_DRAFT = "brief_draft"
    QUEUED = "queued"
    RUNNING = "running"
    DRAFT_REPORT = "draft_report"
    FINALISED = "finalised"
    FAILED = "failed"


# --- PRD v1.10 sensemaking vocabularies (§3.12). Used from phases P4b and P4c. -------------


class AccountType(StrEnum):
    """B.28 account type."""

    OFFICIAL = "official"
    LIVED = "lived"
    UNCLEAR = "unclear"


class WorkType(StrEnum):
    """B.29 work type."""

    CLEAR = "clear"
    COMPLICATED = "complicated"
    COMPLEX = "complex"
    CHAOTIC = "chaotic"
    CONFUSED = "confused"
    NOT_CLASSIFIED = "not_classified"


class ConstraintType(StrEnum):
    """B.30 constraint type."""

    RIGID = "rigid"
    GOVERNING = "governing"
    ENABLING = "enabling"
    ABSENT = "absent"


class FragmentType(StrEnum):
    """B.31 fragment type."""

    RECENT_CASE = "recent_case"
    WENT_WELL = "went_well"
    WENT_BADLY = "went_badly"
    SURPRISE = "surprise"
    WORKAROUND = "workaround"
    OTHER = "other"


class GapClass(StrEnum):
    """B.32 gap class."""

    EFFECTIVE_ADAPTATION = "effective_adaptation"
    RISKY_DRIFT = "risky_drift"
    OBSOLETE_RULE = "obsolete_rule"
    UNEXPLAINED = "unexplained"


class AshenCategory(StrEnum):
    """B.33 ASHEN category."""

    ARTEFACTS = "artefacts"
    SKILLS = "skills"
    HEURISTICS = "heuristics"
    EXPERIENCE = "experience"
    NATURAL_TALENT = "natural_talent"


class SequenceBasis(StrEnum):
    """B.34 sequence basis, strongest first (system_trace since R5b, Appendix E tier 2)."""

    SYSTEM_TRACE = "system_trace"
    EXPLICIT_ORDER = "explicit_order"
    DOCUMENT_ORDER = "document_order"
    DEPENDENCY = "dependency"
    NARRATION_ORDER = "narration_order"


class ViewMembership(StrEnum):
    """B.35 view membership."""

    BOTH = "both"
    DONE_ONLY = "done_only"
    DOCUMENTED_ONLY = "documented_only"


class CapabilityDimension(StrEnum):
    """B.36 capability dimension."""

    SKILLSET = "skillset"
    WAYS_OF_WORKING = "ways_of_working"
    SYSTEMS = "systems"
    PROCESS = "process"
    STRUCTURE = "structure"


class DecisionCadence(StrEnum):
    """B.37 decision cadence."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ANNUALLY = "annually"
    EXCEPTIONAL = "exceptional"


class InterviewType(StrEnum):
    """B.38 interview type."""

    LANDSCAPE = "landscape"
    PRACTICE = "practice"
    FOLLOW_UP = "follow_up"


class ElementLevel(StrEnum):
    """B.39 element level."""

    LANDSCAPE = "landscape"
    PRACTICE = "practice"


# PRD v1.11 (P10b system records, value calculator, step disposition): vocabularies only until
# P10b uses them.
class SystemLogColumn(StrEnum):
    """B.40 system log column."""

    CASE_ID = "case_id"
    ACTIVITY = "activity"
    TIMESTAMP = "timestamp"
    END_TIMESTAMP = "end_timestamp"
    RESOURCE = "resource"
    ROLE = "role"
    SYSTEM = "system"
    CASE_ATTRIBUTE = "case_attribute"


class StepDisposition(StrEnum):
    """B.41 disposition."""

    DELETE = "delete"
    AUTOMATE_RULES = "automate_rules"
    AI_ASSISTED = "ai_assisted"
    HUMAN_APPROVES = "human_approves"
    KEEP_HUMAN = "keep_human"


class ValueEvidence(StrEnum):
    """B.42 value evidence label."""

    MEASURED = "measured"
    ESTIMATED = "estimated"
    MIXED = "mixed"
    ASSUMED = "assumed"


class AlignmentStatus(StrEnum):
    """B.43 alignment status."""

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    HIDDEN_WORK = "hidden_work"
    NO_SYSTEM_RECORD = "no_system_record"


# PRD v1.12 (P13 Reality views: intent layer, discrepancy engine): vocabularies only until P13 uses
# them.
class IntentKind(StrEnum):
    """B.44 intent kind."""

    PROMISE = "promise"
    TARGET = "target"
    CONTROL_OBJECTIVE = "control_objective"
    POLICY_RULE = "policy_rule"


class IntentOrigin(StrEnum):
    """B.45 intent origin."""

    DOCUMENT = "document"
    OWNER_STATED = "owner_stated"


class ImpactClass(StrEnum):
    """B.46 impact class (Reality views)."""

    CONTROL_EXPOSURE = "control_exposure"
    TIME_IMPACT = "time_impact"
    CAPACITY_DRAIN = "capacity_drain"
    WORKAROUND = "workaround"


class Verdict(StrEnum):
    """B.47 verdict (where the fix lies)."""

    CODIFY = "codify"
    CORRECT = "correct"
    REWRITE = "rewrite"
    ASK = "ask"
    AS_DESIGNED = "as_designed"


class DiscrepancyType(StrEnum):
    """B.48 discrepancy type."""

    SKIPPED_STEP = "D1"
    ADDED_STEP = "D2"
    REORDERED = "D3"
    REWORK_LOOP = "D4"
    CONTROL_BYPASSED = "D5"
    OFF_SYSTEM = "D6"
    TAKES_LONGER = "D7"
    WAITING = "D8"
    PARALLEL_ROUTES = "D9"
    BELIEF_GAP = "D10"
    NO_RECORD = "D11"
    DIFFERENT_ROLE = "D12"
    DESIGN_GAP = "D13"
    PROMISE_MISSED = "D14"


class IntentMetric(StrEnum):
    """B.49 intent metric."""

    CYCLE_TIME_MIN = "cycle_time_min"
    STEP_TIME_MIN = "step_time_min"
    WAIT_MIN = "wait_min"
    LEAD_TIME_MIN = "lead_time_min"
    STRAIGHT_THROUGH_PCT = "straight_through_pct"
    RECORDED_PCT = "recorded_pct"
    OTHER = "other"


class FigureLabel(StrEnum):
    """B.50 figure label (Reality views)."""

    MEASURED = "measured"
    STATED = "stated"
    DOCUMENTED = "documented"
    TARGET = "target"
    MIXED = "mixed"


# --- Comparing countries (PRD §3.19; DECISIONS 98) ------------------------------------------------


class ReasonClass(StrEnum):
    """B.51 reason class: why two countries differ (Eric's choice, never the app's)."""

    REQUIRED = "required"
    CHOSEN = "chosen"
    INHERITED = "inherited"
    UNKNOWN = "unknown"


class FindingTopic(StrEnum):
    """B.52 finding topic: which Compass readout page a finding belongs on."""

    DECISION_RIGHT = "decision_right"
    ROLE_PRESENCE = "role_presence"
    ROLE_REASON = "role_reason"
    WAY_OF_WORKING = "way_of_working"


class DifferenceKind(StrEnum):
    """B.53 country difference kind."""

    WHO_DOES = "who_does"
    WHO_DECIDES = "who_decides"
    HOW_DECIDED = "how_decided"
    STEP_KIND = "step_kind"
    WORK_TYPE = "work_type"
    WORK_TIME = "work_time"
    WAIT_TIME = "wait_time"
    DOCUMENTED_VS_DONE = "documented_vs_done"
    ONLY_REFERENCE = "only_reference"
    ONLY_OTHER = "only_other"


class PairStatus(StrEnum):
    """B.54 step pair status: proposed by rule, suggested by Claude, or Eric's decision."""

    PROPOSED = "proposed"
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"
    ONLY_REFERENCE = "only_reference"
    ONLY_OTHER = "only_other"


class DifferenceStatus(StrEnum):
    """B.55 difference status."""

    OPEN = "open"
    KEPT = "kept"
    CLASSED = "classed"
    DISMISSED = "dismissed"


class ReturnKind(StrEnum):
    """B.56 return finding kind (compass-return 1.0)."""

    STEP = "step"
    DISCREPANCY = "discrepancy"
    INTENT = "intent"
    KNOWLEDGE_RISK = "knowledge_risk"
    HYPOTHESIS_VERDICT = "hypothesis_verdict"
    VARIATION = "variation"
