"""Versions, publish, reopen and exports (API_CONTRACT.md → Versions, publish and exports)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.actions import publish
from app.domain.models import VersionDetail, VersionSummary
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["publish"])


@router.get("/engagements/{engagement_id}/versions")
def list_versions(request: Request, engagement_id: str) -> list[VersionSummary]:
    return unwrap(publish.list_versions(request.app.state.sessions, engagement_id))


@router.get("/versions/{version_id}")
def get_version(request: Request, version_id: str) -> VersionDetail:
    return unwrap(publish.get_version(request.app.state.sessions, version_id))


@router.post("/versions/{version_id}/publish")
def publish_version(request: Request, version_id: str) -> VersionDetail:
    state = request.app.state
    return unwrap(publish.publish(state.config, state.sessions, version_id))


@router.post("/versions/{version_id}/reopen", status_code=201)
def reopen_version(request: Request, version_id: str) -> VersionDetail:
    state = request.app.state
    return unwrap(publish.reopen(state.config, state.sessions, version_id))


@router.get("/versions/{version_id}/export/{fmt}")
def export_version(request: Request, version_id: str, fmt: str) -> Response:
    state = request.app.state
    file = unwrap(publish.export(state.config, state.sessions, version_id, fmt))
    return Response(
        content=file.content.encode("utf-8"),
        media_type=file.media_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )
