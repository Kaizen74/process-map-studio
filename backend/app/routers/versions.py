"""Version endpoints (API_CONTRACT.md → Draft: graph, layout, lint; quality card; Views: the
alignment matrix and registers)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.actions import (
    boundaries,
    coverage,
    exceptions,
    lenses,
    quality,
    registers,
    validation_pack,
    versions,
)
from app.domain.graph import (
    AlignmentRow,
    CapabilityNote,
    ElementDetail,
    GlossaryEntry,
    Graph,
    LintReport,
    StoryEntry,
)
from app.domain.layout import Layout
from app.domain.models import Registers
from app.domain.quality import QualityCard
from app.domain.sensemaking import CoverageReport, ExceptionReport, LaneBoundaryFinding, View
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


@router.get("/versions/{version_id}/capability-notes")
def get_capability_notes(request: Request, version_id: str) -> list[CapabilityNote]:
    return unwrap(lenses.get_capability_notes(request.app.state.sessions, version_id))


@router.get("/versions/{version_id}/coverage")
def get_coverage(request: Request, version_id: str) -> CoverageReport:
    return unwrap(coverage.get_coverage(request.app.state.sessions, version_id))


@router.get("/versions/{version_id}/exceptions")
def get_exceptions(request: Request, version_id: str, view: View | None = None) -> ExceptionReport:
    return unwrap(exceptions.get_exceptions(request.app.state.sessions, version_id, view))


@router.get("/versions/{version_id}/lane-boundaries")
def get_lane_boundaries(request: Request, version_id: str) -> list[LaneBoundaryFinding]:
    return unwrap(boundaries.lane_boundaries(request.app.state.sessions, version_id))


@router.get("/versions/{version_id}/validation-pack")
def get_validation_pack(request: Request, version_id: str) -> Response:
    file = unwrap(validation_pack.validation_pack(request.app.state.sessions, version_id))
    return Response(
        content=file.content.encode("utf-8"),
        media_type=file.media_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )


@router.get("/versions/{version_id}/stories")
def get_stories(request: Request, version_id: str) -> list[StoryEntry]:
    return unwrap(lenses.get_stories(request.app.state.sessions, version_id))


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
