"""Version endpoints (API_CONTRACT.md → Draft: graph, layout, lint; quality card; Views: the
alignment matrix and registers)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import lenses, quality, registers, versions
from app.domain.graph import AlignmentRow, ElementDetail, GlossaryEntry, Graph, LintReport
from app.domain.layout import Layout
from app.domain.models import Registers
from app.domain.quality import QualityCard
from app.domain.sensemaking import View
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["versions"])


@router.get("/versions/{version_id}/graph")
def get_graph(request: Request, version_id: str, view: View | None = None) -> Graph:
    return unwrap(versions.get_graph(request.app.state.sessions, version_id, view))


@router.get("/versions/{version_id}/layout")
def get_layout(
    request: Request, version_id: str, view: View | None = None, show_other: bool = False
) -> Layout:
    return unwrap(versions.get_layout(request.app.state.sessions, version_id, view, show_other))


@router.get("/versions/{version_id}/alignment-matrix")
def get_alignment_matrix(request: Request, version_id: str) -> list[AlignmentRow]:
    return unwrap(versions.get_alignment_matrix(request.app.state.sessions, version_id))


@router.get("/versions/{version_id}/registers")
def get_registers(request: Request, version_id: str) -> Registers:
    return unwrap(registers.get_registers(request.app.state.sessions, version_id))


@router.get("/versions/{version_id}/glossary")
def get_glossary(request: Request, version_id: str) -> list[GlossaryEntry]:
    return unwrap(lenses.get_glossary(request.app.state.sessions, version_id))


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
