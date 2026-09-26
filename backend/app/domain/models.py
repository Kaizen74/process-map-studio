"""Pydantic models shared by all layers (PRD §3.2). Domain models for §3.5 arrive in phase P1."""

from __future__ import annotations

from pydantic import BaseModel


class HealthInfo(BaseModel):
    """GET /api/health response (API_CONTRACT.md)."""

    status: str
    app_version: str
    prd_version: str
