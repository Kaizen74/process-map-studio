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


def test_the_system_records_module_is_off_by_default_and_switches(client: TestClient) -> None:
    """R7, decision A: optional modules start off; switching off hides, never deletes."""
    assert client.get("/api/settings").json()["system_records_enabled"] is False
    on = client.put("/api/settings/modules", json={"system_records_enabled": True})
    assert on.status_code == 200 and on.json()["system_records_enabled"] is True
    assert client.get("/api/settings").json()["system_records_enabled"] is True
    unchanged = client.put("/api/settings/modules", json={})
    assert unchanged.json()["system_records_enabled"] is True  # a field left out keeps its value
    off = client.put("/api/settings/modules", json={"system_records_enabled": False})
    assert off.json()["system_records_enabled"] is False
    maybe = client.put("/api/settings/modules", json={"system_records_enabled": "maybe"})
    assert maybe.status_code == 422
    assert client.put("/api/settings/modules", json={"gap": True}).status_code == 422


def test_gap_analysis_starts_on_value_starts_off_and_both_switch(client: TestClient) -> None:
    """R10, decision A: gap analysis keeps its old default (on); the value calculator starts off."""
    first = client.get("/api/settings").json()
    assert (first["gap_analysis_enabled"], first["value_enabled"]) == (True, False)
    both = client.put(
        "/api/settings/modules", json={"gap_analysis_enabled": False, "value_enabled": True}
    ).json()
    assert (both["gap_analysis_enabled"], both["value_enabled"]) == (False, True)
    assert both["system_records_enabled"] is False  # left out: unchanged
    one = client.put("/api/settings/modules", json={"gap_analysis_enabled": True}).json()
    assert (one["gap_analysis_enabled"], one["value_enabled"]) == (True, True)
    bad = client.put("/api/settings/modules", json={"value_enabled": "maybe"})
    assert bad.status_code == 422


def test_regional_settings_validate_and_keep_what_is_left_out(client: TestClient) -> None:
    """R10: Settings → Regional (PRD §3.4 item 9): an ISO 4217 code and an IANA time zone."""
    saved = client.put("/api/settings/regional", json={"currency": " usd "})
    assert saved.status_code == 200, saved.text
    assert (saved.json()["currency"], saved.json()["default_timezone"]) == ("USD", "Asia/Singapore")
    zone = client.put("/api/settings/regional", json={"default_timezone": "Europe/London"}).json()
    assert (zone["currency"], zone["default_timezone"]) == ("USD", "Europe/London")
    bad_code = "Enter a three-letter currency code, for example SGD."
    bad_zone = "Choose a time zone from the list, for example Asia/Singapore."
    for body, field, message in (
        ({"currency": "dollars"}, "currency", bad_code),
        ({"currency": "S1D"}, "currency", bad_code),
        ({"default_timezone": "Mars/Olympus"}, "default_timezone", bad_zone),
    ):
        refused = client.put("/api/settings/regional", json=body)
        assert refused.status_code == 422
        error = refused.json()["error"]
        assert (error["details"]["field"], error["message"]) == (field, message)
    assert client.put("/api/settings/regional", json={"locale": "en"}).status_code == 422
    after = client.get("/api/settings").json()
    assert (after["currency"], after["default_timezone"]) == ("USD", "Europe/London")
