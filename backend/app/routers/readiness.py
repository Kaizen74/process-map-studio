"""Readiness endpoint (API_CONTRACT.md → Readiness)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import readiness
from app.domain.models import Readiness
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["readiness"])


@router.get("/engagements/{engagement_id}/readiness")
def get_readiness(request: Request, engagement_id: str) -> Readiness:
    state = request.app.state
    return unwrap(readiness.get_readiness(state.config, state.sessions, engagement_id))
