"""Settings store (PRD §3.2, §3.4): read and write the local .env file; mask the API key.

Shared mechanics only: explicit paths in, Ok/Err out. No database, no domain rules. Callers
(actions) decide which keys may be written and validate values for meaning.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from app.domain.result import Err, ErrorKind, Ok, Result

_KEY_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
_UNSAFE_VALUE = re.compile(r"[\x00-\x1f\x7f]")
_MIN_KEY_LENGTH_TO_REVEAL_LAST4 = 12


def _parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name.strip()] = value
    return values


def read_env(path: Path) -> Result[dict[str, str]]:
    """Read KEY=VALUE pairs from a .env file. A missing file is an empty result, not an error."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Ok({})
    except (OSError, UnicodeDecodeError) as exc:
        return Err(
            ErrorKind.IO, "The settings file could not be read.", {"reason": type(exc).__name__}
        )
    return Ok(_parse(text))


def write_env_key(path: Path, name: str, value: str) -> Result[None]:
    """Set one KEY=VALUE in the .env file, keeping every other line and comment as it was.

    The file is replaced atomically and, on macOS and Linux, readable only by the current user.
    """
    if not _KEY_NAME.match(name):
        return Err(ErrorKind.VALIDATION, "That setting name isn't allowed.", {"name": name})
    if _UNSAFE_VALUE.search(value):
        return Err(
            ErrorKind.VALIDATION, "Settings can't contain line breaks or control characters."
        )
    try:
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    except (OSError, UnicodeDecodeError) as exc:
        return Err(
            ErrorKind.IO, "The settings file could not be read.", {"reason": type(exc).__name__}
        )

    new_line = f"{name}={value}"
    replaced = False
    for index, line in enumerate(lines):
        if line.strip().split("=", 1)[0].strip() == name and not line.lstrip().startswith("#"):
            lines[index] = new_line
            replaced = True
    if not replaced:
        lines.append(new_line)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".env.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("\n".join(lines) + "\n")
            if os.name != "nt":
                os.chmod(temp_name, 0o600)
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    except OSError as exc:
        return Err(
            ErrorKind.IO, "The settings file could not be saved.", {"reason": type(exc).__name__}
        )
    return Ok(None)


def mask_key(key: str) -> str:
    """The only part of an API key ever shown: its last 4 characters ("" if unset or too short)."""
    key = key.strip()
    if len(key) < _MIN_KEY_LENGTH_TO_REVEAL_LAST4:
        return ""
    return key[-4:]
