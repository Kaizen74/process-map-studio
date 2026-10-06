"""Interviewee profiles (PRD §3.5 `interviewee_profiles`; C5a): the only database access."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.interview import ProfileView
from app.repositories.tables import IntervieweeProfile, Role


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
