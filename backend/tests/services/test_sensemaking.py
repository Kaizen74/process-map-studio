"""Marker pre-tagging and account-type cues (PRD §3.12.3, §3.12.10 Step B; Appendix A.8, A.9).
Run on the illustrative A.1 transcript as the PRD gives it."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.domain.result import Err, Ok
from app.domain.sensemaking import Lexicon
from app.services import prompts, sensemaking

PRD = Path(__file__).resolve().parents[3] / "PRD_ProcessMapStudio.md"


def appendix_a1() -> list[str]:
    """The A.1 transcript lines exactly as the PRD (the single source of truth) gives them."""
    text = PRD.read_text(encoding="utf-8")
    block = text.split("**A.1 `interview_transcript.txt`**", 1)[1].split("```", 2)[1]
    return [line for line in block.splitlines() if line.startswith("[")]


def lexicon() -> Lexicon:
    result = sensemaking.load_lexicon()
    assert isinstance(result, Ok)
    return result.value


def turn(time: str) -> str:
    """The words of the A.1 turn at `time` (speaker label removed)."""
    for line in appendix_a1():
        if line.startswith(f"[{time}]"):
            return re.sub(r"^\[\d\d:\d\d\] [^:]+: ", "", line)
    raise AssertionError(time)


def tags(time: str) -> set[tuple[str, str]]:
    return {(t.family, t.phrase.lower()) for t in sensemaking.pretag(turn(time), lexicon())}


def test_the_lexicon_is_versioned_and_stamped_with_the_codebook_version() -> None:
    lex = lexicon()
    versions = prompts.instruction_versions()
    assert lex.version == versions["marker_lexicon"] == "1"
    assert lex.codebook_version == versions["codebook"] == "1"
    # Every marker family of the §3.12.10 table is there.
    assert {
        "sequence", "handoff", "decision", "approval", "wait", "check", "rework", "variation",
        "official", "lived", "work_type_clear", "work_type_complex", "work_type_chaotic",
        "heuristic", "experience", "sme_term",
    } <= set(lex.families)  # fmt: skip


@pytest.mark.parametrize(
    ("time", "expected"),
    [
        # A.9 marker tags.
        ("06:40", {("sequence", "first thing")}),
        ("14:05", {("sequence", "then"), ("check", "check"), ("work_type_clear", "checklist")}),
        ("21:50", {("handoff", "sends back"), ("wait", "wait")}),
        (
            "22:30",
            {
                ("official", "officially"),
                ("lived", "what actually happens"),
                ("variation", "on a busy wave"),
            },
        ),
        (
            "29:48",
            {("work_type_complex", "no fixed answer"), ("work_type_complex", "read the situation")},
        ),
        ("24:10", {("heuristic", "rule of thumb"), ("experience", "learned it after")}),
        ("24:46", {("work_type_chaotic", "firefighting")}),
        ("31:10", {("sequence", "then"), ("sequence", "around t-")}),
    ],
)
def test_a9_marker_tags_on_the_fixture_transcript(
    time: str, expected: set[tuple[str, str]]
) -> None:
    assert expected <= tags(time)


def test_the_longest_phrase_wins_and_only_whole_words_match() -> None:
    lex = lexicon()
    found = sensemaking.pretag("First thing, wait for it. A specific uncheck.", lex)
    phrases = [(t.family, t.phrase) for t in found]
    assert ("sequence", "First thing") in phrases and ("sequence", "First") not in phrases
    assert ("wait", "wait for") in phrases and ("wait", "wait") not in phrases
    # "if" inside "specific" and "check" inside "uncheck" are not markers.
    assert not any(f in ("decision", "check") for f, _ in phrases)
    # Positions point at the words found.
    text = "Then I re-plan."
    [then, replan] = sensemaking.pretag(text, lex)
    assert text[then.start : then.end] == "Then" and text[replan.start : replan.end] == "re-plan"


def test_a8_account_cues_per_sentence() -> None:
    first, second = sensemaking.pretag_account_type(turn("22:30"), lexicon())
    assert (first.account_type, first.cue) == ("official", "Officially")
    assert (second.account_type, second.cue) == ("lived", "What actually happens")
    assert second.text.endswith("otherwise we'd miss the slot.")
    # No cue in the passage: unclear until the model confirms a lived or official reading with a
    # quoted cue (A.8 expects 21:50 to end up lived; B3).
    assert {s.account_type for s in sensemaking.pretag_account_type(turn("21:50"), lexicon())} == {
        "unclear"
    }


def test_a_damaged_lexicon_is_a_plain_error(tmp_path: Path) -> None:
    broken = tmp_path / "marker_lexicon.json"
    broken.write_text('{"version": "1"}', encoding="utf-8")
    result = sensemaking.load_lexicon(broken)
    assert isinstance(result, Err) and result.message == sensemaking.LEXICON_DAMAGED
    assert isinstance(sensemaking.load_lexicon(tmp_path / "missing.json"), Err)


@pytest.mark.parametrize("name", sorted(prompts.CODEBOOK_STAGES - {"S3c_worktype"}))
def test_the_map_building_prompts_carry_the_codebook(name: str) -> None:
    result = prompts.load_prompt(name)
    assert isinstance(result, Ok)
    text = result.value.text
    assert '<codebook version="1">' in text and text.rstrip().endswith("</codebook>")
    assert "Tier 1 — invariants" in text and "Sequence evidence, strongest to weakest" in text
    assert result.value.version == prompts.instruction_versions()[name]  # the prompt's own


@pytest.mark.parametrize("name", ["S3_calibrate", "S3b_verify", "S5_questions", "R_repair"])
def test_other_prompts_do_not(name: str) -> None:
    result = prompts.load_prompt(name)
    assert isinstance(result, Ok) and "<codebook" not in result.value.text


def test_a_missing_codebook_is_a_plain_error(tmp_path: Path) -> None:
    source = prompts.PROMPTS_DIR / "S4_assemble.md"
    (tmp_path / "S4_assemble.md").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    result = prompts.load_prompt("S4_assemble", tmp_path)
    assert isinstance(result, Err) and result.details == {"prompt": "codebook"}
