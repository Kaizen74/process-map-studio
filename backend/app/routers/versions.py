"""Version endpoints (API_CONTRACT.md → Draft: graph, layout, lint; quality card)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import quality, versions
from app.domain.graph import ElementDetail, Graph, LintReport
from app.domain.layout import Layout
from app.domain.quality import QualityCard
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["versions"])


@router.get("/versions/{version_id}/graph")
def get_graph(request: Request, version_id: str) -> Graph:
    return unwrap(versions.get_graph(request.app.state.sessions, version_id))


@router.get("/versions/{version_id}/layout")
def get_layout(request: Request, version_id: str) -> Layout:
    return unwrap(versions.get_layout(request.app.state.sessions, version_id))


@router.get("/versions/{version_id}/lint")
def get_lint(request: Request, version_id: str) -> LintReport:
    return unwrap(versions.get_lint(request.app.state.sessions, version_id))


@router.get("/versions/{version_id}/quality-card")
def get_quality_card(request: Request, version_id: str) -> QualityCard:
    return unwrap(
        quality.get_quality_card(request.app.state.config, request.app.state.sessions, version_id)
    )


@router.get("/elements/{element_id}")
def get_element(request: Request, element_id: str) -> ElementDetail:
    return unwrap(versions.get_element(request.app.state.sessions, element_id))
