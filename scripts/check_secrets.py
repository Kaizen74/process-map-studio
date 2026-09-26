"""Secret check: blocks API keys, the .env file and the data/ folder from reaching git.

PRD constraint 12 and section 3.10. Standard library only, so it runs before setup.

Usage:
  python scripts/check_secrets.py            # staged files only (used by the pre-commit hook)
  python scripts/check_secrets.py --all      # tracked and staged files, plus names in history

Exit codes: 0 = clean, 1 = blocked, 2 = could not run (for example, not a git repository).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Anthropic keys start with "sk-ant-" (for example sk-ant-api03-..., sk-ant-admin01-...).
# The pattern needs at least 16 key characters after the prefix, so prose that merely
# mentions the prefix is not flagged.
KEY_PATTERN = r"sk-ant-[A-Za-z0-9_-]{16,}"
KEY_REGEX = re.compile(KEY_PATTERN)

ALLOWED_ENV_FILES = {".env.example"}


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def is_forbidden_path(path: str) -> str | None:
    """Return a plain-language reason if this path must never be committed, else None."""
    parts = Path(path).parts
    if not parts:
        return None
    if parts[0] == "data":
        return "files in the data folder hold your confidential work and never go to GitHub"
    name = parts[-1]
    if name in ALLOWED_ENV_FILES:
        return None
    if name == ".env" or name.startswith(".env."):
        return "the .env file holds your API key and never goes to GitHub"
    return None


def find_key_hits(text: str) -> list[int]:
    """Return 1-based line numbers containing something that looks like an API key."""
    return [n for n, line in enumerate(text.splitlines(), start=1) if KEY_REGEX.search(line)]


def staged_paths(repo: Path) -> list[str]:
    result = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"], repo)
    return [p for p in result.stdout.split("\0") if p]


def tracked_paths(repo: Path) -> list[str]:
    result = run_git(["ls-files", "-z"], repo)
    return [p for p in result.stdout.split("\0") if p]


def history_paths(repo: Path) -> list[str]:
    result = run_git(["log", "--all", "--name-only", "--format=", "-z"], repo)
    names: set[str] = set()
    for chunk in result.stdout.split("\0"):
        for line in chunk.splitlines():
            if line.strip():
                names.add(line.strip())
    return sorted(names)


def index_content(repo: Path, path: str) -> str | None:
    """Read the staged (index) version of a file; None if it is binary or unreadable."""
    result = subprocess.run(["git", "show", f":{path}"], cwd=repo, capture_output=True, check=False)
    if result.returncode != 0:
        return None
    data = result.stdout
    if b"\0" in data[:8000]:
        return None
    return data.decode("utf-8", errors="replace")


def check(repo: Path, scan_all: bool) -> list[str]:
    problems: list[str] = []
    paths = staged_paths(repo)
    if scan_all:
        paths = sorted(set(paths) | set(tracked_paths(repo)))

    for path in paths:
        reason = is_forbidden_path(path)
        if reason:
            problems.append(f"{path}: {reason}.")
            continue
        text = index_content(repo, path)
        if text is None:
            continue
        for line_no in find_key_hits(text):
            problems.append(f"{path} line {line_no}: this looks like an API key.")

    if scan_all:
        for path in history_paths(repo):
            reason = is_forbidden_path(path)
            if reason:
                problems.append(f"{path} (in an earlier commit): {reason}.")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="scan every tracked file too")
    args = parser.parse_args(argv)

    top = run_git(["rev-parse", "--show-toplevel"], Path.cwd())
    if top.returncode != 0:
        print("FAIL secret check: this folder is not a git repository, so it cannot be checked.")
        return 2
    repo = Path(top.stdout.strip())

    problems = check(repo, scan_all=args.all)
    if problems:
        print("FAIL secret check: this commit was blocked to keep your key and data private.")
        for problem in problems:
            print(f"  - {problem}")
        print(
            "Remove these files from the commit (they stay safely on this computer) and try again."
        )
        return 1
    print("PASS secret check: no API keys, .env file or data folder in git.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
