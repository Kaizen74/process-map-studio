"""Draft endpoints (API_CONTRACT.md → Draft)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import draft, draft_cost, run_records
from app.domain.models import (
    DraftEstimate,
    DraftStarted,
    DraftState,
    OutsideFlowClaims,
    RefreshCheck,
    RejectedClaims,
)
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


@router.get("/versions/{version_id}/refresh-check")
def refresh_check(request: Request, version_id: str) -> RefreshCheck:
    state = request.app.state
    return unwrap(run_records.refresh_check(state.config, state.sessions, version_id))


@router.get("/engagements/{engagement_id}/draft/estimate")
def draft_estimate(request: Request, engagement_id: str) -> DraftEstimate:
    state = request.app.state
    return unwrap(draft_cost.estimate(state.config, state.sessions, engagement_id))


@router.get("/engagements/{engagement_id}/draft")
def get_draft(request: Request, engagement_id: str) -> DraftState:
    return unwrap(draft.get_draft(request.app.state.sessions, engagement_id))


@router.get("/versions/{version_id}/rejected-claims")
def rejected_claims(request: Request, version_id: str) -> RejectedClaims:
    return unwrap(draft.rejected_claims(request.app.state.sessions, version_id))


@router.get("/versions/{version_id}/outside-flow")
def outside_flow(request: Request, version_id: str) -> OutsideFlowClaims:
    return unwrap(draft.outside_flow(request.app.state.sessions, version_id))
