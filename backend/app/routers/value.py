"""Value calculator endpoints (API_CONTRACT.md → Value calculator; PRD §3.14; R9b)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import value
from app.domain.models import (
    AssumptionRow,
    AssumptionsInput,
    RoleCostsInput,
    RoleCostsView,
    StepValueView,
    ValueOverrideInput,
    ValueView,
)
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["value"])


@router.get("/engagements/{engagement_id}/role-costs")
def get_role_costs(request: Request, engagement_id: str) -> RoleCostsView:
    state = request.app.state
    return unwrap(value.get_role_costs(state.config, state.sessions, engagement_id))


@router.put("/engagements/{engagement_id}/role-costs")
def set_role_costs(request: Request, engagement_id: str, body: RoleCostsInput) -> RoleCostsView:
    state = request.app.state
    return unwrap(value.set_role_costs(state.config, state.sessions, engagement_id, body))


@router.get("/engagements/{engagement_id}/value-assumptions")
def get_assumptions(request: Request, engagement_id: str) -> list[AssumptionRow]:
    return unwrap(value.get_assumptions(request.app.state.sessions, engagement_id))


@router.put("/engagements/{engagement_id}/value-assumptions")
def set_assumptions(request: Request, engagement_id: str,
                    body: AssumptionsInput) -> list[AssumptionRow]:  # fmt: skip
    state = request.app.state
    return unwrap(value.set_assumptions(state.config, state.sessions, engagement_id, body))


@router.put("/elements/{element_id}/value-override")
def set_override(request: Request, element_id: str, body: ValueOverrideInput) -> StepValueView:
    state = request.app.state
    return unwrap(value.set_override(state.config, state.sessions, element_id, body))


@router.get("/versions/{version_id}/value")
def get_value(request: Request, version_id: str, view: str = "done") -> ValueView:
    state = request.app.state
    return unwrap(value.get_value(state.config, state.sessions, version_id, view))
