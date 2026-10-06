"""Interviewee profiles (PRD §3.5 `interviewee_profiles`; C5a): the only database access."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.interview import GuideView, InterviewDocument, ProfileView
from app.repositories.tables import IntervieweeProfile, InterviewGuide, Role


def _view(session: Session, row: IntervieweeProfile) -> ProfileView:
    role = session.get(Role, row.role_id) if row.role_id else None
    return ProfileView(
        id=row.id,
        engagement_id=row.engagement_id,
        role_id=row.role_id,
        role_name=role.name if role else "",
        stakeholder_group=row.stakeholder_group,
        interview_type=row.interview_type,
        referred_by_role=row.referred_by_role,
        previous_profile_id=row.previous_profile_session,
        created_at=row.created_at,
    )


def profiles(session: Session, engagement_id: str) -> list[ProfileView]:
    rows = session.scalars(
        select(IntervieweeProfile)
        .where(IntervieweeProfile.engagement_id == engagement_id)
        .order_by(IntervieweeProfile.created_at, IntervieweeProfile.id)
    )
    return [_view(session, r) for r in rows]


def profile(session: Session, profile_id: str) -> ProfileView | None:
    row = session.get(IntervieweeProfile, profile_id)
    return _view(session, row) if row else None


def add_profile(session: Session, engagement_id: str, fields: dict[str, Any]) -> ProfileView:
    row = IntervieweeProfile(engagement_id=engagement_id, **_columns(fields))
    session.add(row)
    session.flush()
    return _view(session, row)


def update_profile(session: Session, profile_id: str, fields: dict[str, Any]) -> ProfileView:
    row = session.get(IntervieweeProfile, profile_id)
    assert row is not None
    for name, value in _columns(fields).items():
        setattr(row, name, value)
    session.flush()
    return _view(session, row)


def _columns(fields: dict[str, Any]) -> dict[str, Any]:
    """API names → column names (the previous session is stored as `previous_profile_session`)."""
    out = dict(fields)
    if "previous_profile_id" in out:
        out["previous_profile_session"] = out.pop("previous_profile_id")
    return out


# --- Tailored guides (PRD §3.5 `interview_guides`; G1) -----------------------------------------


def _guide(row: InterviewGuide) -> GuideView:
    return GuideView(
        id=row.id,
        engagement_id=row.engagement_id,
        profile_id=row.profile_id,
        interview_type=row.interview_type,
        version=row.version,
        edited=row.edited,
        created_at=row.created_at,
        document=InterviewDocument.model_validate(row.content),
    )


def latest_guide(session: Session, profile_id: str) -> GuideView | None:
    row = session.scalars(
        select(InterviewGuide)
        .where(InterviewGuide.profile_id == profile_id)
        .order_by(InterviewGuide.version.desc())
        .limit(1)
    ).first()
    return _guide(row) if row else None


def add_guide(
    session: Session, engagement_id: str, profile_id: str, document: InterviewDocument
) -> GuideView:
    """A new version of this profile's guide (1, 2, …); earlier versions are kept."""
    latest = latest_guide(session, profile_id)
    row = InterviewGuide(
        engagement_id=engagement_id,
        profile_id=profile_id,
        interview_type=document.kind.value,
        version=latest.version + 1 if latest else 1,
        content=document.model_dump(mode="json"),
    )
    session.add(row)
    session.flush()
    return _guide(row)
