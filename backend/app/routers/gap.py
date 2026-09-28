"""Gap analysis endpoints (API_CONTRACT.md → Gap analysis)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import gap
from app.domain.gap import BriefPatch, GapAnalysisView, GapBriefView, GapReport, GapStarted
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["gap analysis"])


@router.post("/versions/{version_id}/gap-analyses/internal", status_code=202)
def start_internal(request: Request, version_id: str) -> GapStarted:
    state = request.app.state
    return unwrap(gap.start_internal(state.sessions, version_id, state.worker.submit))


@router.post("/versions/{version_id}/gap-analyses/external", status_code=201)
def start_external(request: Request, version_id: str) -> GapBriefView:
    return unwrap(gap.start_external(request.app.state.sessions, version_id))


@router.patch("/gap-analyses/{analysis_id}/brief")
def update_brief(request: Request, analysis_id: str, body: BriefPatch) -> GapBriefView:
    return unwrap(gap.update_brief(request.app.state.sessions, analysis_id, body))


@router.post("/gap-analyses/{analysis_id}/run", status_code=202)
def run_external(request: Request, analysis_id: str) -> GapStarted:
    state = request.app.state
    return unwrap(gap.run_external(state.config, state.sessions, analysis_id, state.worker.submit))


@router.get("/versions/{version_id}/gap-analyses")
def list_analyses(request: Request, version_id: str) -> list[GapAnalysisView]:
    return unwrap(gap.list_analyses(request.app.state.sessions, version_id))


@router.get("/gap-analyses/{analysis_id}")
def get_report(request: Request, analysis_id: str) -> GapReport:
    return unwrap(gap.get_report(request.app.state.sessions, analysis_id))
