"""Interview tools for an engagement (API_CONTRACT.md → Interviewee profiles, Tailored interview
guides; phase P4c)."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from app.actions import interview
from app.domain.interview import GuideInput, GuideView, ProfileInput, ProfilePatch, ProfileView
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["interview"])


@router.get("/engagements/{engagement_id}/profiles")
def list_profiles(request: Request, engagement_id: str) -> list[ProfileView]:
    return unwrap(interview.list_profiles(request.app.state.sessions, engagement_id))


@router.post("/engagements/{engagement_id}/profiles", status_code=201)
def add_profile(request: Request, engagement_id: str, body: ProfileInput) -> ProfileView:
    state = request.app.state
    return unwrap(interview.add_profile(state.config, state.sessions, engagement_id, body))


@router.patch("/profiles/{profile_id}")
def edit_profile(request: Request, profile_id: str, body: ProfilePatch) -> ProfileView:
    state = request.app.state
    return unwrap(interview.edit_profile(state.config, state.sessions, profile_id, body))


@router.post("/engagements/{engagement_id}/interview-guide", status_code=201)
def make_guide(request: Request, engagement_id: str, body: GuideInput) -> GuideView:
    state = request.app.state
    return unwrap(interview.make_guide(state.config, state.sessions, engagement_id, body))


@router.get("/engagements/{engagement_id}/interview-guide")
def get_guide(request: Request, engagement_id: str, profile_id: str = "") -> GuideView:
    return unwrap(interview.get_guide(request.app.state.sessions, engagement_id, profile_id))


@router.get("/engagements/{engagement_id}/interview-guide/export")
def export_guide(
    request: Request, engagement_id: str, profile_id: str = "", fmt: str = Query("", alias="format")
) -> Response:
    sessions = request.app.state.sessions
    file = unwrap(interview.export_guide(sessions, engagement_id, profile_id, fmt))
    return Response(
        content=file.content,
        media_type=file.media_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )
