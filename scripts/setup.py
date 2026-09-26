"""One-time setup (run again after every update). PRD §3.1 and §3.10.

Checks Python 3.12 and Node LTS, creates the app's Python environment, installs the
backend and frontend packages, builds the frontend, creates the private data folder and
.env file, and (only in a git repository) switches on the secret-check hook.

Run by Setup.command (Mac) and setup.bat (Windows). Developers: add --dev for check tools.
Standard library only.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

from launcher_common import (
    BACKEND,
    FRONTEND,
    NODE_MISSING,
    PYTHON_MISSING,
    ROOT,
    exit_with,
    find_node,
    node_is_supported,
    node_version,
    python_is_supported,
    say,
    venv_python,
)

TOTAL_STEPS = 7


def step(number: int, text: str) -> None:
    say(f"[{number}/{TOTAL_STEPS}] {text}")


def run(command: list[str], cwd: Path, failure: str) -> None:
    """Run a command, showing its output; stop setup with a plain message if it fails."""
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode != 0:
        exit_with(f"Setup stopped: {failure}")


def check_python() -> None:
    if not python_is_supported((sys.version_info.major, sys.version_info.minor)):
        exit_with(PYTHON_MISSING)


def check_node() -> str:
    """Return the full path of npm if a supported Node.js is installed."""
    found = find_node()
    if not found:
        exit_with(NODE_MISSING)
    node, npm = found
    version = node_version(node)
    if version is None or not node_is_supported(version):
        shown = "unknown" if version is None else f"{version[0]}.{version[1]}"
        exit_with(
            f"Node.js {shown} is too old. Install the LTS version from nodejs.org "
            "(README step 1), then run setup again."
        )
    return npm


def ensure_venv(root: Path) -> Path:
    python = venv_python(root)
    if python.exists():
        probe = subprocess.run(
            [str(python), "-c", "import sys; print(sys.version_info[:2] == (3, 12))"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.stdout.strip() == "True":
            return python
        shutil.rmtree(root / ".venv")
    venv.EnvBuilder(with_pip=True, clear=True).create(root / ".venv")
    return python


def ensure_data_and_env(root: Path) -> list[str]:
    """Create the data folder and a private .env from .env.example; return what was created."""
    created: list[str] = []
    data = root / "data"
    if not data.is_dir():
        data.mkdir(parents=True)
        created.append("data folder")
    env_file = root / ".env"
    example = root / ".env.example"
    if not env_file.exists() and example.is_file():
        shutil.copyfile(example, env_file)
        created.append(".env settings file")
    return created


def activate_hook(root: Path) -> str:
    """Switch on the secret-check hook when this folder is a git repository."""
    if not (root / ".git").exists():
        return "not a git repository; nothing to do"
    git = shutil.which("git")
    if not git:
        return "git isn't installed here; only needed by people changing the code"
    result = subprocess.run([git, "config", "core.hooksPath", ".githooks"], cwd=root, check=False)
    return "switched on" if result.returncode == 0 else "could not be switched on"


def install_test_browser(npm: str) -> str:
    """Developers only: the browser Playwright uses for the accessibility and smoke checks."""
    if os.environ.get("PMS_CHROMIUM_PATH") or os.environ.get("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"):
        return "provided by this computer; nothing to do"
    result = subprocess.run(
        [npm, "exec", "--", "playwright", "install", "chromium"], cwd=FRONTEND, check=False
    )
    return (
        "installed"
        if result.returncode == 0
        else "could not be installed (browser checks will fail)"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Set up Process Map Studio.")
    parser.add_argument("--dev", action="store_true", help="also install the check tools")
    args = parser.parse_args(argv)

    say("Process Map Studio setup")
    say("This takes about 5-10 minutes the first time. Please keep this window open.")
    say()

    step(1, "Checking Python 3.12...")
    check_python()
    step(2, "Checking Node.js...")
    npm = check_node()

    step(3, "Preparing the app's Python environment...")
    python = ensure_venv(ROOT)

    step(4, "Installing the app's Python packages...")
    requirements = "requirements-dev.txt" if args.dev else "requirements.txt"
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-q",
            "-r",
            requirements,
        ],
        BACKEND,
        "the Python packages could not be installed. Check your internet connection and "
        "run setup again.",
    )

    step(5, "Installing the app's screen components...")
    run(
        [npm, "ci", "--no-audit", "--no-fund"],
        FRONTEND,
        "the screen components could not be installed. Check your internet connection and "
        "run setup again.",
    )

    step(6, "Building the app's screens...")
    run(
        [npm, "run", "build"],
        FRONTEND,
        "the app's screens could not be built. Open Claude Code in the app folder and paste "
        "the Bug-fix prompt.",
    )

    step(7, "Preparing your private data folder and settings...")
    for item in ensure_data_and_env(ROOT):
        say(f"      created the {item}")
    say(f"      secret-check hook: {activate_hook(ROOT)}")
    if args.dev:
        say(f"      test browser for the checks: {install_test_browser(npm)}")

    say()
    say("Setup complete. You can now start Process Map Studio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
