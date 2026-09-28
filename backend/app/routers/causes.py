"""Cause library endpoints (API_CONTRACT.md → Cause library)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import causes
from app.domain.models import CausePatch, CauseView
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["cause library"])


@router.get("/engagements/{engagement_id}/cause-library")
def list_causes(request: Request, engagement_id: str) -> list[CauseView]:
    return unwrap(causes.list_causes(request.app.state.sessions, engagement_id))


@router.patch("/cause-library/{cause_id}")
def validate_cause(request: Request, cause_id: str, body: CausePatch) -> CauseView:
    state = request.app.state
    return unwrap(causes.validate(state.config, state.sessions, cause_id, body))
