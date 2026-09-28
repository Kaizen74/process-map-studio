"""Map versions repository (PRD §3.5 map_versions): drafts and published versions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.domain.models import VersionView
from app.repositories.tables import (
    Claim,
    Edge,
    Element,
    ElementClaim,
    MapVersion,
    MergeProposal,
    Phase,
    Unknown,
    ValidationQuestion,
    VersionSource,
)

# Everything a draft holds, moved as a whole when a refresh is folded into the draft.
CONTENT = (Claim, Unknown, Phase, Element, Edge, MergeProposal, ValidationQuestion, VersionSource)


def _view(row: MapVersion) -> VersionView:
    return VersionView(
        id=row.id,
        engagement_id=row.engagement_id,
        label=row.label,
        state=row.state,
        created_at=row.created_at,
    )


def create(session: Session, *, engagement_id: str, label: str, state: str) -> VersionView:
    row = MapVersion(engagement_id=engagement_id, label=label, state=state)
    session.add(row)
    session.flush()
    return _view(row)


def get(session: Session, version_id: str) -> VersionView | None:
    row = session.get(MapVersion, version_id)
    return _view(row) if row else None


def current_draft(session: Session, engagement_id: str) -> VersionView | None:
    """The engagement's one draft, if any (PRD §3.5: at most one draft at a time)."""
    row = session.scalars(
        select(MapVersion)
        .where(MapVersion.engagement_id == engagement_id)
        .where(MapVersion.state == "draft")
        .order_by(MapVersion.created_at.desc(), MapVersion.id)
    ).first()
    return _view(row) if row else None


def drafts(session: Session, engagement_id: str) -> list[VersionView]:
    """The engagement's draft versions, newest first (two exist only while a new draft is made)."""
    rows = session.scalars(
        select(MapVersion)
        .where(MapVersion.engagement_id == engagement_id)
        .where(MapVersion.state == "draft")
        .order_by(MapVersion.created_at.desc(), MapVersion.id)
    )
    return [_view(row) for row in rows]


def delete(session: Session, version_id: str) -> None:
    row = session.get(MapVersion, version_id)
    if row is not None:
        session.delete(row)
        session.flush()


def element_count(session: Session, version_id: str) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(Element).where(Element.version_id == version_id)
        )
        or 0
    )


def set_lint_report(session: Session, version_id: str, report: dict[str, Any]) -> None:
    row = session.get(MapVersion, version_id)
    if row is not None:
        row.lint_report = report
        session.flush()


def lint_report(session: Session, version_id: str) -> dict[str, Any] | None:
    row = session.get(MapVersion, version_id)
    return dict(row.lint_report) if row is not None and row.lint_report is not None else None


def reviewed_count(session: Session, version_id: str) -> int:
    """Elements Eric has confirmed, edited or added: locked against any AI re-run."""
    return (
        session.scalar(
            select(func.count())
            .select_from(Element)
            .where(
                Element.version_id == version_id,
                Element.review_status.in_(("confirmed", "edited", "added")),
            )
        )
        or 0
    )


def set_label(session: Session, version_id: str, label: str) -> None:
    row = session.get(MapVersion, version_id)
    if row is not None:
        row.label = label
        session.flush()


def building(session: Session, engagement_id: str) -> list[VersionView]:
    """Versions a refresh is still building (state `building`)."""
    rows = session.scalars(
        select(MapVersion)
        .where(MapVersion.engagement_id == engagement_id)
        .where(MapVersion.state == "building")
    )
    return [_view(r) for r in rows]


def move_content(session: Session, from_id: str, to_id: str) -> None:
    """Hand every claim, step, line, phase, question, merge proposal and source link of one
    version to another."""
    for table in CONTENT:
        session.execute(update(table).where(table.version_id == from_id).values(version_id=to_id))
    session.flush()


def clear_for_refresh(session: Session, version_id: str, keep: set[str]) -> None:
    """Remove what a refresh replaces from a draft: questions, unknowns, merge proposals, the
    source links, claims no kept step is built from, and phases no kept step uses. The steps and
    lines themselves are handled by the caller."""
    for table in (ValidationQuestion, Unknown, MergeProposal, VersionSource):
        session.execute(sql_delete(table).where(table.version_id == version_id))
    kept_claims = select(ElementClaim.claim_id).where(ElementClaim.element_id.in_(keep))
    session.execute(
        sql_delete(Claim).where(Claim.version_id == version_id).where(Claim.id.not_in(kept_claims))
    )
    used = select(Element.phase_id).where(Element.id.in_(keep)).where(Element.phase_id.is_not(None))
    session.execute(
        sql_delete(Phase).where(Phase.version_id == version_id).where(Phase.id.not_in(used))
    )
    session.flush()


def delete_unused_phases(session: Session, version_id: str) -> None:
    used = select(Element.phase_id).where(Element.version_id == version_id)
    session.execute(
        sql_delete(Phase)
        .where(Phase.version_id == version_id)
        .where(Phase.id.not_in(used.where(Element.phase_id.is_not(None))))
    )
    session.flush()


def publication(session: Session, version_id: str) -> tuple[str, str]:
    """(published_at, published_by) of a version; empty strings while it is a draft."""
    row = session.get(MapVersion, version_id)
    if row is None:
        return "", ""
    return row.published_at or "", row.published_by or ""


def set_quality_card(session: Session, version_id: str, card: dict[str, Any]) -> None:
    session.execute(update(MapVersion).where(MapVersion.id == version_id).values(quality_card=card))


def quality_card(session: Session, version_id: str) -> dict[str, Any] | None:
    return session.scalar(select(MapVersion.quality_card).where(MapVersion.id == version_id))
