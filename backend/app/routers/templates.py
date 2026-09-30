"""Standard interview templates (API_CONTRACT.md → Interview templates). No engagement needed."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response

from app.actions import interview_templates
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
