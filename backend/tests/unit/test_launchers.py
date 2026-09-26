"""Launch helpers and double-click launchers (PRD §3.1, §3.10, §6.3 P0a)."""

from __future__ import annotations

import ast
import datetime as dt
import importlib.util
import os
import shutil
import signal
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path
from types import ModuleType

import pytest

from tests.paths import BACKEND_ROOT, FRONTEND_ROOT, REPO_ROOT, SCRIPTS_DIR

SCRIPT_FILES = sorted(SCRIPTS_DIR.glob("*.py"))
LOCAL_MODULES = {path.stem for path in SCRIPT_FILES}


def load_script(name: str) -> ModuleType:
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(f"pms_{name}", SCRIPTS_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = load_script("launcher_common")
setup_script = load_script("setup")
start_script = load_script("start")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


# --- Standard library only -------------------------------------------------------------


@pytest.mark.parametrize("path", SCRIPT_FILES, ids=lambda p: p.name)
def test_launch_helpers_import_only_the_standard_library(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    outside = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        for name in names:
            top = name.split(".")[0]
            if top not in sys.stdlib_module_names and top not in LOCAL_MODULES | {"__future__"}:
                outside.append(name)
    assert outside == [], f"{path.name} imports non-standard modules: {outside}"


# --- Version checks and settings --------------------------------------------------------


def test_python_version_rule() -> None:
    assert common.python_is_supported((3, 12, 3))
    assert not common.python_is_supported((3, 11, 9))
    assert not common.python_is_supported((3, 13, 0))


@pytest.mark.parametrize(
    ("text", "expected", "supported"),
    [
        ("v22.13.0\n", (22, 13), True),
        ("v22.22.2", (22, 22), True),
        ("v24.1.0", (24, 1), True),
        ("v22.12.0", (22, 12), False),
        ("v20.19.1", (20, 19), False),
    ],
)
def test_node_version_rule(text: str, expected: tuple[int, int], supported: bool) -> None:
    assert common.parse_node_version(text) == expected
    assert common.node_is_supported(expected) is supported


def test_unreadable_node_version() -> None:
    assert common.parse_node_version("command not found") is None


def test_read_env_file_and_port(tmp_path: Path) -> None:
    assert common.configured_port(tmp_path) == 8000
    (tmp_path / ".env").write_text("# comment\n\nAPP_PORT=8123\nOWNER_NAME='Eric'\nbad line\n")
    assert common.read_env_file(tmp_path / ".env") == {"APP_PORT": "8123", "OWNER_NAME": "Eric"}
    assert common.configured_port(tmp_path) == 8123
    (tmp_path / ".env").write_text("APP_PORT=abc\n")
    assert common.configured_port(tmp_path) == 8000


def test_port_is_free_detects_a_busy_port() -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        assert not common.port_is_free(sock.getsockname()[1])
    assert common.port_is_free(free_port())


# --- Setup ------------------------------------------------------------------------------


def test_setup_creates_data_folder_and_env_from_example(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text("ANTHROPIC_API_KEY=\nAPP_PORT=8000\n")
    created = setup_script.ensure_data_and_env(tmp_path)
    assert created == ["data folder", ".env settings file"]
    assert (tmp_path / "data").is_dir()
    assert (tmp_path / ".env").read_text() == "ANTHROPIC_API_KEY=\nAPP_PORT=8000\n"


def test_setup_never_overwrites_an_existing_env(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text("ANTHROPIC_API_KEY=\n")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=kept\n")
    (tmp_path / "data").mkdir()
    assert setup_script.ensure_data_and_env(tmp_path) == []
    assert (tmp_path / ".env").read_text() == "ANTHROPIC_API_KEY=kept\n"


def test_setup_activates_hook_only_in_a_git_repository(tmp_path: Path) -> None:
    assert "not a git repository" in setup_script.activate_hook(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert setup_script.activate_hook(tmp_path) == "switched on"
    hooks_path = subprocess.run(
        ["git", "config", "core.hooksPath"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert hooks_path.stdout.strip() == ".githooks"


def test_setup_rejects_wrong_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup_script, "python_is_supported", lambda _version: False)
    with pytest.raises(SystemExit):
        setup_script.check_python()


def test_setup_explains_missing_node(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(setup_script, "find_node", lambda: None)
    with pytest.raises(SystemExit):
        setup_script.check_node()
    assert "Node.js was not found" in capsys.readouterr().out


def test_setup_explains_old_node(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(setup_script, "find_node", lambda: ("node", "npm"))
    monkeypatch.setattr(setup_script, "node_version", lambda _node: (20, 11))
    with pytest.raises(SystemExit):
        setup_script.check_node()
    assert "Node.js 20.11 is too old" in capsys.readouterr().out


def test_readme_troubleshooting_matches_launcher_messages() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert '"Python 3.12 was not found" during setup' in readme
    assert '"Node.js was not found" during setup' in readme
    assert common.PYTHON_MISSING.startswith("Python 3.12 was not found")
    assert common.NODE_MISSING.startswith("Node.js was not found")
    assert '"Port already in use"' in readme
    assert "Setup complete. You can now start Process Map Studio." in readme
    assert "Setup complete. You can now start Process Map Studio." in (
        SCRIPTS_DIR / "setup.py"
    ).read_text(encoding="utf-8")


# --- Database backup before updates --------------------------------------------------------


def test_backup_skipped_when_there_is_no_database(tmp_path: Path) -> None:
    assert start_script.backup_database(tmp_path, dt.datetime(2026, 9, 26, 9, 30, 5)) is None
    assert not (tmp_path / "backups").exists()


def test_backup_copies_database_with_date_time_name(tmp_path: Path) -> None:
    (tmp_path / "app.db").write_bytes(b"sqlite contents")
    target = start_script.backup_database(tmp_path, dt.datetime(2026, 9, 26, 9, 30, 5))
    assert target == tmp_path / "backups" / "app-20260926-093005.db"
    assert target.read_bytes() == b"sqlite contents"
    assert (tmp_path / "app.db").read_bytes() == b"sqlite contents"


def test_update_backs_up_first_then_upgrades(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "app.db").write_bytes(b"db")
    calls: list[str] = []
    monkeypatch.setattr(start_script, "ROOT", tmp_path)
    monkeypatch.setattr(start_script, "pending_migrations", lambda _python: 1)

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command[-1])
        assert list((tmp_path / "backups").glob("app-*.db")), "backup must exist before upgrade"
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(start_script.subprocess, "run", fake_run)
    start_script.apply_database_updates(Path("python"), tmp_path)
    assert calls == ["upgrade"]


def test_no_update_means_no_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "app.db").write_bytes(b"db")
    monkeypatch.setattr(start_script, "pending_migrations", lambda _python: 0)
    start_script.apply_database_updates(Path("python"), tmp_path)
    assert not (tmp_path / "backups").exists()


def test_pending_migrations_reads_backend_answer() -> None:
    assert start_script.pending_migrations(common.venv_python(REPO_ROOT)) == 0


# --- Start script, end to end -------------------------------------------------------------


def run_start(
    *args: str, cwd: Path = REPO_ROOT, script: Path | None = None
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, str(script or SCRIPTS_DIR / "start.py"), *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def test_start_explains_when_setup_has_not_run(tmp_path: Path) -> None:
    shutil.copytree(SCRIPTS_DIR, tmp_path / "scripts")
    process = run_start("--no-browser", script=tmp_path / "scripts" / "start.py", cwd=tmp_path)
    output, _ = process.communicate(timeout=30)
    assert process.returncode == 1
    assert "The app isn't set up yet" in output


def test_start_explains_a_busy_port() -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        process = run_start("--no-browser", "--port", str(port))
        output, _ = process.communicate(timeout=30)
    assert process.returncode == 1
    assert "Port already in use" in output


@pytest.mark.skipif(os.name == "nt", reason="uses POSIX signals to stop the app")
def test_start_serves_the_placeholder_page_and_stops_cleanly() -> None:
    assert (FRONTEND_ROOT / "dist" / "index.html").is_file(), "build the frontend first"
    port = free_port()
    process = run_start("--no-browser", "--port", str(port))
    url = f"http://127.0.0.1:{port}"
    seen: list[str] = []
    try:
        # Wait for the line Eric sees in the window: the app says it is running.
        assert process.stdout is not None
        for line in process.stdout:
            seen.append(line)
            if "Close this window to stop it." in line:
                break
        assert "Process Map Studio is running at " + url + "\n" in seen, "".join(seen)
        with urllib.request.urlopen(url + "/", timeout=5) as response:
            page = response.read().decode("utf-8")
        assert "<title>Process Map Studio</title>" in page
        assert '<div id="root">' in page
        with urllib.request.urlopen(url + "/api/health", timeout=5) as response:
            assert response.status == 200
    finally:
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=30)
    assert process.returncode == 0
    assert common.port_is_free(port), "stopping must also stop the server"


# --- Double-click launchers ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "script"),
    [("Setup.command", "scripts/setup.py"), ("Start.command", "scripts/start.py")],
)
def test_mac_launchers(name: str, script: str) -> None:
    path = REPO_ROOT / name
    text = path.read_bytes().decode("utf-8")
    assert text.startswith("#!/bin/bash\n") and "\r\n" not in text
    assert script in text and "python3.12" in text
    assert path.stat().st_mode & 0o111, f"{name} must be executable"


@pytest.mark.parametrize(
    ("name", "script"),
    [("setup.bat", r"scripts\setup.py"), ("start.bat", r"scripts\start.py")],
)
def test_windows_launchers(name: str, script: str) -> None:
    text = (REPO_ROOT / name).read_bytes().decode("utf-8")
    assert text.startswith("@echo off\r\n")
    assert text.count("\n") == text.count("\r\n"), f"{name} needs Windows line endings"
    assert script in text and "py -3.12" in text


@pytest.mark.parametrize("name", ["Setup.command", "Start.command", "run_checks.sh"])
def test_executable_bit_is_recorded_in_git(name: str) -> None:
    result = subprocess.run(
        ["git", "ls-files", "-s", name],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if not result.stdout:
        pytest.skip(f"{name} not tracked yet")
    assert result.stdout.startswith("100755"), f"{name} must be committed as executable"


def test_manage_reports_no_pending_updates_yet() -> None:
    result = subprocess.run(
        [str(common.venv_python(REPO_ROOT)), "-m", "app.manage", "pending-migrations"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "0"


def test_start_never_uses_a_proxy_for_the_local_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """A proxy set on Eric's computer must not stop the launcher reaching the local app."""
    import http.server
    import threading

    class Health(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Health)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
        monkeypatch.setenv("no_proxy", "")
        monkeypatch.setenv("NO_PROXY", "")
        url = f"http://127.0.0.1:{server.server_address[1]}/api/health"
        assert not any(
            type(h).__name__ == "ProxyHandler" for h in start_script.LOCAL_OPENER.handlers
        )
        with start_script.LOCAL_OPENER.open(url, timeout=5) as response:
            assert response.read() == b"ok"
    finally:
        server.shutdown()
        server.server_close()


def test_dev_setup_skips_the_test_browser_when_one_is_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PMS_CHROMIUM_PATH", "/opt/some/chromium")
    monkeypatch.setattr(setup_script.subprocess, "run", lambda *a, **k: pytest.fail("no download"))
    assert "nothing to do" in setup_script.install_test_browser("npm")


def test_dev_setup_installs_the_test_browser_otherwise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PMS_CHROMIUM_PATH", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", raising=False)
    seen: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(setup_script.subprocess, "run", fake_run)
    assert setup_script.install_test_browser("npm") == "installed"
    assert seen == [["npm", "exec", "--", "playwright", "install", "chromium"]]
