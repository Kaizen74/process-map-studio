"""System actions: app health for the launcher and the placeholder page."""

from __future__ import annotations

from app.config import AppConfig
from app.domain.models import HealthInfo
from app.domain.result import Ok, Result


def get_health(config: AppConfig) -> Result[HealthInfo]:
    """Report that the app is running, with its version numbers."""
    return Ok(
        HealthInfo(status="ok", app_version=config.app_version, prd_version=config.prd_version)
    )
