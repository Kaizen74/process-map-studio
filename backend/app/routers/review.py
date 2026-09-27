"""Review endpoints (API_CONTRACT.md → Review, phase P6)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.actions import map_edits, review
from app.domain.graph import ElementDetail, GraphEdge
from app.domain.models import (
    AuditEntry,
    EdgeInput,
    EdgePatch,
    ElementPatch,
    NewStep,
    RaciInput,
)
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["review"])


def _review(request: Request, element_id: str, action: str) -> ElementDetail:
    state = request.app.state
    return unwrap(review.review(state.config, state.sessions, element_id, action))


@router.post("/elements/{element_id}/confirm")
def confirm(request: Request, element_id: str) -> ElementDetail:
    return _review(request, element_id, "confirm")


@router.post("/elements/{element_id}/reject")
def reject(request: Request, element_id: str) -> ElementDetail:
    return _review(request, element_id, "reject")


@router.post("/elements/{element_id}/restore")
def restore(request: Request, element_id: str) -> ElementDetail:
    return _review(request, element_id, "restore")


@router.patch("/elements/{element_id}")
def edit(request: Request, element_id: str, patch: ElementPatch) -> ElementDetail:
    state = request.app.state
    return unwrap(review.edit(state.config, state.sessions, element_id, patch))


@router.put("/elements/{element_id}/raci")
def set_raci(request: Request, element_id: str, raci: list[RaciInput]) -> ElementDetail:
    state = request.app.state
    return unwrap(review.set_raci(state.config, state.sessions, element_id, raci))


@router.get("/versions/{version_id}/audit")
def get_audit(request: Request, version_id: str) -> list[AuditEntry]:
    return unwrap(review.get_audit(request.app.state.sessions, version_id))


@router.post("/versions/{version_id}/elements", status_code=201)
def add_step(request: Request, version_id: str, step: NewStep) -> ElementDetail:
    state = request.app.state
    return unwrap(map_edits.add_step(state.config, state.sessions, version_id, step))


@router.post("/versions/{version_id}/edges", status_code=201)
def add_edge(request: Request, version_id: str, edge: EdgeInput) -> GraphEdge | None:
    state = request.app.state
    return unwrap(map_edits.add_edge(state.config, state.sessions, version_id, edge))


@router.patch("/versions/{version_id}/edges/{edge_id}")
def change_edge(
    request: Request, version_id: str, edge_id: str, change: EdgePatch
) -> GraphEdge | None:
    state = request.app.state
    return unwrap(map_edits.change_edge(state.config, state.sessions, version_id, edge_id, change))


@router.delete("/versions/{version_id}/edges/{edge_id}", status_code=204)
def remove_edge(request: Request, version_id: str, edge_id: str) -> Response:
    state = request.app.state
    unwrap(map_edits.remove_edge(state.config, state.sessions, version_id, edge_id))
    return Response(status_code=204)
