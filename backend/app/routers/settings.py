"""Settings endpoints (API_CONTRACT.md → Settings)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.actions import settings
from app.domain.models import (
    AiUsage,
    ApiKeyUpdate,
    ConnectionTest,
    ModelChoices,
    ModelUpdate,
    ModuleSettings,
    ProfileUpdate,
    RegionalSettings,
    ResearchSetting,
    SettingsView,
    WebSearchTest,
)
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


@router.post("/test-connection")
def test_connection(request: Request) -> ConnectionTest:
    return unwrap(settings.test_connection(request.app.state.config))


@router.get("/models")
def list_models(request: Request) -> ModelChoices:
    return unwrap(settings.list_model_choices(request.app.state.config))


@router.put("/model")
def update_model(request: Request, body: ModelUpdate) -> SettingsView:
    return unwrap(
        settings.update_model(
            request.app.state.config,
            body.model,
            body.effort,
            body.verifier_enabled,
            sessions=request.app.state.sessions,
        )
    )


@router.put("/modules")
def set_modules(request: Request, body: ModuleSettings) -> SettingsView:
    state = request.app.state
    return unwrap(settings.set_modules(state.config, body.model_dump(), state.sessions))


@router.put("/regional")
def set_regional(request: Request, body: RegionalSettings) -> SettingsView:
    state = request.app.state
    return unwrap(
        settings.set_regional(state.config, body.currency, body.default_timezone, state.sessions)
    )


@router.put("/research")
def set_research(request: Request, body: ResearchSetting) -> SettingsView:
    return unwrap(settings.set_research(request.app.state.config, body.web_research_enabled))


@router.post("/test-web-search")
def test_web_search(request: Request) -> WebSearchTest:
    state = request.app.state
    return unwrap(settings.test_web_search(state.config, state.sessions))


@router.get("/usage")
def get_usage(request: Request, limit: int = 50) -> AiUsage:
    return unwrap(settings.list_usage(request.app.state.sessions, limit))
