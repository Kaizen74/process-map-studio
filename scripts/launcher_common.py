"""Shared helpers for the launch scripts (setup.py, start.py, dev.py).

Standard library only: these scripts run before any dependency is installed (PRD §3.1).
Messages are plain language for a non-technical owner and match README.md's
"If something goes wrong" table.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

REQUIRED_PYTHON = (3, 12)
MIN_NODE = (22, 13)
DEFAULT_PORT = 8000

PYTHON_MISSING = (
    "Python 3.12 was not found. Install Python 3.12 from python.org (README step 1). "
    'On Windows, tick "Add python.exe to PATH" in the installer. Then run setup again.'
)
NODE_MISSING = (
    "Node.js was not found. Install the LTS version from nodejs.org (README step 1), "
    "then run setup again."
)
NOT_SET_UP = (
    "The app isn't set up yet. Double-click Setup.command (Mac) or setup.bat (Windows) "
    "first, wait for 'Setup complete', then start the app again."
)


def say(message: str = "") -> None:
    print(message, flush=True)


def venv_python(root: Path = ROOT) -> Path:
    """Path of the Python inside the app's own environment (it may not exist yet)."""
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def python_is_supported(version: tuple[int, ...]) -> bool:
    return tuple(version[:2]) == REQUIRED_PYTHON


def parse_node_version(text: str) -> tuple[int, int] | None:
    """Turn 'v22.13.1' into (22, 13); None if the text isn't a version."""
    match = re.match(r"\s*v?(\d+)\.(\d+)", text)
    return (int(match.group(1)), int(match.group(2))) if match else None


def node_is_supported(version: tuple[int, int]) -> bool:
    return version >= MIN_NODE


def find_node() -> tuple[str, str] | None:
    """Full paths of node and npm, or None if either is missing."""
    node = shutil.which("node")
    npm = shutil.which("npm")
    return (node, npm) if node and npm else None


def node_version(node: str) -> tuple[int, int] | None:
    result = subprocess.run([node, "--version"], capture_output=True, text=True, check=False)
    return parse_node_version(result.stdout) if result.returncode == 0 else None


def read_env_file(path: Path) -> dict[str, str]:
    """Read KEY=VALUE lines from a .env file (comments and blank lines ignored)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def configured_port(root: Path = ROOT) -> int:
    value = read_env_file(root / ".env").get("APP_PORT", "")
    return int(value) if value.isdigit() else DEFAULT_PORT


def data_dir(root: Path = ROOT) -> Path:
    """The private data folder: DATA_DIR from the environment, else from .env, else ./data.

    Relative paths are inside the app folder. The app is started with the same absolute path,
    so the launcher's safety copy and the app always use the same database.
    """
    value = os.environ.get("DATA_DIR") or read_env_file(root / ".env").get("DATA_DIR") or "./data"
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    """True if the app's server could listen on this port now.

    On macOS and Linux a port just released by a stopped app stays briefly in TIME_WAIT;
    the server (uvicorn) sets SO_REUSEADDR and can still use it, so this check does too.
    An app actively listening still makes the port busy. On Windows SO_REUSEADDR would
    allow sharing a busy port, so it is not set there.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if os.name != "nt":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def exit_with(message: str, code: int = 1) -> NoReturn:
    say(message)
    sys.exit(code)
