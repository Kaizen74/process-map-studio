"""Engagement and role endpoints (API_CONTRACT.md → Engagements and roles)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.actions import another_flow, countries, engagements
from app.domain.models import (
    AnotherCountry,
    AnotherFlow,
    EngagementCreate,
    EngagementSummary,
    EngagementView,
    RoleCreate,
    RolePatch,
    RoleView,
    ScopeFields,
)
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["engagements"])


@router.post("/engagements", status_code=201)
def create_engagement(request: Request, body: EngagementCreate) -> EngagementView:
    state = request.app.state
    return unwrap(engagements.create_engagement(state.config, state.sessions, body))


@router.get("/engagements")
def list_engagements(request: Request) -> list[EngagementSummary]:
    return unwrap(engagements.list_engagements(request.app.state.sessions))


@router.get("/engagements/{engagement_id}")
def get_engagement(request: Request, engagement_id: str) -> EngagementView:
    return unwrap(engagements.get_engagement(request.app.state.sessions, engagement_id))


@router.patch("/engagements/{engagement_id}")
def update_engagement(request: Request, engagement_id: str, body: ScopeFields) -> EngagementView:
    state = request.app.state
    return unwrap(engagements.update_engagement(state.config, state.sessions, engagement_id, body))


@router.post("/engagements/{engagement_id}/another-country", status_code=201)
def another_country(request: Request, engagement_id: str, body: AnotherCountry) -> EngagementView:
    state = request.app.state
    return unwrap(countries.another_country(state.config, state.sessions, engagement_id, body))


@router.post("/engagements/{engagement_id}/another-flow", status_code=201)
def start_another_flow(request: Request, engagement_id: str, body: AnotherFlow) -> EngagementView:
    state = request.app.state
    return unwrap(another_flow.another_flow(state.config, state.sessions, engagement_id, body))


@router.delete("/engagements/{engagement_id}", status_code=204)
def delete_engagement(request: Request, engagement_id: str) -> Response:
    state = request.app.state
    unwrap(engagements.delete_engagement(state.config, state.sessions, engagement_id))
    return Response(status_code=204)


@router.get("/engagements/{engagement_id}/roles")
def list_roles(request: Request, engagement_id: str) -> list[RoleView]:
    return unwrap(engagements.list_roles(request.app.state.sessions, engagement_id))


@router.post("/engagements/{engagement_id}/roles", status_code=201)
def create_role(request: Request, engagement_id: str, body: RoleCreate) -> RoleView:
    state = request.app.state
    return unwrap(engagements.create_role(state.config, state.sessions, engagement_id, body))


@router.patch("/roles/{role_id}")
def update_role(request: Request, role_id: str, body: RolePatch) -> RoleView:
    state = request.app.state
    return unwrap(engagements.update_role(state.config, state.sessions, role_id, body))


@router.delete("/roles/{role_id}", status_code=204)
def delete_role(request: Request, role_id: str) -> Response:
    state = request.app.state
    unwrap(engagements.delete_role(state.config, state.sessions, role_id))
    return Response(status_code=204)
