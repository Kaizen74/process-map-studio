"""System log endpoints (API_CONTRACT.md → System records: event logs; R3)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Request, Response, UploadFile

from app.actions import event_logs, log_alignment
from app.domain.system_records import (
    AlignmentInput,
    AlignmentView,
    ColumnMapInput,
    EventLogView,
    ImportInput,
    ImportStarted,
    MetricsView,
    RoleMapInput,
    SuggestStarted,
)
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["system records"])


@router.post("/engagements/{engagement_id}/event-logs", status_code=201)
def upload_log(
    request: Request,
    engagement_id: str,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form()] = "",
    system: Annotated[str, Form()] = "",
    timezone: Annotated[str, Form()] = "",
    window_start: Annotated[str, Form()] = "",
    window_end: Annotated[str, Form()] = "",
) -> EventLogView:
    state = request.app.state
    return unwrap(
        event_logs.upload_log(
            state.config, state.sessions, engagement_id, stream=file.file, name=name,
            system=system, timezone=timezone, window_start=window_start, window_end=window_end,
        )
    )  # fmt: skip


@router.get("/engagements/{engagement_id}/event-logs")
def list_logs(request: Request, engagement_id: str) -> list[EventLogView]:
    return unwrap(event_logs.list_logs(request.app.state.sessions, engagement_id))


@router.get("/event-logs/{log_id}")
def get_log(request: Request, log_id: str) -> EventLogView:
    return unwrap(event_logs.get_log(request.app.state.sessions, log_id))


@router.delete("/event-logs/{log_id}", status_code=204)
def delete_log(request: Request, log_id: str) -> Response:
    state = request.app.state
    unwrap(event_logs.delete_log(state.config, state.sessions, log_id))
    return Response(status_code=204)


@router.put("/event-logs/{log_id}/column-map")
def set_column_map(request: Request, log_id: str, body: ColumnMapInput) -> EventLogView:
    state = request.app.state
    return unwrap(event_logs.set_column_map(state.config, state.sessions, log_id, body))


@router.put("/event-logs/{log_id}/role-map")
def set_role_map(request: Request, log_id: str, body: RoleMapInput) -> EventLogView:
    return unwrap(event_logs.set_role_map(request.app.state.sessions, log_id, body))


@router.post("/event-logs/{log_id}/import", status_code=202)
def start_import(request: Request, log_id: str, body: ImportInput) -> ImportStarted:
    state = request.app.state
    return unwrap(event_logs.start_import(state.sessions, log_id, body, state.worker.submit))


@router.get("/event-logs/{log_id}/metrics")
def get_metrics(request: Request, log_id: str, scope: str = Query("")) -> MetricsView:
    return unwrap(event_logs.get_metrics(request.app.state.sessions, log_id, scope))


@router.get("/event-logs/{log_id}/alignment")
def get_alignment(request: Request, log_id: str) -> AlignmentView:
    return unwrap(log_alignment.get_alignment(request.app.state.sessions, log_id))


@router.put("/event-logs/{log_id}/alignment")
def set_alignment(request: Request, log_id: str, body: AlignmentInput) -> AlignmentView:
    state = request.app.state
    return unwrap(log_alignment.set_alignment(state.config, state.sessions, log_id, body))


@router.post("/event-logs/{log_id}/alignment/suggest", status_code=202)
def suggest_alignment(request: Request, log_id: str) -> SuggestStarted:
    state = request.app.state
    return unwrap(log_alignment.start_suggest(state.sessions, log_id, state.worker.submit))
