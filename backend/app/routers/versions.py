"""Version endpoints (API_CONTRACT.md → Draft: graph and lint)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import versions
from app.domain.graph import Graph, LintReport
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["versions"])


@router.get("/versions/{version_id}/graph")
def get_graph(request: Request, version_id: str) -> Graph:
    return unwrap(versions.get_graph(request.app.state.sessions, version_id))


@router.get("/versions/{version_id}/lint")
def get_lint(request: Request, version_id: str) -> LintReport:
    return unwrap(versions.get_lint(request.app.state.sessions, version_id))
