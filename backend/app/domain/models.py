"""Pydantic models shared by all layers (PRD §3.2). Domain models for §3.5 arrive in phase P1."""

from __future__ import annotations

from pydantic import BaseModel, SecretStr


class HealthInfo(BaseModel):
    """GET /api/health response (API_CONTRACT.md)."""

    status: str
    app_version: str
    prd_version: str


class SettingsView(BaseModel):
    """The Settings object (API_CONTRACT.md → Settings). Never contains the API key itself."""

    owner_name: str
    model: str
    effort: str
    verifier_enabled: bool
    web_research_enabled: bool
    key_set: bool
    key_last4: str


class ProfileUpdate(BaseModel):
    owner_name: str


class ApiKeyUpdate(BaseModel):
    # SecretStr keeps the key out of repr, str, logs and JSON dumps.
    anthropic_api_key: SecretStr
