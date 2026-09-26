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


class GapMode(StrEnum):
    """B.21 gap analysis mode."""

    INTERNAL = "internal"
    EXTERNAL = "external"


class InternalFindingType(StrEnum):
    """B.22 internal finding type."""

    DEAD_CONTROL_CANDIDATE = "dead_control_candidate"
    UNDOCUMENTED_WORK = "undocumented_work"
    OWNERSHIP_MISMATCH = "ownership_mismatch"
    THRESHOLD_GAP = "threshold_gap"
    SEQUENCE_GAP = "sequence_gap"
    TRIGGER_GAP = "trigger_gap"
    EXCEPTION_GAP = "exception_gap"
    STALE_DOCUMENTATION = "stale_documentation"
    DOCUMENTATION_UPDATE = "documentation_update"


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
