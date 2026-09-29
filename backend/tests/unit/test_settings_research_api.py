"""Web research settings (API_CONTRACT.md → PUT /settings/research, POST /settings/test-web-search;
PRD §3.11.2): off by default; the test search is mocked (MOCK_CLAUDE=1, no key needed for the
fake) and logged in AI usage; web search switched off for the organisation gives the README
message."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import AppConfig
from app.main import create_app

KEY = "sk-" + "ant-" + "api03-" + "R3s34rch" * 6 + "Zq9x"


@pytest.fixture()
def client(settings_config: AppConfig) -> TestClient:
    return TestClient(create_app(settings_config), raise_server_exceptions=False)


def test_research_is_off_by_default_and_switches(client: TestClient) -> None:
    assert client.get("/api/settings").json()["web_research_enabled"] is False
    on = client.put("/api/settings/research", json={"web_research_enabled": True})
    assert on.status_code == 200 and on.json()["web_research_enabled"] is True
    assert client.get("/api/settings").json()["web_research_enabled"] is True
    off = client.put("/api/settings/research", json={"web_research_enabled": False})
    assert off.json()["web_research_enabled"] is False
    bad = client.put("/api/settings/research", json={"web_research_enabled": "maybe"})
    assert bad.status_code == 422
    extra = client.put("/api/settings/research", json={"web_research_enabled": True, "x": 1})
    assert extra.status_code == 422


def test_the_web_search_test_needs_a_key(client: TestClient) -> None:
    tested = client.post("/api/settings/test-web-search")
    assert tested.status_code == 200
    assert tested.json()["available"] is False
    assert tested.json()["message"].startswith("Add your Claude API key first")


def test_the_web_search_test_in_mock_mode_is_logged(client: TestClient, env_file: Path) -> None:
    env_file.write_text(f"ANTHROPIC_API_KEY={KEY}\nMOCK_CLAUDE=1\n")
    tested = client.post("/api/settings/test-web-search")
    assert tested.status_code == 200, tested.text
    assert tested.json() == {
        "available": True,
        "message": "Web search works for your Anthropic organisation.",
    }
    usage = client.get("/api/settings/usage").json()["items"]
    assert [(u["stage_id"], u["status"]) for u in usage] == [("GB_test", "mock")]
    assert KEY not in tested.text


def test_web_search_switched_off_says_where_to_look(
    settings_config: AppConfig, env_file: Path, tmp_path: Path
) -> None:
    fixtures = tmp_path / "fixtures"
    (fixtures / "GB_test").mkdir(parents=True)
    (fixtures / "GB_test" / "default.json").write_text(json.dumps({"error": "web_search_disabled"}))
    config = dataclasses.replace(settings_config, mock_fixtures_dir=fixtures)
    env_file.write_text(f"ANTHROPIC_API_KEY={KEY}\nMOCK_CLAUDE=1\n")
    client = TestClient(create_app(config), raise_server_exceptions=False)
    tested = client.post("/api/settings/test-web-search").json()
    assert tested == {
        "available": False,
        "message": "Web search isn't enabled for your Anthropic organisation. "
        "See the README, 'If something goes wrong'.",
    }
