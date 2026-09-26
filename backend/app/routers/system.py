"""System endpoints (API_CONTRACT.md → System)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import system
from app.domain.models import HealthInfo
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(request: Request) -> HealthInfo:
    return unwrap(system.get_health(request.app.state.config))
