"""Redaction-term endpoints (API_CONTRACT.md → Redaction terms)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.actions import redaction
from app.domain.models import RedactionTermCreate, RedactionTermView
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["redaction"])


@router.get("/engagements/{engagement_id}/redaction-terms")
def list_terms(request: Request, engagement_id: str) -> list[RedactionTermView]:
    return unwrap(redaction.list_terms(request.app.state.sessions, engagement_id))


@router.post("/engagements/{engagement_id}/redaction-terms", status_code=201)
def add_term(request: Request, engagement_id: str, body: RedactionTermCreate) -> RedactionTermView:
    state = request.app.state
    return unwrap(redaction.add_term(state.config, state.sessions, engagement_id, body))


@router.delete("/redaction-terms/{term_id}", status_code=204)
def delete_term(request: Request, term_id: str) -> Response:
    state = request.app.state
    unwrap(redaction.delete_term(state.config, state.sessions, term_id))
    return Response(status_code=204)
