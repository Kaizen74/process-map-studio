"""Transcript parsing (PRD §3.7 S0, §6.3 P2): every format yields the same speakers and times."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from app.domain.models import ParsedDocument, ParsedSegment
from app.domain.result import Err, ErrorKind, Ok, Result
from app.services import parsing
from tests.paths import BACKEND_ROOT

FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "engagement_load_control"

# PRD Appendix A.1 (v1.10: sixteen turns, four of them the interviewer's): (anchor, speaker).
EXPECTED = [
    ("06:38", "Interviewer"),
    ("06:40", "Priya Nair"),
    ("07:55", "Priya Nair"),
    ("14:05", "Priya Nair"),
    ("16:22", "Priya Nair"),
    ("21:45", "Interviewer"),
    ("21:50", "Priya Nair"),
    ("22:30", "Priya Nair"),
    ("24:10", "Priya Nair"),
    ("24:40", "Interviewer"),
    ("24:46", "Priya Nair"),
    ("27:15", "Priya Nair"),
    ("29:02", "Priya Nair"),
    ("29:40", "Interviewer"),
    ("29:48", "Priya Nair"),
    ("31:10", "Priya Nair"),
]


def _docx(path: Path) -> Result[ParsedDocument]:
    match parsing.parse_docx(path):
        case Ok(value=document):
            return Ok(ParsedDocument(segments=parsing.detect_speakers(document.segments)))
        case Err() as err:
            return err


def _pdf(path: Path) -> Result[ParsedDocument]:
    match parsing.parse_pdf_text(path):
        case Ok(value=document):
            return Ok(ParsedDocument(segments=parsing.detect_speakers(document.segments)))
        case Err() as err:
            return err


READERS: dict[str, Callable[[Path], Result[ParsedDocument]]] = {
    "txt": parsing.parse_transcript_text,
    "vtt": parsing.parse_vtt,
    "srt": parsing.parse_srt,
    "docx": _docx,
    "pdf": _pdf,
}


def turns(fmt: str) -> list[ParsedSegment]:
    result = READERS[fmt](FIXTURES / f"interview_transcript.{fmt}")
    assert isinstance(result, Ok), result
    return [s for s in result.value.segments if s.speaker_label]


def anchor(segment: ParsedSegment) -> str:
    return parsing.segment_anchor(
        fmt="txt",
        seq=segment.seq,
        page=segment.page,
        section="",
        text="",
        start_ms=segment.start_ms,
    )


@pytest.mark.parametrize("fmt", list(READERS))
def test_every_format_yields_the_a1_speakers_and_timestamps(fmt: str) -> None:
    found = turns(fmt)
    assert [(anchor(s), s.speaker_label) for s in found] == EXPECTED


@pytest.mark.parametrize("fmt", list(READERS))
def test_turn_text_is_what_was_said_without_the_speaker_prefix(fmt: str) -> None:
    found = {anchor(s): s.text.replace("\u2019", "'") for s in turns(fmt)}
    assert found["06:40"] == (
        "First thing, I build the preliminary load plan off the booked figures, usually around "
        "T-120. Takes me about twenty minutes."
    )
    assert found["31:10"] == "Then I issue the final load sheet, around T-15."
    assert all("Priya Nair:" not in text for text in found.values())


def test_times_end_where_the_next_turn_starts() -> None:
    found = turns("txt")
    assert (found[0].start_ms, found[0].end_ms) == (398_000, 400_000)
    assert found[-1].end_ms is None


def test_vtt_and_srt_keep_their_cue_end_times() -> None:
    assert turns("vtt")[-1].end_ms == 1_875_000
    assert turns("srt")[1].end_ms == 475_000


def test_pdf_turns_rejoin_wrapped_lines_and_page_breaks() -> None:
    found = {anchor(s): s for s in turns("pdf")}
    # v1.10 A.1 (sixteen turns): the 22:30 turn starts on page 1 and finishes on page 2.
    split = found["22:30"]
    assert split.page == 1
    assert split.text.replace("\u2019", "'") == (
        "Officially the ramp should send the report within ten minutes. What actually happens on "
        "a busy wave is I walk down and read it off their sheet, otherwise we'd miss the slot."
    )
    assert found["24:10"].page == 2


def test_word_headings_are_not_speakers() -> None:
    result = _docx(FIXTURES / "interview_transcript.docx")
    assert isinstance(result, Ok)
    first = result.value.segments[0]
    assert (first.speaker_label, first.text) == (
        "",
        "Interview: load control (illustrative fixture)",
    )


def write(tmp_path: Path, name: str, content: str | bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return path


def test_plain_speaker_lines_without_times(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "t.txt",
        "Interviewer: What happens first?\nSME 2: I check the plan.\n  It takes a while.\n\n"
        "Interviewer: Thanks.\n",
    )
    result = parsing.parse_transcript_text(path)
    assert isinstance(result, Ok)
    assert [(s.speaker_label, s.text, s.start_ms) for s in result.value.segments] == [
        ("Interviewer", "What happens first?", None),
        ("SME 2", "I check the plan. It takes a while.", None),
        ("Interviewer", "Thanks.", None),
    ]


# An Otter.ai text export (illustrative, fictional names): the speaker and time on one line, the
# words on the lines below, a blank line between turns and a "Transcribed by" footer.
OTTER = (
    "Speaker 1  0:06  \nWalk me through the last plan you built.\n\n"
    "Alex Tan  0:12  \nFirst I build the plan off the booked figures.\n"
    "It takes about twenty minutes.\nNote: the lead signs it off.\n\n"
    "Speaker 2  0:40\n\n"
    "Unknown Speaker  1:02:03\nThanks, we meet again at 10:30.\n\n"
    "Transcribed by https://otter.ai\n"
)


def test_otter_exports_are_split_into_speaker_turns(tmp_path: Path) -> None:
    result = parsing.parse_transcript_text(write(tmp_path, "otter.txt", OTTER))
    assert isinstance(result, Ok)
    assert [(s.speaker_label, s.start_ms, s.end_ms, s.text) for s in result.value.segments] == [
        ("Speaker 1", 6_000, 12_000, "Walk me through the last plan you built."),
        (
            "Alex Tan",
            12_000,
            3_723_000,
            "First I build the plan off the booked figures. It takes about twenty minutes. "
            "Note: the lead signs it off.",
        ),
        ("Unknown Speaker", 3_723_000, None, "Thanks, we meet again at 10:30."),
    ]


def test_hour_timestamps_and_times_without_a_speaker(tmp_path: Path) -> None:
    path = write(tmp_path, "t.txt", "[1:02:03] Lead: Start.\n[1:02:09] And more.\n")
    result = parsing.parse_transcript_text(path)
    assert isinstance(result, Ok)
    assert [(s.speaker_label, s.start_ms, s.text) for s in result.value.segments] == [
        ("Lead", 3_723_000, "Start."),
        ("Lead", 3_729_000, "And more."),
    ]


def test_text_before_any_speaker_is_kept_without_one(tmp_path: Path) -> None:
    path = write(tmp_path, "t.txt", "Recorded on site.\nInterviewer: Hello.\n")
    result = parsing.parse_transcript_text(path)
    assert isinstance(result, Ok)
    assert [(s.speaker_label, s.text) for s in result.value.segments] == [
        ("", "Recorded on site."),
        ("Interviewer", "Hello."),
    ]


def test_windows_encoded_and_bom_files_are_read(tmp_path: Path) -> None:
    latin = write(tmp_path, "a.txt", "Interviewer: café\n".encode("cp1252"))
    bom = write(tmp_path, "b.txt", "﻿Interviewer: Hello\n".encode())
    for path, text in ((latin, "café"), (bom, "Hello")):
        result = parsing.parse_transcript_text(path)
        assert isinstance(result, Ok)
        assert (result.value.segments[0].speaker_label, result.value.segments[0].text) == (
            "Interviewer",
            text,
        )


def test_vtt_cues_without_voice_tags_use_prefixes_and_continue_speakers(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "t.vtt",
        "WEBVTT\n\n1\n00:00:01.000 --> 00:00:04.500\nInterviewer: <i>Hello</i> there\n\n"
        "00:00:05.000 --> 00:00:06.000\nstill talking\n\n"
        "00:00:07.000 --> 00:00:09.000\n<v.loud Sam Lee>Hi</v>\n",
    )
    result = parsing.parse_vtt(path)
    assert isinstance(result, Ok)
    assert [(s.speaker_label, s.text, s.start_ms, s.end_ms) for s in result.value.segments] == [
        ("Interviewer", "Hello there", 1_000, 4_500),
        ("Interviewer", "still talking", 5_000, 6_000),
        ("Sam Lee", "Hi", 7_000, 9_000),
    ]


def test_a_vtt_file_must_start_with_webvtt(tmp_path: Path) -> None:
    result = parsing.parse_vtt(write(tmp_path, "t.vtt", "00:00:01.000 --> 00:00:02.000\nHi\n"))
    assert isinstance(result, Err) and result.kind == ErrorKind.VALIDATION


def test_srt_with_windows_line_endings(tmp_path: Path) -> None:
    content = (
        "1\r\n00:00:01,000 --> 00:00:02,000\r\nLead: One\r\n\r\n"
        "2\r\n00:00:03,000 --> 00:00:04,000\r\nTwo\r\n"
    )
    result = parsing.parse_srt(write(tmp_path, "t.srt", content))
    assert isinstance(result, Ok)
    assert [(s.speaker_label, s.text) for s in result.value.segments] == [
        ("Lead", "One"),
        ("Lead", "Two"),
    ]


def test_missing_file_is_a_plain_error(tmp_path: Path) -> None:
    result = parsing.parse_transcript_text(tmp_path / "gone.txt")
    assert isinstance(result, Err) and result.kind == ErrorKind.IO


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Priya Nair", True),
        ("Priya", True),
        ("Jean-Luc Picard", True),
        ("Dr. Tan", True),
        ("Interviewer", False),
        ("Speaker 1", False),
        ("Load controller", False),
        ("Ramp Supervisor", False),
        ("SME", False),
        ("Captain", False),
        ("priya nair", False),
        ("A Very Long Name Indeed", False),
        ("", False),
    ],
)
def test_name_like_labels(label: str, expected: bool) -> None:
    assert parsing.looks_like_name(label) is expected


def test_a_known_role_is_never_a_name() -> None:
    assert parsing.looks_like_name("Tower", frozenset({"tower"})) is False
    assert parsing.looks_like_name("Tower") is True


def test_plain_text_documents_are_read_by_paragraph(tmp_path: Path) -> None:
    path = write(
        tmp_path, "notes.txt", "Note: first line\ncontinues here.\n\n\nSecond  paragraph.\r\n"
    )
    result = parsing.parse_text_document(path)
    assert isinstance(result, Ok)
    assert [(s.seq, s.text, s.speaker_label) for s in result.value.segments] == [
        (1, "Note: first line continues here.", ""),
        (2, "Second paragraph.", ""),
    ]
    assert isinstance(parsing.parse_text_document(tmp_path / "gone.txt"), Err)
