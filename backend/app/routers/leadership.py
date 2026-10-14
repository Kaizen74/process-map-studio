"""Leadership view endpoints (API_CONTRACT.md → Leadership view)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import leadership
from app.domain.leadership import DecisionNeeded, LeadershipView
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["leadership"])


@router.get("/versions/{version_id}/leadership")
def get_view(request: Request, version_id: str) -> LeadershipView:
    state = request.app.state
    return unwrap(leadership.get_view(state.config, state.sessions, version_id))


@router.put("/versions/{version_id}/leadership/decisions")
def save_decisions(
    request: Request, version_id: str, body: list[DecisionNeeded]
) -> list[DecisionNeeded]:
    state = request.app.state
    return unwrap(leadership.save_decisions(state.config, state.sessions, version_id, body))
