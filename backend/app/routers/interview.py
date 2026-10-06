"""Interview tools for an engagement (API_CONTRACT.md → Interviewee profiles; phase P4c)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import interview
from app.domain.interview import ProfileInput, ProfilePatch, ProfileView
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
