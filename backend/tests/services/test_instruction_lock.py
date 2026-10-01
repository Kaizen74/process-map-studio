"""The AI's instructions can't drift silently (anti-drift guardrail, PRD §3.8, Appendix E).

Every file in `app/prompts/` (the stage prompts and the interview question bank) is pinned in
`instruction_lock.json` to its version and a fingerprint of its wording. The mock answers are keyed
by the data sent, not by the prompt's wording, so without this lock a prompt could be reworded and
every offline test would still pass while the real model received different instructions.

- Changing a file's wording without giving it a new version fails here.
- A new version fails here until its fingerprint is recorded: run the tests with
  PMS_UPDATE_LOCK=1 (which records only files whose version changed, never a rewording under the
  old version) and log the change and its reason in DECISIONS.md.
- The stage prompts and exports also stay free of blaming words (PRD §3.12.9, rule 4).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from app.services.prompts import PROMPTS_DIR, instruction_version
from app.services.wording import banned_words

LOCK = Path(__file__).resolve().parent / "instruction_lock.json"
REPO = Path(__file__).resolve().parents[3]


def fingerprint(path: Path) -> str:
    """SHA-256 of the file's text with Windows line endings made plain (a Windows checkout must
    give the same fingerprint)."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def instruction_files() -> list[Path]:
    return sorted(p for p in PROMPTS_DIR.iterdir() if p.suffix in (".md", ".json"))


def current() -> dict[str, dict[str, str]]:
    return {
        p.name: {"version": instruction_version(p) or "", "sha256": fingerprint(p)}
        for p in instruction_files()
    }


def recorded() -> dict[str, dict[str, str]]:
    return dict(json.loads(LOCK.read_text(encoding="utf-8")))


def test_update_mode_records_only_new_versions() -> None:
    if os.environ.get("PMS_UPDATE_LOCK") != "1":
        pytest.skip("only with PMS_UPDATE_LOCK=1")  # the normal run checks, never writes
    old = recorded() if LOCK.exists() else {}
    new = current()
    for name, entry in new.items():
        before = old.get(name)
        if before and before["version"] == entry["version"] and before["sha256"] != entry["sha256"]:
            new[name] = before  # a rewording under the old version is never recorded
    LOCK.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_every_instruction_file_has_a_version() -> None:
    for path in instruction_files():
        assert instruction_version(path), f"{path.name} has no version"


def test_every_instruction_file_is_locked_and_nothing_else() -> None:
    assert set(recorded()) == {p.name for p in instruction_files()}, (
        "a prompt was added or removed: record it with PMS_UPDATE_LOCK=1 and log it in DECISIONS.md"
    )


@pytest.mark.parametrize("path", instruction_files(), ids=lambda p: p.name)
def test_instructions_match_their_recorded_version(path: Path) -> None:
    lock = recorded()[path.name]
    version = instruction_version(path)
    assert version == lock["version"], (
        f"{path.name} is now version {version} (recorded: {lock['version']}): record the new "
        "fingerprint with PMS_UPDATE_LOCK=1 and log the change and its reason in DECISIONS.md"
    )
    assert fingerprint(path) == lock["sha256"], (
        f"{path.name} was reworded but is still version {version}: give it a new version, so "
        "every AI call records which wording it used, then record it with PMS_UPDATE_LOCK=1"
    )


def test_the_lock_notices_a_rewording(tmp_path: Path) -> None:
    """The guardrail itself: one changed word gives a different fingerprint, a Windows line ending
    does not."""
    original = PROMPTS_DIR / "S1_extract_interview.md"
    text = original.read_text(encoding="utf-8")
    reworded = tmp_path / "reworded.md"
    reworded.write_text(text.replace("exactly", "roughly", 1), encoding="utf-8")
    windows = tmp_path / "windows.md"
    windows.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert fingerprint(reworded) != fingerprint(original)
    assert fingerprint(windows) == fingerprint(original)


def test_no_blaming_words_in_prompts_screens_or_exports() -> None:
    """PRD §3.12.9 rule 4 on everything the app says or asks the model to say."""
    folders = [REPO / "backend" / "app", REPO / "frontend" / "src"]
    suffixes = {".md", ".json", ".py", ".ts", ".tsx", ".css", ".html"}
    checked, hits = 0, []
    for folder in folders:
        for path in folder.rglob("*"):
            if path.suffix not in suffixes or path.name == "wording.py":  # the list itself
                continue
            checked += 1
            if found := banned_words(path.read_text(encoding="utf-8")):
                hits.append(f"{path.relative_to(REPO)}: {', '.join(found)}")
    assert checked > 100
    assert hits == []
