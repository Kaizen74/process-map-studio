"""Source endpoints (API_CONTRACT.md → Sources)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, Response, UploadFile

from app.actions import sources
from app.domain.models import (
    SegmentPage,
    SegmentPatch,
    SegmentView,
    SourcePatch,
    SourceView,
    SpeakerView,
)
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["sources"])


@router.post("/engagements/{engagement_id}/sources", status_code=201)
def upload_source(
    request: Request,
    engagement_id: str,
    file: Annotated[UploadFile, File()],
    kind: Annotated[str | None, Form()] = None,
    version_date: Annotated[str | None, Form()] = None,
    owner: Annotated[str | None, Form()] = None,
    controlled_copy: Annotated[bool, Form()] = False,
) -> SourceView:
    state = request.app.state
    return unwrap(
        sources.upload_source(
            state.config,
            state.sessions,
            engagement_id,
            filename=file.filename or "",
            stream=file.file,
            content_type=file.content_type or "",
            enqueue=state.worker.submit,
            kind=kind or None,
            version_date=version_date,
            owner=owner,
            controlled_copy=controlled_copy,
        )
    )


@router.get("/engagements/{engagement_id}/sources")
def list_sources(request: Request, engagement_id: str) -> list[SourceView]:
    return unwrap(sources.list_sources(request.app.state.sessions, engagement_id))


@router.get("/sources/{source_id}")
def get_source(request: Request, source_id: str) -> SourceView:
    return unwrap(sources.get_source(request.app.state.sessions, source_id))


@router.patch("/sources/{source_id}")
def update_source(request: Request, source_id: str, body: SourcePatch) -> SourceView:
    state = request.app.state
    return unwrap(
        sources.update_source(state.config, state.sessions, source_id, body, state.worker.submit)
    )


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(request: Request, source_id: str) -> Response:
    state = request.app.state
    unwrap(sources.delete_source(state.config, state.sessions, source_id))
    return Response(status_code=204)


@router.get("/sources/{source_id}/segments")
def list_segments(
    request: Request,
    source_id: str,
    page: int = 1,
    page_size: int = 200,
    raw: bool = False,
    around: str | None = None,
) -> SegmentPage:
    return unwrap(
        sources.list_segments(
            request.app.state.sessions, source_id, page, page_size, raw=raw, around=around
        )
    )


@router.patch("/segments/{segment_id}")
def correct_segment(request: Request, segment_id: str, body: SegmentPatch) -> SegmentView:
    state = request.app.state
    return unwrap(sources.correct_segment(state.config, state.sessions, segment_id, body))


@router.get("/sources/{source_id}/speakers")
def get_speakers(request: Request, source_id: str) -> list[SpeakerView]:
    return unwrap(sources.get_speakers(request.app.state.sessions, source_id))


@router.put("/sources/{source_id}/speakers")
def map_speakers(
    request: Request, source_id: str, body: dict[str, str | None]
) -> list[SpeakerView]:
    state = request.app.state
    return unwrap(sources.map_speakers(state.config, state.sessions, source_id, body))
