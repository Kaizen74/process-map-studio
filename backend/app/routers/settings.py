"""Settings endpoints (API_CONTRACT.md → Settings)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import settings
from app.domain.models import ApiKeyUpdate, ProfileUpdate, SettingsView
from app.routers.http import unwrap

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings(request: Request) -> SettingsView:
    return unwrap(settings.get_settings(request.app.state.config))


@router.put("/profile")
def update_profile(request: Request, body: ProfileUpdate) -> SettingsView:
    return unwrap(settings.update_profile(request.app.state.config, body.owner_name))


@router.put("/key")
def save_api_key(request: Request, body: ApiKeyUpdate) -> SettingsView:
    return unwrap(
        settings.save_api_key(request.app.state.config, body.anthropic_api_key.get_secret_value())
    )
