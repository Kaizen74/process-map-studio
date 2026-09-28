"""Draft endpoints (API_CONTRACT.md → Draft)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import draft
from app.domain.models import DraftStarted, DraftState, RejectedClaims
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["draft"])


@router.post("/engagements/{engagement_id}/draft", status_code=202)
def start_draft(request: Request, engagement_id: str) -> DraftStarted:
    state = request.app.state
    return unwrap(
        draft.start_draft(state.config, state.sessions, engagement_id, state.worker.submit)
    )


@router.post("/versions/{version_id}/refresh", status_code=202)
def start_refresh(request: Request, version_id: str) -> DraftStarted:
    state = request.app.state
    return unwrap(
        draft.start_refresh(state.config, state.sessions, version_id, state.worker.submit)
    )


@router.get("/engagements/{engagement_id}/draft")
def get_draft(request: Request, engagement_id: str) -> DraftState:
    return unwrap(draft.get_draft(request.app.state.sessions, engagement_id))


@router.get("/versions/{version_id}/rejected-claims")
def rejected_claims(request: Request, version_id: str) -> RejectedClaims:
    return unwrap(draft.rejected_claims(request.app.state.sessions, version_id))
