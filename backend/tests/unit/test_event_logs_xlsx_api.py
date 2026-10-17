"""Excel event logs (P10b R11b; API_CONTRACT.md → System records: event logs; PRD §3.13.1
"CSV or Excel"; constraint 24): fixture A.11 saved as .xlsx imports exactly like the CSV, in
memory, and leaves no user ID anywhere."""

from __future__ import annotations

import csv
import io
import json
import tempfile
from datetime import datetime
from typing import Any

import pytest
from openpyxl import Workbook

from app.services import mining
from tests.unit.test_event_logs_api import CODES, LOG, Engagement, _error
from tests.unit.test_event_logs_api import engagement as engagement  # the shared fixture
from tests.uploads import wait_for_jobs

STAMPS = {"timestamp", "end_timestamp"}


def a11_as_xlsx(extra_sheet: bool = True) -> bytes:
    """Fixture A.11 as Excel writes it: times as date cells, a second sheet that is not read."""
    rows = list(csv.reader(io.StringIO(LOG.decode("utf-8"))))
    header = rows[0]
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = "DCS extract"
    sheet.append([*header, None])  # an empty header cell at the end (formatting) is left out
    for row in rows[1:]:
        sheet.append(
            [
                datetime.fromisoformat(v) if h in STAMPS and v else v
                for h, v in zip(header, row, strict=True)
            ]
        )
    if extra_sheet:
        notes = book.create_sheet("Notes")
        notes.append(["Extract run by", "IT"])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def upload_xlsx(engagement: Engagement, content: bytes) -> Any:
    files = {
        "file": (
            "dcs.xlsx",
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    return engagement.client.post(
        f"/api/engagements/{engagement.id}/event-logs",
        files=files,
        data={"name": "DCS extract (Excel)", "system": "DCS"},
    )


def test_an_excel_extract_imports_exactly_like_the_csv_and_leaves_no_user_id(
    engagement: Engagement,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def to_disk(*_: Any, **__: Any) -> None:
        raise AssertionError("an extract must never be written to a temporary file")

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", to_disk)
    monkeypatch.setattr(tempfile, "TemporaryFile", to_disk)
    monkeypatch.setattr(tempfile, "SpooledTemporaryFile", to_disk)
    from_csv = engagement.upload().json()
    uploaded = upload_xlsx(engagement, a11_as_xlsx())
    assert uploaded.status_code == 201, uploaded.text
    log = uploaded.json()
    assert log["column_map"] == from_csv["column_map"]
    assert log["resources"] == from_csv["resources"]
    assert log["validation_report"] == from_csv["validation_report"]
    assert log["validation_report"]["timestamp_format"] == "%Y-%m-%d %H:%M:%S"

    client = engagement.client
    done = {}
    for lid in (from_csv["id"], log["id"]):
        mapped = engagement.put(lid, "column-map", {"columns": log["column_map"]})
        assert mapped.status_code == 200
        roles = engagement.put(lid, "role-map", {"roles": engagement.roles_for_codes()})
        assert roles.status_code == 200
        started = engagement.start(lid)
        assert started.status_code == 202, started.text
        wait_for_jobs(client)
        done[lid] = client.get(f"/api/jobs/{started.json()['job_id']}").json()
    job = done[log["id"]]
    assert (job["status"], job["message"]) == ("done", "Imported 1,063 events from 200 cases.")
    for scope in ("activity", "transition", "case", "variant", "role"):
        figures = [
            client.get(f"/api/event-logs/{lid}/metrics", params={"scope": scope}).json()
            for lid in done
        ]
        assert figures[0]["groups"], scope
        assert figures[1]["groups"] == figures[0]["groups"], scope  # identical figures

    stored = b"".join(p.read_bytes() for p in engagement.data_dir.rglob("*") if p.is_file())
    answers = json.dumps([client.get(f"/api/event-logs/{log['id']}").json(), job])
    for code in CODES:
        assert code.encode() not in stored, code
        assert code not in answers, code


def test_a_damaged_or_empty_excel_file_is_refused_in_plain_words(
    engagement: Engagement,
) -> None:
    damaged = upload_xlsx(engagement, mining.XLSX_START + b"not really a workbook")
    assert _error(damaged) == (422, "VALIDATION", mining.BAD_XLSX)
    assert damaged.json()["error"]["details"]["field"] == "file"
    out = io.BytesIO()
    Workbook().save(out)
    assert _error(upload_xlsx(engagement, out.getvalue()))[2] == "The file has no header row."


def test_excel_cells_are_written_as_the_log_reader_expects() -> None:
    from datetime import date, time

    assert mining._log_cell(datetime(2026, 3, 2, 6, 49)) == "2026-03-02 06:49:00"
    assert mining._log_cell(datetime(2026, 3, 2, 6, 49, 0, 500000)) == "2026-03-02 06:49:00.500000"
    assert mining._log_cell(date(2026, 3, 2)) == "2026-03-02"
    assert mining._log_cell(time(6, 49)) == "06:49:00"
    assert mining._log_cell(1000.0) == "1000"
    assert mining._log_cell(12.5) == "12.5"
    assert mining._log_cell(False) == "FALSE"
    assert mining._log_cell(" FL1000 ") == "FL1000"
    assert mining._log_cell(None) == ""


def test_a_csv_is_still_read_as_csv() -> None:
    result = mining.read_extract(b"case_id;activity\nC1;Opened\n")
    assert result.value == (["case_id", "activity"], [{"case_id": "C1", "activity": "Opened"}])  # type: ignore[union-attr]
