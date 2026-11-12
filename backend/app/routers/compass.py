"""Capability Compass hand-off and What we are testing (API_CONTRACT.md → Capability Compass
hand-off)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.actions import compass, compass_return
from app.domain.compass import HandoffIn, HandoffPreview, TestingCreate, TestingItem, TestingPatch
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["compass"])


@router.post("/compass/preview")
def preview_handoff(body: HandoffIn) -> HandoffPreview:
    return unwrap(compass.preview(body.handoff))


@router.get("/engagements/{engagement_id}/testing")
def list_testing(request: Request, engagement_id: str) -> list[TestingItem]:
    return unwrap(compass.list_items(request.app.state.sessions, engagement_id))


@router.post("/engagements/{engagement_id}/testing", status_code=201)
def add_testing(request: Request, engagement_id: str, body: TestingCreate) -> TestingItem:
    state = request.app.state
    return unwrap(compass.add_item(state.config, state.sessions, engagement_id, body))


@router.patch("/testing/{item_id}")
def update_testing(request: Request, item_id: str, body: TestingPatch) -> TestingItem:
    state = request.app.state
    return unwrap(compass.update_item(state.config, state.sessions, item_id, body))


@router.delete("/testing/{item_id}", status_code=204)
def delete_testing(request: Request, item_id: str) -> Response:
    state = request.app.state
    unwrap(compass.delete_item(state.config, state.sessions, item_id))
    return Response(status_code=204)


@router.get("/versions/{version_id}/compass-return")
def export_compass_return(
    request: Request, version_id: str, fmt: str = "json", cells: str = ""
) -> Response:
    state = request.app.state
    file = unwrap(
        compass_return.export(state.config, state.sessions, version_id, fmt, cells.split(","))
    )
    return Response(
        content=file.content.encode("utf-8"),
        media_type=file.media_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )
