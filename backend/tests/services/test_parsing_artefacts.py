"""Parsing working spreadsheets (.xlsx, .csv) and email threads (.eml) (P10b R11; PRD §3.2
`parsing`, criterion 92; API_CONTRACT.md → Sources)."""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from app.domain.models import ParsedDocument
from app.domain.result import Err, ErrorKind, Ok, Result
from app.services import parsing
from tests import artefacts


def _ok(result: Result[ParsedDocument]) -> ParsedDocument:
    assert isinstance(result, Ok), result
    return result.value


def _rows(document: ParsedDocument, fmt: str) -> list[tuple[str, str, str, str]]:
    return [
        (
            parsing.segment_anchor(fmt=fmt, seq=s.seq, page=s.page, section=s.section, text=s.text),
            s.section,
            s.speaker_label,
            s.text,
        )
        for s in document.segments
    ]


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_xlsx_rows_read_with_their_headers_and_sheet_cell_anchors(tmp_path: Path) -> None:
    document = _ok(parsing.parse_xlsx(_write(tmp_path, "tracker.xlsx", artefacts.make_xlsx())))
    assert _rows(document, "xlsx") == [
        ("Plan!A1", "Plan", "", artefacts.SHEET_TITLE),  # above the header row: as it is
        ("Plan!A3", "Plan", "", "Flight | Step | Owner | Minutes | Date"),
        ("Plan!A4", "Plan", "", "Flight: SQ 221 | Step: Draft load plan | Owner: Load controller "
                                "| Minutes: 20 | Date: 2026-03-02"),
        ("Plan!A5", "Plan", "", "Flight: SQ 221 | Step: Weight check | Owner: Ramp | Minutes: 12.5 "
                                "| Date: 2026-03-02 09:14"),
        ("'Shift log'!A1", "Shift log", "", "Shift | Note"),
        ("'Shift log'!A2", "Shift log", "", "Shift: Night | Note: Plan revised twice; captain "
                                            "called LC | extra"),  # under no header: value only
    ]  # fmt: skip
    assert [s.seq for s in document.segments] == [1, 2, 3, 4, 5, 6]
    assert document.hidden_names == []


def test_sheet_names_are_quoted_as_excel_writes_them() -> None:
    assert parsing.sheet_ref("Plan") == "Plan"
    assert parsing.sheet_ref("Shift log") == "'Shift log'"
    assert parsing.sheet_ref("Ops' notes") == "'Ops'' notes'"
    assert parsing.sheet_ref("2026") == "'2026'"


def test_csv_reads_as_one_sheet_anchored_by_record(tmp_path: Path) -> None:
    document = _ok(parsing.parse_csv(_write(tmp_path, "tracker.csv", artefacts.CSV)))
    assert _rows(document, "csv") == [
        ("row 1", "", "", "Flight | Step | Minutes"),
        ("row 2", "", "", "Flight: SQ 221 | Step: Draft load plan | Minutes: 20"),
        ("row 4", "", "", "Flight: SQ 222 | Step: Weight check; ramp | Minutes: 12"),
    ]


def test_csv_in_windows_1252_is_read(tmp_path: Path) -> None:
    data = b"Step,Note\nWeigh bags,Caf\xe9 \x96 gate 4\n"  # e acute and an en dash in Windows-1252
    document = _ok(parsing.parse_csv(_write(tmp_path, "notes.csv", data)))
    assert document.segments[1].text == "Step: Weigh bags | Note: Caf\u00e9 \u2013 gate 4"


@pytest.mark.parametrize("name", ["empty.xlsx", "empty.csv"])
def test_a_spreadsheet_without_filled_cells_is_refused(tmp_path: Path, name: str) -> None:
    if name.endswith(".xlsx"):
        book = Workbook()
        path = tmp_path / name
        book.save(path)
        result = parsing.parse_xlsx(path)
    else:
        result = parsing.parse_csv(_write(tmp_path, name, b",,\n\n"))
    assert isinstance(result, Err)
    assert (result.kind, result.message) == (ErrorKind.VALIDATION, parsing.NO_CELLS)


def test_more_than_5000_filled_rows_is_refused_with_a_pointer_to_system_records(
    tmp_path: Path,
) -> None:
    lines = ["Case,Activity"] + [f"C{n},Opened" for n in range(parsing.MAX_SHEET_ROWS)]
    result = parsing.parse_csv(_write(tmp_path, "export.csv", "\n".join(lines).encode()))
    assert isinstance(result, Err)
    assert (result.kind, result.message) == (ErrorKind.VALIDATION, parsing.TOO_MANY_ROWS)
    assert "System records" in parsing.TOO_MANY_ROWS
    lines = lines[: parsing.MAX_SHEET_ROWS]  # exactly 5,000 rows is accepted
    document = _ok(parsing.parse_csv(_write(tmp_path, "export.csv", "\n".join(lines).encode())))
    assert len(document.segments) == parsing.MAX_SHEET_ROWS


def test_a_damaged_spreadsheet_is_a_plain_error(tmp_path: Path) -> None:
    result = parsing.parse_xlsx(_write(tmp_path, "broken.xlsx", b"not a zip file"))
    assert isinstance(result, Err)
    assert (result.kind, result.message) == (ErrorKind.IO, "The spreadsheet could not be opened.")


