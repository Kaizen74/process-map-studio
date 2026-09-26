"""Developer mode (Claude Code only; PRD §3.1).

Runs the backend on 127.0.0.1:8000 with auto-reload and the Vite dev server on
127.0.0.1:5173, which proxies /api to the backend. Press Ctrl+C to stop both.
Standard library only.
"""

from __future__ import annotations

import subprocess
import sys

from launcher_common import BACKEND, FRONTEND, NOT_SET_UP, exit_with, find_node, say, venv_python


def main() -> int:
    python = venv_python()
    found = find_node()
    if not python.exists() or not found or not (FRONTEND / "node_modules").is_dir():
        exit_with(NOT_SET_UP + " (Developers: python3.12 scripts/setup.py --dev)")
    _, npm = found
    backend = subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--reload",
        ],
        cwd=BACKEND,
    )
    frontend = subprocess.Popen([npm, "run", "dev"], cwd=FRONTEND)
    say("Developer mode: open http://127.0.0.1:5173 (Ctrl+C stops both servers)")
    try:
        while backend.poll() is None and frontend.poll() is None:
            try:
                backend.wait(timeout=1)
            except subprocess.TimeoutExpired:
                continue
    except KeyboardInterrupt:
        pass
    finally:
        for process in (backend, frontend):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
