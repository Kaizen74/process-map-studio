"""Engagement aggregate repository: engagements, their roles and their confidential terms.

The only database access for these tables (PRD §3.2). Returns domain models, never ORM rows.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import ElementKind, ReviewStatus
from app.domain.models import (
    EngagementSummary,
    EngagementView,
    MappingConventions,
    ReviewProgress,
    RoleView,
    VersionLabel,
)
from app.repositories.tables import (
    Element,
    Engagement,
    MapVersion,
    RedactionTerm,
    Role,
    Source,
    now_iso,
)

STEPS = (ElementKind.ACTIVITY.value, ElementKind.DECISION.value, ElementKind.APPROVAL.value)
CONFIDENTIAL_ORIGIN = "confidential_term"

SCOPE_COLUMNS = (
    "name",
    "process_name",
    "trigger",
    "end_point",
    "in_scope_roles",
    "out_of_scope",
    "process_kpi",
    "industry",
    "adjacent_industries",
    "conventions",
)


def _confidential_terms(session: Session, engagement_id: str) -> list[str]:
    query = (
        select(RedactionTerm.term)
        .where(RedactionTerm.engagement_id == engagement_id)
        .where(RedactionTerm.origin == CONFIDENTIAL_ORIGIN)
        .order_by(RedactionTerm.created_at, RedactionTerm.id)
    )
    return list(session.scalars(query))


def _view(session: Session, row: Engagement) -> EngagementView:
    return EngagementView(
        id=row.id,
        name=row.name,
        process_name=row.process_name,
        trigger=row.trigger,
        end_point=row.end_point,
        in_scope_roles=list(row.in_scope_roles),
        out_of_scope=row.out_of_scope,
        process_kpi=row.process_kpi,
        industry=row.industry,
        adjacent_industries=list(row.adjacent_industries),
        confidential_terms=_confidential_terms(session, row.id),
        conventions=MappingConventions.model_validate(row.conventions or {}),
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def create(session: Session, fields: dict[str, Any]) -> EngagementView:
    row = Engagement(**{k: v for k, v in fields.items() if k in SCOPE_COLUMNS})
    session.add(row)
    session.flush()
    if "confidential_terms" in fields:
        set_confidential_terms(session, row.id, fields["confidential_terms"])
    return _view(session, row)


def get(session: Session, engagement_id: str) -> EngagementView | None:
    row = session.get(Engagement, engagement_id)
    return _view(session, row) if row else None


def exists(session: Session, engagement_id: str) -> bool:
    return session.get(Engagement, engagement_id) is not None


def update(session: Session, engagement_id: str, fields: dict[str, Any]) -> EngagementView | None:
    row = session.get(Engagement, engagement_id)
    if row is None:
        return None
    for name, value in fields.items():
        if name in SCOPE_COLUMNS:
            setattr(row, name, value)
    if "confidential_terms" in fields:
        set_confidential_terms(session, row.id, fields["confidential_terms"])
    row.updated_at = now_iso()
    session.flush()
    return _view(session, row)


def touch(session: Session, engagement_id: str) -> None:
    """Mark the engagement as changed (e.g. a role or source was added)."""
    row = session.get(Engagement, engagement_id)
    if row is not None:
        row.updated_at = now_iso()


def delete(session: Session, engagement_id: str) -> bool:
    row = session.get(Engagement, engagement_id)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def set_confidential_terms(session: Session, engagement_id: str, terms: list[str]) -> None:
    existing = session.scalars(
        select(RedactionTerm)
        .where(RedactionTerm.engagement_id == engagement_id)
        .where(RedactionTerm.origin == CONFIDENTIAL_ORIGIN)
    )
    for row in existing:
        session.delete(row)
    for term in terms:
        session.add(
            RedactionTerm(
                engagement_id=engagement_id, term=term, replacement="", origin=CONFIDENTIAL_ORIGIN
            )
        )
    session.flush()


def latest_version(
    session: Session, engagement_id: str
) -> tuple[VersionLabel | None, ReviewProgress]:
    """The newest map version's label and how many of its steps have been reviewed.

    Start and end are structural, not steps, so they are not counted (PRD §3.7).
    """
    latest = session.scalars(
        select(MapVersion)
        .where(MapVersion.engagement_id == engagement_id)
        .where(MapVersion.state != "building")  # a refresh's half-built version is never shown
        .order_by(MapVersion.created_at.desc(), MapVersion.id)
        .limit(1)
    ).first()
    if latest is None:
        return None, ReviewProgress(reviewed=0, total=0)
    total = (
        session.scalar(
            select(func.count())
            .select_from(Element)
            .where(Element.version_id == latest.id)
            .where(Element.kind.in_(STEPS))
        )
        or 0
    )
    reviewed = (
        session.scalar(
            select(func.count())
            .select_from(Element)
            .where(Element.version_id == latest.id)
            .where(Element.kind.in_(STEPS))
            .where(Element.review_status != ReviewStatus.DRAFT.value)
        )
        or 0
    )
    label = VersionLabel(label=latest.label, state=latest.state)
    return label, ReviewProgress(reviewed=reviewed, total=total)


def list_summaries(session: Session) -> list[EngagementSummary]:
    rows = session.scalars(select(Engagement).order_by(Engagement.updated_at.desc(), Engagement.id))
    summaries = []
    for row in rows:
        label, progress = latest_version(session, row.id)
        sources = (
            session.scalar(
                select(func.count()).select_from(Source).where(Source.engagement_id == row.id)
            )
            or 0
        )
        view = _view(session, row)
        summaries.append(
            EngagementSummary(
                **view.model_dump(),
                latest_version=label,
                review_progress=progress,
                sources_count=sources,
            )
        )
    return summaries


# --- Roles ------------------------------------------------------------------------------------


def _role_view(row: Role) -> RoleView:
    return RoleView(
        id=row.id,
        engagement_id=row.engagement_id,
        name=row.name,
        aliases=list(row.aliases),
        is_system=row.is_system,
        lane_order=row.lane_order,
    )


def _roles(session: Session, engagement_id: str) -> list[Role]:
    query = (
        select(Role)
        .where(Role.engagement_id == engagement_id)
        .order_by(Role.lane_order.is_(None), Role.lane_order, Role.created_at, Role.id)
    )
    return list(session.scalars(query))


def list_roles(session: Session, engagement_id: str) -> list[RoleView]:
    return [_role_view(r) for r in _roles(session, engagement_id)]


def get_role(session: Session, role_id: str) -> RoleView | None:
    row = session.get(Role, role_id)
    return _role_view(row) if row else None


def role_name_taken(
    session: Session, engagement_id: str, name: str, exclude_id: str | None = None
) -> bool:
    for row in _roles(session, engagement_id):
        if row.name.casefold() == name.casefold() and row.id != exclude_id:
            return True
    return False


def create_role(
    session: Session, engagement_id: str, name: str, aliases: list[str], is_system: bool
) -> RoleView:
    count = len(_roles(session, engagement_id))
    row = Role(
        engagement_id=engagement_id,
        name=name,
        aliases=aliases,
        is_system=is_system,
        lane_order=count + 1,
    )
    session.add(row)
    session.flush()
    return _role_view(row)


def update_role(session: Session, role_id: str, fields: dict[str, Any]) -> RoleView | None:
    row = session.get(Role, role_id)
    if row is None:
        return None
    for name in ("name", "aliases", "is_system"):
        if name in fields:
            setattr(row, name, fields[name])
    if "lane_order" in fields:
        roles = [r for r in _roles(session, row.engagement_id) if r.id != row.id]
        position = max(1, min(int(fields["lane_order"]), len(roles) + 1))
        roles.insert(position - 1, row)
        for index, role in enumerate(roles, start=1):
            role.lane_order = index
    session.flush()
    return _role_view(row)


def role_names(session: Session, engagement_id: str) -> frozenset[str]:
    """Every role name and alias in the engagement, in lower case."""
    names: set[str] = set()
    for row in session.scalars(select(Role).where(Role.engagement_id == engagement_id)):
        names.add(row.name.casefold())
        names.update(alias.casefold() for alias in row.aliases)
    return frozenset(names)
