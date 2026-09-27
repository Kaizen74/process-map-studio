"""Review endpoints (API_CONTRACT.md → Review, phase P6)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import review
from app.domain.graph import ElementDetail
from app.domain.models import AuditEntry, ElementPatch, RaciInput
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
