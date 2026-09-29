"""Start Process Map Studio (PRD §3.1, §3.10).

Backs up data/app.db to data/backups/ if a database update is waiting, applies the update,
starts one local server on 127.0.0.1 serving the API and the built screens, opens the
browser, and keeps running until this window is closed.

Run by Start.command (Mac) and start.bat (Windows). Standard library only.
Options for developers and tests: --port N, --no-browser.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from launcher_common import (
    BACKEND,
    FRONTEND,
    NOT_SET_UP,
    ROOT,
    configured_port,
    data_dir,
    exit_with,
    port_is_free,
    say,
    venv_python,
)

STARTUP_TIMEOUT_S = 60
# Talk to the local app directly, never through a proxy set on this computer.
LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def backup_database(data_dir: Path, now: dt.datetime) -> Path | None:
    """Copy data/app.db to data/backups/app-<date-time>.db; None if there is no database yet."""
    database = data_dir / "app.db"
    if not database.is_file():
        return None
    backups = data_dir / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    target = backups / f"app-{now:%Y%m%d-%H%M%S}.db"
    shutil.copy2(database, target)
    return target


def backend_env(data: Path) -> dict[str, str]:
    """Environment for the backend: the same data folder the launcher backs up."""
    return {**os.environ, "DATA_DIR": str(data)}


def pending_migrations(python: Path, data: Path) -> int:
    result = subprocess.run(
        [str(python), "-m", "app.manage", "pending-migrations"],
        cwd=BACKEND,
        env=backend_env(data),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        exit_with(
            "The app could not check its database. Run Setup again; if this keeps happening, "
            "open Claude Code in the app folder and paste the Bug-fix prompt."
        )
    return int(result.stdout.strip() or "0")


def apply_database_updates(python: Path, data: Path) -> None:
    if pending_migrations(python, data) == 0:
        return
    backup = backup_database(data, dt.datetime.now())
    if backup:
        say(f"Saved a safety copy of your database: {backup}")
    say("Applying a database update...")
    result = subprocess.run(
        [str(python), "-m", "app.manage", "upgrade"],
        cwd=BACKEND,
        env=backend_env(data),
        check=False,
    )
    if result.returncode != 0:
        exit_with(
            "The database update did not finish. Your safety copy is in data/backups. "
            "Open Claude Code in the app folder and paste the Bug-fix prompt."
        )


def wait_until_ready(url: str, server: subprocess.Popen[bytes], timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if server.poll() is not None:
            return False
        try:
            with LOCAL_OPENER.open(f"{url}/api/health", timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(0.3)
    return False


def stop(server: subprocess.Popen[bytes]) -> None:
    if server.poll() is None:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start Process Map Studio.")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    python = venv_python(ROOT)
    if not python.exists() or not (FRONTEND / "dist" / "index.html").is_file():
        exit_with(NOT_SET_UP)

    port = args.port or configured_port(ROOT)
    if not port_is_free(port):
        exit_with(
            f"Port already in use: something is already using port {port}. The app may "
            "already be running; look for its window, or restart your computer and start again."
        )

    data = data_dir(ROOT)
    data.mkdir(parents=True, exist_ok=True)
    apply_database_updates(python, data)

    url = f"http://127.0.0.1:{port}"
    say("Starting Process Map Studio...")
    env = {**backend_env(data), "APP_PORT": str(port)}
    server = subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=BACKEND,
        env=env,
    )

    def handle_terminate(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, handle_terminate)
    # Closing the Terminal window (macOS) sends a hang-up; stop the server then too.
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, handle_terminate)
    try:
        if not wait_until_ready(url, server, STARTUP_TIMEOUT_S):
            stop(server)
            exit_with(
                "The app did not start. Run Setup again; if this keeps happening, open Claude "
                "Code in the app folder and paste the Bug-fix prompt."
            )
        if not args.no_browser:
            webbrowser.open(url)
        say()
        say(f"Process Map Studio is running at {url}")
        say("Close this window to stop it.")
        server.wait()
    except KeyboardInterrupt:
        say("Stopping Process Map Studio...")
    finally:
        stop(server)
    return 0


if __name__ == "__main__":
    sys.exit(main())
