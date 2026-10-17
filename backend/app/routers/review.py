"""Review endpoints (API_CONTRACT.md → Review, phase P6)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.actions import dispositions, map_edits, merges, questions, review
from app.domain.graph import ElementDetail, GraphEdge
from app.domain.models import (
    AuditEntry,
    DispositionInput,
    DispositionView,
    EdgeInput,
    EdgePatch,
    ElementPatch,
    MergeDecisionInput,
    MergeProposalView,
    NewStep,
    QuestionStatus,
    QuestionView,
    RaciInput,
    WorkTypeInput,
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


@router.put("/elements/{element_id}/work-type")
def set_work_type(request: Request, element_id: str, body: WorkTypeInput) -> ElementDetail:
    state = request.app.state
    return unwrap(review.set_work_type(state.config, state.sessions, element_id, body))


@router.put("/elements/{element_id}/disposition")
def set_disposition(request: Request, element_id: str, body: DispositionInput) -> DispositionView:
    state = request.app.state
    return unwrap(dispositions.set_disposition(state.config, state.sessions, element_id, body))


@router.get("/versions/{version_id}/dispositions")
def get_dispositions(request: Request, version_id: str) -> list[DispositionView]:
    return unwrap(dispositions.get_dispositions(request.app.state.sessions, version_id))


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


@router.get("/versions/{version_id}/questions")
def list_questions(request: Request, version_id: str) -> list[QuestionView]:
    return unwrap(questions.list_questions(request.app.state.sessions, version_id))


@router.patch("/questions/{question_id}")
def set_question_status(request: Request, question_id: str, body: QuestionStatus) -> QuestionView:
    state = request.app.state
    return unwrap(questions.set_status(state.config, state.sessions, question_id, body.status))


@router.get("/versions/{version_id}/merge-proposals")
def list_merge_proposals(request: Request, version_id: str) -> list[MergeProposalView]:
    return unwrap(merges.list_proposals(request.app.state.sessions, version_id))


@router.post("/merge-proposals/{proposal_id}/decision")
def decide_merge(request: Request, proposal_id: str, body: MergeDecisionInput) -> MergeProposalView:
    state = request.app.state
    return unwrap(merges.decide(state.config, state.sessions, proposal_id, body.decision))
