"""settings_store service (PRD §3.2, §3.4)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from app.domain.result import Err, ErrorKind, Ok
from app.services.settings_store import mask_key, read_env, write_env_key


def test_missing_file_reads_as_empty(tmp_path: Path) -> None:
    assert read_env(tmp_path / ".env") == Ok({})


def test_reads_pairs_ignoring_comments_blanks_and_quotes(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "# comment\n\nOWNER_NAME='Eric Yim'\nANTHROPIC_MODEL=\"claude-opus-5-5\"\n"
        "APP_PORT = 8000\nnot a setting\nEMPTY=\n"
    )
    assert read_env(path) == Ok(
        {
            "OWNER_NAME": "Eric Yim",
            "ANTHROPIC_MODEL": "claude-opus-5-5",
            "APP_PORT": "8000",
            "EMPTY": "",
        }
    )


def test_write_appends_a_new_setting(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    assert write_env_key(path, "OWNER_NAME", "Eric") == Ok(None)
    assert path.read_text() == "OWNER_NAME=Eric\n"


def test_write_replaces_in_place_and_keeps_everything_else(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "# my notes\nANTHROPIC_API_KEY=\n# OWNER_NAME=old comment\n"
        "OWNER_NAME=Owner\nAPP_PORT=8000\n"
    )
    assert write_env_key(path, "OWNER_NAME", "Eric Yim") == Ok(None)
    assert path.read_text() == (
        "# my notes\nANTHROPIC_API_KEY=\n# OWNER_NAME=old comment\n"
        "OWNER_NAME=Eric Yim\nAPP_PORT=8000\n"
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_written_file_is_private_to_the_user(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("X=1\n")
    os.chmod(path, 0o644)
    write_env_key(path, "OWNER_NAME", "Eric")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_no_temporary_files_are_left_behind(tmp_path: Path) -> None:
    write_env_key(tmp_path / ".env", "OWNER_NAME", "Eric")
    assert [p.name for p in tmp_path.iterdir()] == [".env"]


@pytest.mark.parametrize("value", ["line\nbreak", "tab\there", "nul\x00"])
def test_control_characters_are_refused(tmp_path: Path, value: str) -> None:
    result = write_env_key(tmp_path / ".env", "OWNER_NAME", value)
    assert isinstance(result, Err) and result.kind is ErrorKind.VALIDATION
    assert not (tmp_path / ".env").exists()


@pytest.mark.parametrize("name", ["owner_name", "1ABC", "A-B", ""])
def test_bad_setting_names_are_refused(tmp_path: Path, name: str) -> None:
    result = write_env_key(tmp_path / ".env", name, "x")
    assert isinstance(result, Err) and result.kind is ErrorKind.VALIDATION


def test_unreadable_or_unwritable_file_is_an_io_error(tmp_path: Path) -> None:
    folder_in_the_way = tmp_path / ".env"
    folder_in_the_way.mkdir()
    read = read_env(folder_in_the_way)
    write = write_env_key(folder_in_the_way, "OWNER_NAME", "Eric")
    assert isinstance(read, Err) and read.kind is ErrorKind.IO
    assert isinstance(write, Err) and write.kind is ErrorKind.IO


def test_write_failure_is_an_io_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object) -> None:
        raise PermissionError("read-only")

    monkeypatch.setattr("app.services.settings_store.os.replace", refuse)
    result = write_env_key(tmp_path / ".env", "OWNER_NAME", "Eric")
    assert isinstance(result, Err) and result.kind is ErrorKind.IO
    assert list(tmp_path.iterdir()) == []


# Built by concatenation so the source never contains a key-shaped string (secret check).
FAKE_KEY = "sk-" + "ant-" + "api03-abcdefghijklmnop-WXYZ"


@pytest.mark.parametrize(
    ("key", "shown"),
    [("", ""), ("short", ""), (FAKE_KEY, "WXYZ"), (f"  {FAKE_KEY}\n", "WXYZ")],
)
def test_mask_key_shows_only_the_last_four(key: str, shown: str) -> None:
    assert mask_key(key) == shown
