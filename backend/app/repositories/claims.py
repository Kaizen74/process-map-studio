"""Claims and unknowns repository (PRD §3.5 claims, unknowns): what each source says, checked."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import ClaimRecord, UnknownRecord
from app.repositories.tables import Claim, Unknown


def add_claims(session: Session, version_id: str, claims: list[ClaimRecord]) -> None:
    for claim in claims:
        session.add(Claim(version_id=version_id, **claim.model_dump()))
    session.flush()


def add_unknowns(session: Session, version_id: str, unknowns: list[UnknownRecord]) -> None:
    for unknown in unknowns:
        session.add(Unknown(version_id=version_id, **unknown.model_dump()))
    session.flush()


def list_claims(session: Session, version_id: str, status: str | None = None) -> list[ClaimRecord]:
    query = select(Claim).where(Claim.version_id == version_id)
    if status is not None:
        query = query.where(Claim.verification_status == status)
    rows = session.scalars(query.order_by(Claim.created_at, Claim.id))
    return [
        ClaimRecord(
            source_id=row.source_id,
            stage=row.stage,
            claim_type=row.claim_type,
            payload=dict(row.payload),
            segment_ids=list(row.segment_ids),
            quote=row.quote,
            provenance=row.provenance,
            basis=row.basis,
            verification_status=row.verification_status,
            rejection_reason=row.rejection_reason,
            rejection_guardrail=row.rejection_guardrail,
        )
        for row in rows
    ]


def list_unknowns(session: Session, version_id: str) -> list[UnknownRecord]:
    rows = session.scalars(
        select(Unknown).where(Unknown.version_id == version_id).order_by(Unknown.created_at)
    )
    return [
        UnknownRecord(source_id=r.source_id, question=r.question, segment_ids=list(r.segment_ids))
        for r in rows
    ]


def counts(session: Session, version_id: str) -> dict[str, int]:
    """Claims per verification status in a version, e.g. {"verified": 12, "rejected": 3}."""
    rows = session.execute(
        select(Claim.verification_status, func.count())
        .where(Claim.version_id == version_id)
        .group_by(Claim.verification_status)
    )
    return {status: count for status, count in rows}
