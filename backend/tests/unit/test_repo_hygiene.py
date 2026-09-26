"""Repository hygiene (PRD §3.10, §6.2 item 10): secret check, .gitignore, pre-commit hook."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.paths import REPO_ROOT, SCRIPTS_DIR

# Built by concatenation so this test file itself never contains a key-shaped string.
FAKE_KEY = "sk-" + "ant-" + "api03-" + "X" * 40


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A throwaway git repository with the real secret check and pre-commit hook installed."""
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "scripts").mkdir()
    shutil.copy(SCRIPTS_DIR / "check_secrets.py", tmp_path / "scripts" / "check_secrets.py")
    shutil.copytree(REPO_ROOT / ".githooks", tmp_path / ".githooks")
    shutil.copy(REPO_ROOT / ".gitignore", tmp_path / ".gitignore")
    git(tmp_path, "config", "core.hooksPath", ".githooks")
    return tmp_path


def run_check(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "check_secrets.py"), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_clean_staged_file_passes(repo: Path) -> None:
    (repo / "notes.txt").write_text("Nothing secret here. Keys start with sk-ant- in general.\n")
    git(repo, "add", "notes.txt")
    result = run_check(repo)
    assert result.returncode == 0, result.stdout
    assert "PASS" in result.stdout


def test_planted_fake_key_is_blocked(repo: Path) -> None:
    (repo / "config.py").write_text(f'KEY = "{FAKE_KEY}"\n')
    git(repo, "add", "config.py")
    result = run_check(repo)
    assert result.returncode == 1
    assert "config.py line 1: this looks like an API key" in result.stdout
    assert FAKE_KEY not in result.stdout, "the check must never print the key itself"


def test_env_file_is_blocked_even_when_forced(repo: Path) -> None:
    (repo / ".env").write_text("ANTHROPIC_API_KEY=\n")
    git(repo, "add", "-f", ".env")
    result = run_check(repo)
    assert result.returncode == 1
    assert ".env: the .env file holds your API key" in result.stdout


def test_env_example_is_allowed(repo: Path) -> None:
    (repo / ".env.example").write_text("ANTHROPIC_API_KEY=\n")
    git(repo, "add", ".env.example")
    assert run_check(repo).returncode == 0


def test_data_folder_is_blocked_even_when_forced(repo: Path) -> None:
    (repo / "data").mkdir()
    (repo / "data" / "app.db").write_bytes(b"\0sqlite")
    git(repo, "add", "-f", "data/app.db")
    result = run_check(repo)
    assert result.returncode == 1
    assert "data/app.db: files in the data folder" in result.stdout


def test_all_mode_scans_tracked_files_and_history(repo: Path) -> None:
    (repo / "data").mkdir()
    (repo / "data" / "old.txt").write_text("confidential")
    git(repo, "add", "-f", "data/old.txt")
    git(repo, "commit", "-q", "--no-verify", "-m", "slipped through")
    git(repo, "rm", "-q", "--cached", "data/old.txt")
    git(repo, "commit", "-q", "--no-verify", "-m", "removed")
    result = run_check(repo, "--all")
    assert result.returncode == 1
    assert "data/old.txt (in an earlier commit)" in result.stdout


def test_pre_commit_hook_blocks_commit_with_key(repo: Path) -> None:
    (repo / "leak.md").write_text(f"my key is {FAKE_KEY}\n")
    git(repo, "add", "leak.md")
    result = git(repo, "commit", "-m", "try to leak")
    assert result.returncode != 0
    assert "FAIL secret check" in result.stdout + result.stderr
    assert git(repo, "rev-parse", "--verify", "HEAD").returncode != 0, "nothing was committed"


def test_pre_commit_hook_allows_clean_commit(repo: Path) -> None:
    (repo / "ok.md").write_text("hello\n")
    git(repo, "add", "ok.md")
    result = git(repo, "commit", "-q", "-m", "clean")
    assert result.returncode == 0, result.stdout + result.stderr


def test_not_a_repository_reports_plainly(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "check_secrets.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "not a git repository" in result.stdout


@pytest.mark.parametrize(
    "path",
    [".env", ".env.local", "data/app.db", "data/sources/interview.txt", "data/backups/a.db"],
)
def test_gitignore_hides_secrets_and_data(path: str) -> None:
    result = git(REPO_ROOT, "check-ignore", "--no-index", "-q", path)
    assert result.returncode == 0, f"{path} must be ignored by git"


def test_gitignore_keeps_env_example() -> None:
    assert git(REPO_ROOT, "check-ignore", "--no-index", "-q", ".env.example").returncode == 1


def test_pre_commit_hook_is_executable_and_calls_the_check() -> None:
    hook = REPO_ROOT / ".githooks" / "pre-commit"
    assert hook.stat().st_mode & 0o111, "hook must be executable"
    assert "check_secrets.py" in hook.read_text()


def test_this_repository_is_clean() -> None:
    result = run_check(REPO_ROOT, "--all")
    assert result.returncode == 0, result.stdout
