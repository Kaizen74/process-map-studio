"""Intent and Reality endpoints (API_CONTRACT.md → Intent; PRD §4 Intent and Reality; P13)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.actions import intent, intent_ai
from app.domain.reality import (
    ConflictPatch,
    IntentConflictView,
    IntentFields,
    IntentJobStarted,
    IntentPatch,
    IntentView,
)
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["intent and reality"])


@router.get("/engagements/{engagement_id}/intent")
def list_intent(request: Request, engagement_id: str) -> list[IntentView]:
    return unwrap(intent.list_intent(request.app.state.sessions, engagement_id))


@router.post("/engagements/{engagement_id}/intent", status_code=201)
def add_intent(request: Request, engagement_id: str, body: IntentFields) -> IntentView:
    state = request.app.state
    return unwrap(intent.add_owner_stated(state.config, state.sessions, engagement_id, body))


@router.patch("/intent/{intent_id}")
def update_intent(request: Request, intent_id: str, body: IntentPatch) -> IntentView:
    state = request.app.state
    return unwrap(intent.update_intent(state.config, state.sessions, intent_id, body))


@router.delete("/intent/{intent_id}", status_code=204)
def delete_intent(request: Request, intent_id: str) -> Response:
    state = request.app.state
    unwrap(intent.delete_intent(state.config, state.sessions, intent_id))
    return Response(status_code=204)


@router.post("/engagements/{engagement_id}/intent/extract", status_code=202)
def extract_intent(request: Request, engagement_id: str) -> IntentJobStarted:
    state = request.app.state
    return unwrap(intent_ai.start_extract(state.sessions, engagement_id, state.worker.submit))


@router.post("/versions/{version_id}/intent/compare", status_code=202)
def compare_intent(request: Request, version_id: str) -> IntentJobStarted:
    state = request.app.state
    return unwrap(intent_ai.start_compare(state.sessions, version_id, state.worker.submit))


@router.get("/versions/{version_id}/intent/conflicts")
def list_conflicts(request: Request, version_id: str) -> list[IntentConflictView]:
    return unwrap(intent_ai.list_conflicts(request.app.state.sessions, version_id))


@router.patch("/intent-conflicts/{conflict_id}")
def update_conflict(request: Request, conflict_id: str, body: ConflictPatch) -> IntentConflictView:
    state = request.app.state
    return unwrap(intent_ai.update_conflict(state.config, state.sessions, conflict_id, body))
