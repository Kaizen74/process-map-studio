"""Deleting an engagement leaves none of its words in the database file (deep review,
2026-10-19). SQLite keeps deleted rows in free pages until something overwrites them, so without
`secure_delete` a deleted client's interview could still be read from data/app.db with any text
viewer. The app's own backups (made only before a database update) are a separate copy and say
so in the README."""

from __future__ import annotations

import sqlite3
import sqlite3.dbapi2
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import AppConfig
from app.main import create_app
from tests.uploads import upload

PHRASE = "Zebracorn quartermaster rebalances the hold"


@pytest.fixture(params=["this build's default", "a build with secure delete off"])
def sqlite_build(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLite's own default differs between builds (this one has SECURE_DELETE on; others, such as
    some Windows and macOS Pythons, may not), so the app must not rely on it."""
    if request.param == "a build with secure delete off":
        connect = sqlite3.dbapi2.connect

        def off(*args: Any, **kwargs: Any) -> sqlite3.Connection:
            connection = connect(*args, **kwargs)
            connection.execute("PRAGMA secure_delete=OFF")
            return connection

        monkeypatch.setattr(sqlite3, "connect", off)
        monkeypatch.setattr(sqlite3.dbapi2, "connect", off)  # the module SQLAlchemy uses


@pytest.mark.usefixtures("sqlite_build")
def test_a_deleted_engagement_s_text_is_not_left_in_the_database_file(
    settings_config: AppConfig,
) -> None:
    with TestClient(create_app(settings_config)) as client:
        created = client.post(
            "/api/engagements", json={"name": "Gone", "trigger": "t", "end_point": "e"}
        ).json()
        transcript = ("Interviewer: What happens next?\nLead: " + PHRASE + " every shift.\n") * 40
        assert upload(client, created["id"], "notes.txt", transcript.encode()).json()["text_status"]
        path = db.db_path(settings_config.data_dir)
        assert PHRASE.encode() in path.read_bytes()  # stored while the engagement exists
        with db.make_engine(path).connect() as connection:
            assert connection.exec_driver_sql("PRAGMA secure_delete").scalar() == 1
        assert client.delete(f"/api/engagements/{created['id']}").status_code == 204
    assert PHRASE.encode() not in path.read_bytes()
