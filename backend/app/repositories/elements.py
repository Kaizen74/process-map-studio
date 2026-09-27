"""Map repository (PRD §3.5): phases, elements, their claims, edges, RACI, evidence, constraints,
AI flags, merge proposals, validation questions and the sources a draft was made from.

Everything here belongs to one version; deleting the version (or an element) cascades.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.graph import (
    AiFlagRecord,
    ConstraintRecord,
    EdgeRecord,
    ElementRecord,
    EvidencePassage,
    EvidenceRecord,
    MergeProposalRecord,
    PhaseRecord,
    QuestionRecord,
    RaciRecord,
    Record,
)
from app.repositories.tables import (
    AiFlag,
    Constraint,
    Edge,
    Element,
    ElementClaim,
    EvidenceLink,
    MergeProposal,
    Phase,
    Raci,
    Row,
    Source,
    SourceSegment,
    ValidationQuestion,
    VersionSource,
)


def _add[R: Record](
    session: Session, table: type[Row], records: Sequence[R], **extra: Any
) -> list[R]:
    """Insert records (their `id` is ignored) and return them with their new IDs."""
    rows = [table(**r.model_dump(exclude={"id"}), **extra) for r in records]
    session.add_all(rows)
    session.flush()
    return [type(r).model_validate(row) for r, row in zip(records, rows, strict=True)]


def _for_elements(version_id: str) -> Any:
    return select(Element.id).where(Element.version_id == version_id)


# --- Writing -----------------------------------------------------------------------------------


def add_phases(
    session: Session, version_id: str, phases: Sequence[PhaseRecord]
) -> list[PhaseRecord]:
    return _add(session, Phase, phases, version_id=version_id)


def add_elements(
    session: Session, version_id: str, elements: Sequence[ElementRecord]
) -> list[ElementRecord]:
    return _add(session, Element, elements, version_id=version_id)


def update_element(
    session: Session, element_id: str, fields: dict[str, Any]
) -> ElementRecord | None:
    row = session.get(Element, element_id)
    if row is None:
        return None
    for name, value in fields.items():
        if name not in ElementRecord.model_fields or name == "id":
            raise ValueError(f"not an element field: {name}")
        setattr(row, name, value)
    session.flush()
    return ElementRecord.model_validate(row)


def delete_elements(session: Session, element_ids: Sequence[str]) -> None:
    if element_ids:
        session.execute(delete(Element).where(Element.id.in_(element_ids)))
        session.flush()


def link_claims(session: Session, element_id: str, claim_ids: Sequence[str]) -> None:
    session.add_all(ElementClaim(element_id=element_id, claim_id=c) for c in claim_ids)
    session.flush()


def unlink_claims(session: Session, claim_ids: Sequence[str]) -> None:
    if claim_ids:
        session.execute(delete(ElementClaim).where(ElementClaim.claim_id.in_(claim_ids)))
        session.flush()


def add_edges(session: Session, version_id: str, edges: Sequence[EdgeRecord]) -> list[EdgeRecord]:
    return _add(session, Edge, edges, version_id=version_id)


def add_raci(session: Session, entries: Sequence[RaciRecord]) -> list[RaciRecord]:
    return _add(session, Raci, entries)


def add_evidence(session: Session, links: Sequence[EvidenceRecord]) -> list[EvidenceRecord]:
    return _add(session, EvidenceLink, links)


def add_constraints(
    session: Session, constraints: Sequence[ConstraintRecord]
) -> list[ConstraintRecord]:
    return _add(session, Constraint, constraints)


def add_ai_flags(session: Session, flags: Sequence[AiFlagRecord]) -> list[AiFlagRecord]:
    return _add(session, AiFlag, flags)


def add_merge_proposals(
    session: Session, version_id: str, proposals: Sequence[MergeProposalRecord]
) -> list[MergeProposalRecord]:
    return _add(session, MergeProposal, proposals, version_id=version_id)


def add_questions(
    session: Session, version_id: str, questions: Sequence[QuestionRecord]
) -> list[QuestionRecord]:
    return _add(session, ValidationQuestion, questions, version_id=version_id)


def add_version_sources(session: Session, version_id: str, source_ids: Sequence[str]) -> None:
    session.add_all(VersionSource(version_id=version_id, source_id=s) for s in source_ids)
    session.flush()


# --- Reading -----------------------------------------------------------------------------------


def phases(session: Session, version_id: str) -> list[PhaseRecord]:
    rows = session.scalars(
        select(Phase).where(Phase.version_id == version_id).order_by(Phase.sort_order, Phase.id)
    )
    return [PhaseRecord.model_validate(r) for r in rows]


def elements(session: Session, version_id: str) -> list[ElementRecord]:
    """In the order they were created (the pipeline creates them in process order)."""
    rows = session.scalars(
        select(Element)
        .where(Element.version_id == version_id)
        .order_by(Element.created_at, Element.id)
    )
    return [ElementRecord.model_validate(r) for r in rows]


def element_claims(session: Session, version_id: str) -> dict[str, list[str]]:
    """Element ID → the IDs of the verified claims it is built from."""
    rows = session.execute(
        select(ElementClaim.element_id, ElementClaim.claim_id)
        .where(ElementClaim.element_id.in_(_for_elements(version_id)))
        .order_by(ElementClaim.created_at, ElementClaim.id)
    )
    out: dict[str, list[str]] = {}
    for element_id, claim_id in rows:
        out.setdefault(element_id, []).append(claim_id)
    return out


def edges(session: Session, version_id: str) -> list[EdgeRecord]:
    rows = session.scalars(
        select(Edge).where(Edge.version_id == version_id).order_by(Edge.created_at, Edge.id)
    )
    return [EdgeRecord.model_validate(r) for r in rows]


def raci(session: Session, version_id: str) -> list[RaciRecord]:
    rows = session.scalars(
        select(Raci)
        .where(Raci.element_id.in_(_for_elements(version_id)))
        .order_by(Raci.created_at, Raci.id)
    )
    return [RaciRecord.model_validate(r) for r in rows]


def constraints(session: Session, version_id: str) -> list[ConstraintRecord]:
    rows = session.scalars(
        select(Constraint)
        .where(Constraint.element_id.in_(_for_elements(version_id)))
        .order_by(Constraint.created_at, Constraint.id)
    )
    return [ConstraintRecord.model_validate(r) for r in rows]


def ai_flags(session: Session, version_id: str) -> list[AiFlagRecord]:
    rows = session.scalars(
        select(AiFlag)
        .where(AiFlag.element_id.in_(_for_elements(version_id)))
        .order_by(AiFlag.created_at, AiFlag.id)
    )
    return [AiFlagRecord.model_validate(r) for r in rows]


def merge_proposals(session: Session, version_id: str) -> list[MergeProposalRecord]:
    rows = session.scalars(
        select(MergeProposal)
        .where(MergeProposal.version_id == version_id)
        .order_by(MergeProposal.created_at, MergeProposal.id)
    )
    return [MergeProposalRecord.model_validate(r) for r in rows]


def questions(session: Session, version_id: str) -> list[QuestionRecord]:
    rows = session.scalars(
        select(ValidationQuestion)
        .where(ValidationQuestion.version_id == version_id)
        .order_by(ValidationQuestion.created_at, ValidationQuestion.id)
    )
    return [QuestionRecord.model_validate(r) for r in rows]


def version_source_ids(session: Session, version_id: str) -> list[str]:
    rows = session.scalars(
        select(VersionSource.source_id)
        .where(VersionSource.version_id == version_id)
        .order_by(VersionSource.created_at, VersionSource.id)
    )
    return list(rows)


def evidence(session: Session, version_id: str) -> list[EvidencePassage]:
    """Evidence links of a version's elements and RACI entries, with their passages."""
    raci_ids = select(Raci.id).where(Raci.element_id.in_(_for_elements(version_id)))
    rows = session.execute(
        select(EvidenceLink, SourceSegment, Source)
        .join(SourceSegment, SourceSegment.id == EvidenceLink.segment_id)
        .join(Source, Source.id == SourceSegment.source_id)
        .where(
            EvidenceLink.element_id.in_(_for_elements(version_id))
            | EvidenceLink.raci_id.in_(raci_ids)
        )
        .order_by(EvidenceLink.created_at, EvidenceLink.id)
    )
    return [
        EvidencePassage(
            evidence=EvidenceRecord.model_validate(link),
            source_id=source.id,
            source_name=source.filename,
            source_format=source.format,
            seq=segment.seq,
            page=segment.page,
            section=segment.section,
            text=segment.text,
            start_ms=segment.start_ms,
        )
        for link, segment, source in rows
    ]


def step_counts(session: Session, version_id: str) -> tuple[int, int]:
    """(steps, steps needing a check): activities, decisions and approvals of a version."""
    rows = session.execute(
        select(Element.needs_check).where(
            Element.version_id == version_id,
            Element.kind.in_(("activity", "decision", "approval")),
        )
    ).all()
    return len(rows), sum(1 for (needs_check,) in rows if needs_check)


def open_question_count(session: Session, version_id: str) -> int:
    return len(
        session.scalars(
            select(ValidationQuestion.id).where(
                ValidationQuestion.version_id == version_id, ValidationQuestion.status == "open"
            )
        ).all()
    )
