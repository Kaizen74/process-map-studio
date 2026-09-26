"""System actions."""

from __future__ import annotations

from app.actions.system import get_health
from app.config import load_config
from app.domain.models import HealthInfo
from app.domain.result import Ok


def test_get_health_returns_ok_with_versions() -> None:
    config = load_config({})
    assert get_health(config) == Ok(
        HealthInfo(status="ok", app_version=config.app_version, prd_version=config.prd_version)
    )