def test_cell_values_are_written_plainly() -> None:
    from datetime import date, datetime, time

    assert parsing._cell_text(12.0) == "12"
    assert parsing._cell_text(0.1 + 0.2) == "0.3"
    assert parsing._cell_text(True) == "TRUE"
    assert parsing._cell_text(datetime(2026, 3, 2)) == "2026-03-02"
    assert parsing._cell_text(date(2026, 3, 2)) == "2026-03-02"
    assert parsing._cell_text(time(9, 5)) == "09:05"
    assert parsing._cell_text("  two\tspaces ") == "two spaces"
    assert parsing._cell_text(None) == ""


def test_email_thread_headers_senders_quotes_and_attached_email(tmp_path: Path) -> None:
    document = _ok(parsing.parse_eml(_write(tmp_path, "thread.eml", artefacts.make_eml())))
    assert _rows(document, "eml") == [
        ("¶ 1", "Email 1", "", "From: Tan, Wei Ming · To: LC Ops Desk, ramp.lead@example.com · "
                               "Cc: Priya Nair · Sent: 2026-03-03 09:14 +08:00 · "
                               "Subject: Load plan revision SQ 221"),
        ("¶ 2", "Email 1", "Tan, Wei Ming", "Hi team,"),
        ("¶ 3", "Email 1", "Tan, Wei Ming", "The plan for SQ 221 was revised twice last night "
                                            "because the bags came late. We held the bags until "
                                            "the second wave."),
        # The signature ("Wei Ming", a phone number) is left out; the quote keeps its sender.
        ("¶ 4", "Earlier in the thread", "Priya Nair", "Can we release the plan before the final "
                                                       "figures? The captain is asking."),
        # The attached email (the PDF attachment is not read).
        ("¶ 5", "Email 2", "", "From: Ramp Lead · To: Load Control · Sent: 2026-03-02 21:05 "
                               "+08:00 · Subject: FW: Late bags"),
        ("¶ 6", "Email 2", "Ramp Lead", "Forwarding for the record."),
        ("¶ 7", "Earlier in the thread", "Ops Desk", "Bags for SQ 221 will be 20 minutes late."),
    ]  # fmt: skip
    text = " ".join(s.text for s in document.segments)
    assert "+65" not in text and "Sent: Monday" not in text and "PDF" not in text
    assert document.hidden_names == [
        "Tan, Wei Ming", "Wei Ming Tan", "weiming.tan@example.com", "LC Ops Desk",
        "lc.ops@example.com", "ramp.lead@example.com", "Priya Nair", "priya.nair@example.com",
        "Ramp Lead", "Load Control", "lc@example.com", "Ops Desk", "ops.desk@example.com",
        "Kumar, Ravi", "Ravi Kumar",
    ]  # fmt: skip


def test_html_only_email_is_read_as_text(tmp_path: Path) -> None:
    document = _ok(parsing.parse_eml(_write(tmp_path, "gate.eml", artefacts.make_html_eml())))
    assert _rows(document, "eml") == [
        ("¶ 1", "Email 1", "", "From: Ops Desk · Subject: Gate change"),
        ("¶ 2", "Email 1", "Ops Desk", "Gate changed to C24 & plan reissued."),
        ("¶ 3", "Earlier in the thread", "Ravi Kumar", "Is the gate final?"),
    ]
    assert "color" not in " ".join(s.text for s in document.segments)  # the style block


def test_a_quote_whose_writer_cannot_be_told_from_the_date_is_left_unattributed(
    tmp_path: Path,
) -> None:
    raw = (
        b"From: Priya Nair <priya.nair@example.com>\r\nSubject: Re: plan\r\n\r\n"
        b"Agreed.\r\n\r\nOn 2 March 2026 Ravi Kumar wrote:\r\n> Release at T-40?\r\n"
        b"\r\n> Second paragraph.\r\n"
    )
    document = _ok(parsing.parse_eml(_write(tmp_path, "reply.eml", raw)))
    assert [(s.section, s.speaker_label, s.text) for s in document.segments[1:]] == [
        ("Email 1", "Priya Nair", "Agreed."),
        ("Earlier in the thread", "", "Release at T-40?"),
        ("Earlier in the thread", "", "Second paragraph."),
    ]


def test_quoted_lines_without_an_attribution_line_are_kept_unattributed(tmp_path: Path) -> None:
    raw = b"From: ops@example.com\r\nSubject: x\r\n\r\nYes.\r\n> earlier words\r\n"
    document = _ok(parsing.parse_eml(_write(tmp_path, "r.eml", raw)))
    assert [(s.section, s.speaker_label, s.text) for s in document.segments] == [
        ("Email 1", "", "From: ops@example.com · Subject: x"),
        ("Email 1", "ops@example.com", "Yes."),
        ("Earlier in the thread", "", "earlier words"),
    ]


def test_a_file_that_is_not_an_email_is_refused(tmp_path: Path) -> None:
    result = parsing.parse_eml(_write(tmp_path, "notes.eml", b"just some words\nand more\n"))
    assert isinstance(result, Err)
    assert (result.kind, result.message) == (ErrorKind.VALIDATION, parsing.NOT_AN_EMAIL)


@pytest.mark.parametrize(
    ("label", "name_like"),
    [("Ops Desk", False), ("LC Ops Desk", False), ("Load Control", False), ("Priya Nair", True)],
)
def test_team_mailboxes_are_not_names(label: str, name_like: bool) -> None:
    assert parsing.looks_like_name(label) is name_like


def test_spreadsheets_and_emails_are_on_the_practice_side_of_analysis_a() -> None:
    from app.pipeline import ga_internal

    assert ga_internal.side_of("working_spreadsheet") == "practice"
    assert ga_internal.side_of("email_thread") == "practice"
    assert ga_internal.side_of("sop") == "documents"
