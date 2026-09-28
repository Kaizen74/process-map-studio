"""Map versions repository (PRD §3.5 map_versions): drafts and published versions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.domain.models import VersionView
from app.repositories.tables import (
    AiFlag,
    Base,
    Claim,
    Constraint,
    Edge,
    Element,
    ElementClaim,
    EvidenceLink,
    Image,
    MapVersion,
    MergeProposal,
    Phase,
    Raci,
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


# --- Publishing and reopening (phase P7) -------------------------------------------------------

REOPEN_STATUS = {"confirmed": "confirmed", "edited": "confirmed", "added": "confirmed",
                 "rejected": "rejected"}  # fmt: skip


def rows(session: Session, engagement_id: str) -> list[dict[str, Any]]:
    """Every listed version of an engagement, newest first, with its publishing facts."""
    found = session.scalars(
        select(MapVersion)
        .where(MapVersion.engagement_id == engagement_id, MapVersion.state != "building")
        .order_by(MapVersion.created_at.desc(), MapVersion.id.desc())
    )
    return [_row(r) for r in found]


def _row(row: MapVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "engagement_id": row.engagement_id,
        "label": row.label,
        "state": row.state,
        "created_at": row.created_at,
        "published_at": row.published_at,
        "published_by": row.published_by,
        "parent_version_id": row.parent_version_id,
    }


def row(session: Session, version_id: str) -> dict[str, Any] | None:
    found = session.get(MapVersion, version_id)
    return _row(found) if found else None


def change_log(session: Session, version_id: str) -> list[Any]:
    return session.scalar(select(MapVersion.change_log).where(MapVersion.id == version_id)) or []


def latest_published(session: Session, engagement_id: str) -> dict[str, Any] | None:
    found = session.scalars(
        select(MapVersion)
        .where(MapVersion.engagement_id == engagement_id, MapVersion.state == "published")
        .order_by(MapVersion.published_at.desc(), MapVersion.id.desc())
    ).first()
    return _row(found) if found else None


def published_labels(session: Session, engagement_id: str) -> list[str]:
    return list(
        session.scalars(
            select(MapVersion.label).where(
                MapVersion.engagement_id == engagement_id,
                MapVersion.state.in_(["published", "superseded"]),
            )
        )
    )


def publish(
    session: Session,
    version_id: str,
    *,
    label: str,
    published_at: str,
    published_by: str,
    quality_card: dict[str, Any],
    change_log: list[Any],
) -> None:
    """Make the draft the published version; the earlier published one is superseded."""
    engagement_id = session.scalar(
        select(MapVersion.engagement_id).where(MapVersion.id == version_id)
    )
    session.execute(
        update(MapVersion)
        .where(MapVersion.engagement_id == engagement_id, MapVersion.state == "published")
        .values(state="superseded")
    )
    session.execute(
        update(MapVersion)
        .where(MapVersion.id == version_id)
        .values(
            state="published",
            label=label,
            published_at=published_at,
            published_by=published_by,
            quality_card=quality_card,
            change_log=change_log,
        )
    )


def _copy[T: Base](session: Session, model: type[T], row: T, **changes: Any) -> T:
    """A new row with the same values (new id and created_at) and the given changes."""
    skip = {"id", "created_at"}
    values = {c.key: getattr(row, c.key) for c in model.__table__.columns if c.key not in skip}
    fresh = model(**{**values, **changes})
    session.add(fresh)
    return fresh


def copy_content(session: Session, from_id: str, to_id: str) -> None:
    """Deep copy of a published map into a new draft (PRD §3.5 Reopen): phases, steps with their
    claim links, lines, RACI, evidence links, constraints, AI flags, questions, image rows (the
    files are shared) and sources. Reviewed steps carry over as confirmed; rejected stay rejected.
    """
    phases: dict[str, str] = {}
    for old in session.scalars(select(Phase).where(Phase.version_id == from_id)):
        phases[old.id] = _copy(session, Phase, old, version_id=to_id).id
    session.flush()
    elements: dict[str, str] = {}
    old_elements = list(
        session.scalars(
            select(Element)
            .where(Element.version_id == from_id)
            .order_by(Element.created_at, Element.id)
        )
    )
    for old_el in old_elements:
        fresh = _copy(
            session,
            Element,
            old_el,
            version_id=to_id,
            phase_id=phases.get(old_el.phase_id or ""),
            review_status=REOPEN_STATUS.get(old_el.review_status, old_el.review_status),
        )
        session.flush()
        elements[old_el.id] = fresh.id
    ids = list(elements)
    for link in session.scalars(select(ElementClaim).where(ElementClaim.element_id.in_(ids))):
        _copy(session, ElementClaim, link, element_id=elements[link.element_id])
    for edge in session.scalars(select(Edge).where(Edge.version_id == from_id)):
        _copy(
            session,
            Edge,
            edge,
            version_id=to_id,
            from_element_id=elements[edge.from_element_id],
            to_element_id=elements[edge.to_element_id],
        )
    racis: dict[str, str] = {}
    for entry in session.scalars(select(Raci).where(Raci.element_id.in_(ids))):
        fresh_raci = _copy(session, Raci, entry, element_id=elements[entry.element_id])
        session.flush()
        racis[entry.id] = fresh_raci.id
    for ev in session.scalars(
        select(EvidenceLink).where(
            (EvidenceLink.element_id.in_(ids)) | (EvidenceLink.raci_id.in_(list(racis)))
        )
    ):
        _copy(
            session,
            EvidenceLink,
            ev,
            element_id=elements.get(ev.element_id or ""),
            raci_id=racis.get(ev.raci_id or ""),
        )
    for c in session.scalars(select(Constraint).where(Constraint.element_id.in_(ids))):
        _copy(session, Constraint, c, element_id=elements[c.element_id])
    for flag in session.scalars(select(AiFlag).where(AiFlag.element_id.in_(ids))):
        _copy(session, AiFlag, flag, element_id=elements[flag.element_id])
    for q in session.scalars(
        select(ValidationQuestion).where(ValidationQuestion.version_id == from_id)
    ):
        _copy(
            session,
            ValidationQuestion,
            q,
            version_id=to_id,
            element_id=elements.get(q.element_id or ""),
            phase_id=phases.get(q.phase_id or ""),
        )
    for image in session.scalars(select(Image).where(Image.element_id.in_(ids))):
        _copy(session, Image, image, element_id=elements[image.element_id or ""])
    for source in session.scalars(select(VersionSource).where(VersionSource.version_id == from_id)):
        _copy(session, VersionSource, source, version_id=to_id)
    session.flush()


def create_reopened(
    session: Session, *, engagement_id: str, label: str, parent_id: str
) -> VersionView:
    found = MapVersion(
        engagement_id=engagement_id, label=label, state="draft", parent_version_id=parent_id
    )
    session.add(found)
    session.flush()
    return _view(found)
