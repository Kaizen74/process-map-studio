"""Database tables (PRD §3.5). Only repositories import this module.

Every table has `id` (UUID string) and `created_at` (UTC ISO 8601). Controlled-vocabulary columns
hold Appendix B values as plain strings (validated with `app.domain.enums` by the actions);
there are no CHECK constraints because SQLite cannot change them additively (constraint 16).
Deleting an engagement cascades to every row that belongs to it.

Migration 0001 (backend/migrations/versions/0001_initial.py) creates exactly these tables; a test
keeps the two in step.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, false
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ID = String(36)
CASCADE = "CASCADE"


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    # Microseconds keep "newest first" ordering reliable when several changes happen in a second.
    return datetime.now(UTC).isoformat(timespec="microseconds")


class Base(DeclarativeBase):
    pass


class Row(Base):
    __abstract__ = True
    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    created_at: Mapped[str] = mapped_column(String(32), default=now_iso)


def fk(target: str, *, nullable: bool = False) -> Mapped[Any]:
    return mapped_column(ID, ForeignKey(target, ondelete=CASCADE), nullable=nullable, index=True)


def opt_fk(target: str) -> Mapped[Any]:
    return mapped_column(ID, ForeignKey(target, ondelete="SET NULL"), nullable=True, index=True)


# --- Engagement, sources, roles -------------------------------------------------------------


class Engagement(Row):
    __tablename__ = "engagements"
    name: Mapped[str] = mapped_column(Text)
    process_name: Mapped[str] = mapped_column(Text, default="")
    trigger: Mapped[str] = mapped_column(Text, default="")
    end_point: Mapped[str] = mapped_column(Text, default="")
    in_scope_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    out_of_scope: Mapped[str] = mapped_column(Text, default="")
    process_kpi: Mapped[str] = mapped_column(Text, default="")
    industry: Mapped[str] = mapped_column(Text, default="")
    adjacent_industries: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="active")
    updated_at: Mapped[str] = mapped_column(String(32), default=now_iso)
    # PRD v1.10 (0009): codebook tier 2 conventions (granularity, label style, phase naming).
    conventions: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class Source(Row):
    __tablename__ = "sources"
    engagement_id: Mapped[str] = fk("engagements.id")
    kind: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(Text)
    stored_path: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(Text, default="")
    format: Mapped[str] = mapped_column(String(8))
    version_date: Mapped[str] = mapped_column(String(32), default="")
    owner: Mapped[str] = mapped_column(Text, default="")
    controlled_copy: Mapped[bool] = mapped_column(Boolean, default=False)
    text_status: Mapped[str] = mapped_column(String(16), default="pending")
    error: Mapped[str] = mapped_column(Text, default="")
    # PDF pages with almost no text, to be read by OCR (S0) from phase P3.
    ocr_pages: Mapped[list[int]] = mapped_column(JSON, default=list)


class SourceSegment(Row):
    __tablename__ = "source_segments"
    source_id: Mapped[str] = fk("sources.id")
    seq: Mapped[int] = mapped_column(Integer)
    speaker_label: Mapped[str] = mapped_column(Text, default="")
    speaker_role_id: Mapped[str | None] = opt_fk("roles.id")
    start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text)
    corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    instruction_like: Mapped[bool] = mapped_column(Boolean, default=False)
    # Added in migration 0002: the label was mapped to "Interviewer" (not a role).
    is_interviewer: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # PRD v1.10 (0009): the guide question an interviewer turn matched, its answer block, markers.
    question_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    answer_block_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    marker_tags: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)


class RedactionTerm(Row):
    __tablename__ = "redaction_terms"
    engagement_id: Mapped[str] = fk("engagements.id")
    term: Mapped[str] = mapped_column(Text)
    replacement: Mapped[str] = mapped_column(Text, default="[name]")
    origin: Mapped[str] = mapped_column(String(32))


class Role(Row):
    __tablename__ = "roles"
    engagement_id: Mapped[str] = fk("engagements.id")
    name: Mapped[str] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    lane_order: Mapped[int | None] = mapped_column(Integer, nullable=True)


# --- Versions and the map ------------------------------------------------------------------


class MapVersion(Row):
    __tablename__ = "map_versions"
    engagement_id: Mapped[str] = fk("engagements.id")
    label: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(16))
    parent_version_id: Mapped[str | None] = opt_fk("map_versions.id")
    published_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    published_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_log: Mapped[list[Any]] = mapped_column(JSON, default=list)
    lint_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    quality_card: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    codebook_version: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 0009
    run_record: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # 0010
    system_traces: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)  # 0013


class Claim(Row):
    __tablename__ = "claims"
    version_id: Mapped[str] = fk("map_versions.id")
    source_id: Mapped[str] = fk("sources.id")
    stage: Mapped[str] = mapped_column(String(16))
    claim_type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    segment_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    quote: Mapped[str] = mapped_column(Text, default="")
    provenance: Mapped[str] = mapped_column(String(1))
    basis: Mapped[str] = mapped_column(Text, default="")
    verification_status: Mapped[str] = mapped_column(String(16), default="pending")
    rejection_reason: Mapped[str] = mapped_column(Text, default="")
    rejection_guardrail: Mapped[str] = mapped_column(String(8), default="")
    verifier_verdict: Mapped[str] = mapped_column(String(16), default="not_run")
    verifier_reason: Mapped[str] = mapped_column(Text, default="")
    account_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # B.28 (0009)


class VersionSource(Row):
    """Added in migration 0004: the sources a draft was made from (for silent stances)."""

    __tablename__ = "version_sources"
    version_id: Mapped[str] = fk("map_versions.id")
    source_id: Mapped[str] = fk("sources.id")


class Unknown(Row):
    __tablename__ = "unknowns"
    version_id: Mapped[str] = fk("map_versions.id")
    source_id: Mapped[str] = fk("sources.id")
    question: Mapped[str] = mapped_column(Text)
    segment_ids: Mapped[list[str]] = mapped_column(JSON, default=list)


class Phase(Row):
    __tablename__ = "phases"
    version_id: Mapped[str] = fk("map_versions.id")
    name: Mapped[str] = mapped_column(Text)
    time_window: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Element(Row):
    __tablename__ = "elements"
    version_id: Mapped[str] = fk("map_versions.id")
    stable_key: Mapped[str] = mapped_column(Text, index=True)
    kind: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(Text)
    lane_role_id: Mapped[str | None] = opt_fk("roles.id")
    phase_id: Mapped[str | None] = opt_fk("phases.id")
    work_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    wait_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_text: Mapped[str] = mapped_column(Text, default="")
    complexity: Mapped[str | None] = mapped_column(String(1), nullable=True)
    kpi: Mapped[str] = mapped_column(Text, default="")
    decision_mechanism: Mapped[str] = mapped_column(String(16), default="none")
    decider_role_id: Mapped[str | None] = opt_fk("roles.id")
    rule_or_threshold: Mapped[str] = mapped_column(Text, default="")
    escalation: Mapped[str] = mapped_column(Text, default="")
    handoff_in: Mapped[str] = mapped_column(Text, default="")
    handoff_out: Mapped[str] = mapped_column(Text, default="")
    provenance: Mapped[str] = mapped_column(String(1))
    r_reference: Mapped[str] = mapped_column(Text, default="")
    source_state: Mapped[str] = mapped_column(String(24), default="not_assessed")
    divergence_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    k_risk: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_breakdown: Mapped[list[Any]] = mapped_column(JSON, default=list)
    needs_check: Mapped[bool] = mapped_column(Boolean, default=False)
    review_status: Mapped[str] = mapped_column(String(16), default="draft")
    # PRD v1.10 (0009): work type, views, variants and landscape/practice levels (§3.12).
    work_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    constraint_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    work_type_basis: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    sme_work_type_signifier: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_type_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    practice_described: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    view_membership: Mapped[str | None] = mapped_column(String(16), nullable=True)
    variants: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    parent_element_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    # PRD v1.11 (0012): step disposition (B.41), risk flag and Eric's value overrides (§3.14-3.15).
    disposition: Mapped[str | None] = mapped_column(String(16), nullable=True)
    disposition_suggested: Mapped[str | None] = mapped_column(String(16), nullable=True)
    disposition_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_flag: Mapped[str | None] = mapped_column(String(16), nullable=True)
    time_override_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_override_month: Mapped[float | None] = mapped_column(Float, nullable=True)
    # R9 (0014): Eric's notes on his disposition and on his value overrides.
    disposition_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_override_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ElementClaim(Row):
    __tablename__ = "element_claims"
    element_id: Mapped[str] = fk("elements.id")
    claim_id: Mapped[str] = fk("claims.id")


class Raci(Row):
    __tablename__ = "raci"
    element_id: Mapped[str] = fk("elements.id")
    role_id: Mapped[str] = fk("roles.id")
    letter: Mapped[str] = mapped_column(String(1))
    contested: Mapped[bool] = mapped_column(Boolean, default=False)
    provenance: Mapped[str] = mapped_column(String(1), default="O")


class Edge(Row):
    __tablename__ = "edges"
    version_id: Mapped[str] = fk("map_versions.id")
    from_element_id: Mapped[str] = fk("elements.id")
    to_element_id: Mapped[str] = fk("elements.id")
    kind: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(Text, default="")
    provenance: Mapped[str] = mapped_column(String(1), default="O")
    # PRD v1.10 (0009): why the order is known, typical responses, views, what passes across.
    sequence_basis: Mapped[str | None] = mapped_column(String(16), nullable=True)
    typical: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    view_membership: Mapped[str | None] = mapped_column(String(16), nullable=True)
    information_payload: Mapped[str | None] = mapped_column(Text, nullable=True)


class EvidenceLink(Row):
    __tablename__ = "evidence_links"
    element_id: Mapped[str | None] = fk("elements.id", nullable=True)
    raci_id: Mapped[str | None] = fk("raci.id", nullable=True)
    segment_id: Mapped[str] = fk("source_segments.id")
    source_kind: Mapped[str] = mapped_column(String(32))
    stance: Mapped[str] = mapped_column(String(16))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Added in migration 0004: the cited words (for the highlight) and the divergence detail.
    quote: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")


class Constraint(Row):
    __tablename__ = "constraints"
    element_id: Mapped[str] = fk("elements.id")
    text: Mapped[str] = mapped_column(Text)
    provenance: Mapped[str] = mapped_column(String(1))
    cause_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_key: Mapped[bool] = mapped_column(Boolean, default=False)


class AiFlag(Row):
    __tablename__ = "ai_flags"
    element_id: Mapped[str] = fk("elements.id")
    component: Mapped[str] = mapped_column(String(32))
    input: Mapped[str] = mapped_column(Text, default="")
    output: Mapped[str] = mapped_column(Text, default="")
    handoff: Mapped[str] = mapped_column(Text, default="")
    basis: Mapped[str] = mapped_column(String(40))


class MergeProposal(Row):
    __tablename__ = "merge_proposals"
    version_id: Mapped[str] = fk("map_versions.id")
    claim_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    proposed_label: Mapped[str] = mapped_column(Text)
    similarity: Mapped[float] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String(16), default="pending")
    decided_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Added in migration 0005: the steps behind the proposal, as S2 drafted them.
    claim_groups: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class ValidationQuestion(Row):
    __tablename__ = "validation_questions"
    version_id: Mapped[str] = fk("map_versions.id")
    element_id: Mapped[str | None] = fk("elements.id", nullable=True)
    phase_id: Mapped[str | None] = opt_fk("phases.id")
    question: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String(24))
    origin_ref: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="open")


class Image(Row):
    __tablename__ = "images"
    # Suggested images (extracted from PDFs) exist before any element does: element_id optional.
    element_id: Mapped[str | None] = fk("elements.id", nullable=True)
    stored_path: Mapped[str] = mapped_column(Text)
    caption: Mapped[str] = mapped_column(Text, default="")
    image_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    origin: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="suggested")
    redaction_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    source_id: Mapped[str | None] = fk("sources.id", nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CauseLibraryEntry(Row):
    __tablename__ = "cause_library"
    engagement_id: Mapped[str] = fk("engagements.id")
    element_stable_key: Mapped[str] = mapped_column(Text)
    divergence_type: Mapped[str] = mapped_column(String(16))
    pattern: Mapped[str] = mapped_column(Text)
    inferred_cause: Mapped[str] = mapped_column(Text)
    cause_type: Mapped[str] = mapped_column(String(32))
    provenance: Mapped[str] = mapped_column(String(1))
    validation_result: Mapped[str] = mapped_column(String(16), default="pending")


class AuditRow(Row):
    __tablename__ = "audit_log"
    version_id: Mapped[str | None] = fk("map_versions.id", nullable=True)
    # Engagement-level and app-level actions (scope edits, model changes) have no version.
    engagement_id: Mapped[str | None] = fk("engagements.id", nullable=True)
    actor: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(Text, default="")
    before: Mapped[Any] = mapped_column(JSON, nullable=True)
    after: Mapped[Any] = mapped_column(JSON, nullable=True)


class Job(Row):
    __tablename__ = "jobs"
    engagement_id: Mapped[str | None] = fk("engagements.id", nullable=True)
    type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stage: Mapped[str] = mapped_column(Text, default="")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    # Added in migration 0002: what the job works on (for "read_source", the source ID).
    target_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    # Added in migration 0003: a draft job's stages (name, status, start and finish times).
    stages: Mapped[list[Any]] = mapped_column(JSON, default=list)


class AiCall(Row):
    __tablename__ = "ai_calls"
    job_id: Mapped[str | None] = opt_fk("jobs.id")
    stage_id: Mapped[str] = mapped_column(String(32))
    prompt_version: Mapped[str] = mapped_column(String(32), default="")
    model: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16))
    input_hash: Mapped[str] = mapped_column(String(64), default="")
    web_searches: Mapped[int] = mapped_column(Integer, default=0)


# --- Gap analysis (PRD §3.11) --------------------------------------------------------------


class GapAnalysis(Row):
    __tablename__ = "gap_analyses"
    version_id: Mapped[str] = fk("map_versions.id")
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    brief: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    brief_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    brief_scan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    settings: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str] = mapped_column(Text, default="")
    search_count: Mapped[int] = mapped_column(Integer, default=0)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    finalised_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)  # about the run (0007)


class GapFinding(Row):
    __tablename__ = "gap_findings"
    analysis_id: Mapped[str] = fk("gap_analyses.id")
    section: Mapped[str] = mapped_column(String(16))
    finding_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    element_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence: Mapped[Any] = mapped_column(JSON, nullable=True)
    basis: Mapped[str] = mapped_column(Text, default="")
    provenance: Mapped[str] = mapped_column(String(1))
    severity: Mapped[str | None] = mapped_column(String(8), nullable=True)
    evidence_strength: Mapped[str] = mapped_column(String(8), default="strong")
    comparison: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(16), default="pending")
    rejection_guardrail: Mapped[str] = mapped_column(String(8), default="")
    rejection_reason: Mapped[str] = mapped_column(Text, default="")
    verifier_verdict: Mapped[str] = mapped_column(String(16), default="not_run")
    disposition: Mapped[str] = mapped_column(String(16), default="open")
    disposition_note: Mapped[str] = mapped_column(Text, default="")
    created_item_ref: Mapped[str] = mapped_column(Text, default="")
    gap_class: Mapped[str | None] = mapped_column(String(24), nullable=True)  # B.32 (0009)
    question: Mapped[str] = mapped_column(Text, default="")  # a cause not explained (0006)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)  # flags on the finding (0007)
    stated_reason: Mapped[str] = mapped_column(Text, default="")  # the SME's own words (0011)
    cause_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # B.9 (0011)


class ExternalSource(Row):
    __tablename__ = "external_sources"
    analysis_id: Mapped[str] = fk("gap_analyses.id")
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(Text, default="")
    page_age: Mapped[str] = mapped_column(Text, default="")
    tier: Mapped[str] = mapped_column(String(24), default="other")
    returned_in_results: Mapped[bool] = mapped_column(Boolean, default=False)


class ExternalCitation(Row):
    __tablename__ = "external_citations"
    analysis_id: Mapped[str] = fk("gap_analyses.id")
    source_id: Mapped[str] = fk("external_sources.id")
    citation_ref: Mapped[str] = mapped_column(String(16))
    cited_text: Mapped[str] = mapped_column(Text)


class LeadershipDecision(Row):
    """A "Decision needed" line for one systemic cause type of a version (0008)."""

    __tablename__ = "leadership_decisions"
    version_id: Mapped[str] = fk("map_versions.id")
    cause_type: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text, default="")


# --- Sensemaking (PRD v1.10 §3.12; migration 0009). Filled by phases P4b and P4c. ----------


class Fragment(Row):
    __tablename__ = "fragments"
    version_id: Mapped[str] = fk("map_versions.id")
    source_id: Mapped[str | None] = opt_fk("sources.id")
    segment_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    label: Mapped[str] = mapped_column(Text)
    fragment_type: Mapped[str] = mapped_column(String(16))  # B.31
    sme_signifiers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    element_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    single_account: Mapped[bool] = mapped_column(Boolean, default=False)
    provenance: Mapped[str] = mapped_column(String(1), default="O")


class KnowledgePoint(Row):
    __tablename__ = "knowledge_points"
    element_id: Mapped[str] = fk("elements.id")
    kdp_type: Mapped[str] = mapped_column(String(24))
    ashen: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # B.33
    knowledge_risk: Mapped[str] = mapped_column(String(8), default="low")
    basis: Mapped[str] = mapped_column(Text, default="")
    cadence: Mapped[str | None] = mapped_column(String(16), nullable=True)  # B.37
    information_received: Mapped[list[Any]] = mapped_column(JSON, default=list)
    information_attended: Mapped[list[Any]] = mapped_column(JSON, default=list)
    information_wanted: Mapped[list[Any]] = mapped_column(JSON, default=list)
    communicated_via: Mapped[list[Any]] = mapped_column(JSON, default=list)


class GlossaryTerm(Row):
    __tablename__ = "glossary_terms"
    engagement_id: Mapped[str] = fk("engagements.id")
    term: Mapped[str] = mapped_column(Text)
    plain_meaning: Mapped[str] = mapped_column(Text, default="")
    standard_label: Mapped[str] = mapped_column(Text, default="")
    segment_ids: Mapped[list[str]] = mapped_column(JSON, default=list)


class EmergentTheme(Row):
    __tablename__ = "emergent_themes"
    engagement_id: Mapped[str] = fk("engagements.id")
    version_id: Mapped[str | None] = opt_fk("map_versions.id")
    theme: Mapped[str] = mapped_column(Text)
    fragment_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    basis: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    note: Mapped[str] = mapped_column(Text, default="")


class IntervieweeProfile(Row):
    """Roles only, never personal names (constraint 10)."""

    __tablename__ = "interviewee_profiles"
    engagement_id: Mapped[str] = fk("engagements.id")
    role_id: Mapped[str | None] = opt_fk("roles.id")
    stakeholder_group: Mapped[str] = mapped_column(Text, default="")
    interview_type: Mapped[str] = mapped_column(String(16))  # B.38
    referred_by_role: Mapped[str] = mapped_column(Text, default="")
    previous_profile_session: Mapped[str | None] = mapped_column(ID, nullable=True)


class CapabilityNote(Row):
    __tablename__ = "capability_notes"
    version_id: Mapped[str] = fk("map_versions.id")
    kind: Mapped[str] = mapped_column(String(16))  # strength / weakness
    dimension: Mapped[str] = mapped_column(String(24))  # B.36
    text: Mapped[str] = mapped_column(Text)
    element_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    segment_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    provenance: Mapped[str] = mapped_column(String(1), default="O")
    cause_type: Mapped[str | None] = mapped_column(String(32), nullable=True)


class InterviewGuide(Row):
    __tablename__ = "interview_guides"
    engagement_id: Mapped[str] = fk("engagements.id")
    profile_id: Mapped[str | None] = opt_fk("interviewee_profiles.id")
    interview_type: Mapped[str] = mapped_column(String(16))  # B.38
    version: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    edited: Mapped[bool] = mapped_column(Boolean, default=False)


class CoverageReport(Row):
    __tablename__ = "coverage_reports"
    version_id: Mapped[str] = fk("map_versions.id")
    source_id: Mapped[str | None] = opt_fk("sources.id")
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    follow_up_questions: Mapped[list[Any]] = mapped_column(JSON, default=list)


# --- System records, value calculator (PRD v1.11 §3.13-3.14; migration 0012; filled in P10b) ----


class EventLog(Row):
    __tablename__ = "event_logs"
    engagement_id: Mapped[str] = fk("engagements.id")
    name: Mapped[str] = mapped_column(Text)
    system: Mapped[str] = mapped_column(Text, default="")
    file_ref: Mapped[str] = mapped_column(Text, default="")
    timezone: Mapped[str] = mapped_column(String(64))
    window_start: Mapped[str | None] = mapped_column(String(32), nullable=True)
    window_end: Mapped[str | None] = mapped_column(String(32), nullable=True)
    column_map: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    approved_by_role: Mapped[str] = mapped_column(Text, default="")
    approved_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="uploaded")


class Event(Row):
    """One recorded event. No resource or user column (constraint 24)."""

    __tablename__ = "events"
    log_id: Mapped[str] = fk("event_logs.id")
    case_id: Mapped[str] = mapped_column(Text)
    activity: Mapped[str] = mapped_column(Text)
    ts_start: Mapped[str] = mapped_column(String(32))
    ts_end: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role_id: Mapped[str | None] = opt_fk("roles.id")
    case_attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class CaseKeyMap(Row):
    __tablename__ = "case_key_maps"
    engagement_id: Mapped[str] = fk("engagements.id")
    from_log_id: Mapped[str] = fk("event_logs.id")
    to_log_id: Mapped[str] = fk("event_logs.id")
    from_case_id: Mapped[str] = mapped_column(Text)
    to_case_id: Mapped[str] = mapped_column(Text)


class ActivityAlignment(Row):
    __tablename__ = "activity_alignment"
    log_id: Mapped[str] = fk("event_logs.id")
    activity: Mapped[str] = mapped_column(Text)
    element_id: Mapped[str | None] = opt_fk("elements.id")
    status: Mapped[str] = mapped_column(String(24), default="proposed")  # B.43
    reason: Mapped[str] = mapped_column(Text, default="")
    confirmed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)


class MiningMetric(Row):
    __tablename__ = "mining_metrics"
    log_id: Mapped[str] = fk("event_logs.id")
    scope: Mapped[str] = mapped_column(String(16))  # activity/transition/case/variant/role
    key: Mapped[str] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    case_count: Mapped[int] = mapped_column(Integer)


class RoleCost(Row):
    __tablename__ = "role_costs"
    engagement_id: Mapped[str] = fk("engagements.id")
    role_id: Mapped[str] = fk("roles.id")
    hourly_cost: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    note: Mapped[str] = mapped_column(Text, default="")


class ValueAssumption(Row):
    __tablename__ = "value_assumptions"
    engagement_id: Mapped[str] = fk("engagements.id")
    disposition: Mapped[str] = mapped_column(String(16))  # B.41
    reduction_pct: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(Text, default="")
