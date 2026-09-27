"""Review endpoints (API_CONTRACT.md → Review, phase P6)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import review
from app.domain.graph import ElementDetail
from app.domain.models import AuditEntry
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


@router.get("/versions/{version_id}/audit")
def get_audit(request: Request, version_id: str) -> list[AuditEntry]:
    return unwrap(review.get_audit(request.app.state.sessions, version_id))
