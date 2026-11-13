"""Comparing countries (API_CONTRACT.md → Comparing countries; PRD §3.19; DECISIONS 98)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.actions import comparisons
from app.domain.comparisons import (
    Candidate,
    ComparisonCreate,
    ComparisonSummary,
    ComparisonView,
    DifferenceDecision,
    DifferenceView,
    PairDecision,
    SuggestStarted,
)
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["comparisons"])


@router.get("/engagements/{engagement_id}/comparison-candidates")
def list_candidates(request: Request, engagement_id: str) -> list[Candidate]:
    return unwrap(comparisons.candidates(request.app.state.sessions, engagement_id))


@router.get("/engagements/{engagement_id}/comparisons")
def list_comparisons(request: Request, engagement_id: str) -> list[ComparisonSummary]:
    state = request.app.state
    return unwrap(comparisons.list_comparisons(state.config, state.sessions, engagement_id))


@router.post("/comparisons", status_code=201)
def start_comparison(
    request: Request, response: Response, body: ComparisonCreate
) -> ComparisonView:
    state = request.app.state
    view, created = unwrap(comparisons.start_comparison(state.config, state.sessions, body))
    if not created:
        response.status_code = 200
    return view


@router.get("/comparisons/{comparison_id}")
def get_comparison(request: Request, comparison_id: str) -> ComparisonView:
    state = request.app.state
    return unwrap(comparisons.get_comparison(state.config, state.sessions, comparison_id))


@router.put("/comparisons/{comparison_id}/pairs")
def set_pair(request: Request, comparison_id: str, body: PairDecision) -> ComparisonView:
    state = request.app.state
    return unwrap(comparisons.set_pair(state.config, state.sessions, comparison_id, body))


@router.post("/comparisons/{comparison_id}/suggest", status_code=202)
def suggest_pairs(request: Request, comparison_id: str) -> SuggestStarted:
    state = request.app.state
    return unwrap(
        comparisons.start_suggest(state.config, state.sessions, comparison_id, state.worker.submit)
    )


@router.post("/comparisons/{comparison_id}/refresh")
def refresh(request: Request, comparison_id: str) -> ComparisonView:
    state = request.app.state
    return unwrap(comparisons.refresh(state.config, state.sessions, comparison_id))


@router.put("/comparisons/{comparison_id}/differences/{diff_key:path}")
def decide(
    request: Request, comparison_id: str, diff_key: str, body: DifferenceDecision
) -> DifferenceView:
    state = request.app.state
    return unwrap(comparisons.decide(state.config, state.sessions, comparison_id, diff_key, body))
