"""Standard interview templates and the data request template (API_CONTRACT.md → Interview
templates; GET /templates/data-request). No engagement needed."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response

from app.actions import data_request, interview_templates
from app.domain.interview import TemplateSummary
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["templates"])


@router.get("/templates/interview/plans")
def template_plans() -> list[TemplateSummary]:
    return unwrap(interview_templates.plans())


@router.get("/templates/interview")
def interview_template(
    kind: str = Query("", alias="type"), fmt: str = Query("", alias="format")
) -> Response:
    file = unwrap(interview_templates.template_file(kind, fmt))
    return Response(
        content=file.content,
        media_type=file.media_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )


@router.get("/templates/data-request")
def data_request_template(fmt: str = Query("", alias="format")) -> Response:
    file = unwrap(data_request.template_file(fmt))
    return Response(
        content=file.content,
        media_type=file.media_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )
