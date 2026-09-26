"""Job endpoints (API_CONTRACT.md → Jobs)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import jobs
from app.domain.models import JobView
from app.routers.http import unwrap

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/jobs/{job_id}")
def get_job(request: Request, job_id: str) -> JobView:
    return unwrap(jobs.get_job(request.app.state.sessions, job_id))
