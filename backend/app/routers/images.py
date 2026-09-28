"""Image endpoints (API_CONTRACT.md → Images)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, Response, UploadFile

from app.actions import images
from app.domain.models import ImagePatch, ImageView
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["images"])


@router.post("/elements/{element_id}/images", status_code=201)
def upload_image(
    request: Request,
    element_id: str,
    file: Annotated[UploadFile, File()],
    caption: Annotated[str, Form()] = "",
    image_type: Annotated[str | None, Form()] = None,
    redaction_confirmed: Annotated[bool, Form()] = False,
) -> ImageView:
    state = request.app.state
    return unwrap(
        images.upload(
            state.config,
            state.sessions,
            element_id,
            stream=file.file,
            caption=caption,
            image_type=image_type,
            redaction_confirmed=redaction_confirmed,
        )
    )


@router.get("/elements/{element_id}/images")
def list_images(request: Request, element_id: str) -> list[ImageView]:
    return unwrap(images.list_images(request.app.state.sessions, element_id))


@router.patch("/images/{image_id}")
def change_image(request: Request, image_id: str, body: ImagePatch) -> ImageView:
    state = request.app.state
    return unwrap(images.change(state.config, state.sessions, image_id, body))


@router.delete("/images/{image_id}", status_code=204)
def remove_image(request: Request, image_id: str) -> Response:
    state = request.app.state
    unwrap(images.remove(state.config, state.sessions, image_id))
    return Response(status_code=204)


@router.get("/images/{image_id}/file")
def image_file(request: Request, image_id: str, size: str = "") -> Response:
    data, media_type = unwrap(
        images.image_file(request.app.state.sessions, image_id, thumb=size == "thumb")
    )
    return Response(content=data, media_type=media_type, headers={"Cache-Control": "no-store"})
