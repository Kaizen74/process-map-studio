"""R2: reading an event-log extract (PRD §3.13.3 steps 1 to 4; criterion 83 in part; A.11)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.services import mining

SYSTEM = Path(__file__).resolve().parents[1] / "fixtures" / "system"
LOG = SYSTEM / "dcs_log.csv"
ROLE_MAP: dict[str, str | None] = json.loads((SYSTEM / "role_map.json").read_text("utf-8"))
SINGAPORE = "Asia/Singapore"
DCS_ACTIVITIES = {
    "Plan created",
    "Special load checked",
    "Plan revised",
    "Loading report received",
    "Weight deviation checked",
    "Manual weight override",
    "Load sheet issued",
}


def _fixture() -> tuple[list[str], list[dict[str, str]]]:
    return mining.read_csv(LOG.read_bytes())


def _rows(*lines: str) -> list[dict[str, str]]:
    return mining.read_csv("\n".join(lines).encode("utf-8"))[1]


CORE = {"case_id": "case_id", "activity": "activity", "timestamp": "timestamp"}


# --- the A.11 fixture ------------------------------------------------------------------------


def test_the_generator_rewrites_the_fixture_byte_for_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location("generate_log", SYSTEM / "generate_log.py")
    assert spec and spec.loader
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    monkeypatch.setattr(generator, "HERE", tmp_path)  # write the copy elsewhere
    generator.main()
    assert (tmp_path / "dcs_log.csv").read_bytes() == LOG.read_bytes()
    assert (tmp_path / "role_map.json").read_bytes() == (SYSTEM / "role_map.json").read_bytes()


def test_the_fixture_has_what_appendix_a11_describes() -> None:
    headers, rows = _fixture()
    assert headers == ["case_id", "activity", "timestamp", "end_timestamp", "resource", "system"]
    cases: dict[str, list[str]] = {}
    for row in rows:
        cases.setdefault(row["case_id"], []).append(row["activity"])
    assert len(cases) == 200
    assert {a for acts in cases.values() for a in acts} == DCS_ACTIVITIES  # no Plan approved
    revised = sum("Plan revised" in acts for acts in cases.values()) / 200
    override = sum("Manual weight override" in acts for acts in cases.values()) / 200
    assert 0.13 <= revised <= 0.23  # about 18%
    assert 0.08 <= override <= 0.16  # about 12%
    for acts in cases.values():
        assert acts[0] == "Plan created" and acts[-1] == "Load sheet issued"
        if "Plan revised" in acts:
            assert acts.index("Plan revised") == acts.index("Special load checked") + 1
        if "Manual weight override" in acts:
            assert acts.index("Manual weight override") == len(acts) - 2
    assert set(ROLE_MAP.values()) == {"Load controller", "Ramp"}


def test_loading_report_takes_about_14_minutes_median_and_25_at_the_90th_percentile() -> None:
    parsed = mining.parse_log(_fixture()[1], mining.suggest_column_map(_fixture()[0]), SINGAPORE,
                              ROLE_MAP)  # fmt: skip
    minutes = sorted(
        (int(e.end[11:13]) * 60 + int(e.end[14:16]) - int(e.start[11:13]) * 60
         - int(e.start[14:16])) % (24 * 60)
        for e in parsed.events if e.activity == "Loading report received" and e.end
    )  # fmt: skip
    median, p90 = minutes[len(minutes) // 2], minutes[int(len(minutes) * 0.9)]
    assert 11 <= median <= 17
    assert 20 <= p90 <= 31


# --- step 1: column suggestions --------------------------------------------------------------


def test_the_fixture_headers_map_to_their_own_fields() -> None:
    assert mining.suggest_column_map(_fixture()[0]) == {h: h for h in _fixture()[0]}


@pytest.mark.parametrize(
    ("header", "field"),
    [
        ("Case ID", "case_id"),
        ("Order No.", "case_id"),
        ("CaseKey", "case_id"),
        ("Event Name", "activity"),
        ("Status", "activity"),
        ("Start Time", "timestamp"),
        ("EndTime", "end_timestamp"),
        ("Completed at", "end_timestamp"),
        ("Performed by", "resource"),
        ("User ID", "resource"),
        ("Team", "role"),
        ("Source system", "system"),
    ],
)
def test_a_header_is_matched_by_name_similarity(header: str, field: str) -> None:
    assert mining.suggest_column_map([header])[header] == field


def test_each_field_is_suggested_once_and_unknown_headers_are_left_for_eric() -> None:
    suggested = mining.suggest_column_map(["Case ID", "Order No.", "Region", "Comment", "Activity"])
    assert suggested == {"Case ID": "case_id", "Order No.": None, "Region": None,
                         "Comment": None, "Activity": "activity"}  # fmt: skip


def test_resources_are_listed_once_each_for_the_mapping_step() -> None:
    headers, rows = _fixture()
    assert mining.distinct_resources(rows, mining.suggest_column_map(headers)) == sorted(ROLE_MAP)
    assert mining.distinct_resources(rows, {"case_id": "case_id"}) == []


# --- reading the file ------------------------------------------------------------------------


@pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
def test_common_delimiters_and_a_byte_order_mark_are_read(delimiter: str) -> None:
    text = delimiter.join(["Case ID", "Activity", "Timestamp"]) + "\n"
    text += delimiter.join(["C1", "Order approved", "2026-03-02 09:15"]) + "\n"
    headers, rows = mining.read_csv("﻿".encode() + text.encode("utf-8"))
    assert headers == ["Case ID", "Activity", "Timestamp"]
    assert rows == [
        {"Case ID": "C1", "Activity": "Order approved", "Timestamp": "2026-03-02 09:15"}
    ]


# --- step 2: timestamps ----------------------------------------------------------------------


def test_day_first_and_month_first_are_told_apart_by_the_values() -> None:
    assert mining.detect_format(["13/03/2026 10:00", "02/03/2026 10:00"]) == "%d/%m/%Y %H:%M"
    assert mining.detect_format(["03/13/2026 10:00", "03/02/2026 10:00"]) == "%m/%d/%Y %H:%M"
    assert mining.detect_format(["2026-03-02T06:00:00+08:00"]) == mining.ISO_OFFSET
    assert mining.detect_format(["2026-03-02 06:00:00"]) == "%Y-%m-%d %H:%M:%S"
    assert mining.detect_format(["", "yesterday"]) is None
    assert mining.detect_format([]) is None


def test_times_are_read_in_the_logs_time_zone_and_stored_in_utc() -> None:
    zone = ZoneInfo(SINGAPORE)
    assert mining.to_utc("2026-03-02 06:49:00", "%Y-%m-%d %H:%M:%S", zone) == "2026-03-01T22:49:00Z"
    assert mining.to_utc("2026-03-02T06:00:00+01:00", mining.ISO_OFFSET, zone) == (
        "2026-03-02T05:00:00Z"  # an offset in the value wins over the log's time zone
    )
    assert mining.to_utc("not a time", "%Y-%m-%d %H:%M:%S", zone) is None
    assert mining.to_utc("", "%Y-%m-%d %H:%M:%S", zone) is None
    assert mining.to_utc("2026-03-02 06:49:00", None, zone) is None


def test_eric_can_correct_an_ambiguous_format() -> None:
    rows = _rows("case_id,activity,timestamp", "C1,Opened,01/02/2026 10:00")
    detected = mining.parse_log(rows, CORE, "UTC", {})
    corrected = mining.parse_log(rows, CORE, "UTC", {}, timestamp_format="%m/%d/%Y %H:%M")
    assert detected.events[0].start == "2026-02-01T10:00:00Z"  # day first on a tie
    assert corrected.events[0].start == "2026-01-02T10:00:00Z"
    assert corrected.report.timestamp_format == "%m/%d/%Y %H:%M"


# --- steps 3 and 4: roles and the validation report ------------------------------------------


def test_the_fixture_imports_cleanly_with_roles_and_no_resource_codes() -> None:
    headers, rows = _fixture()
    parsed = mining.parse_log(rows, mining.suggest_column_map(headers), SINGAPORE, ROLE_MAP,
                              window=("2026-03-02", "2026-04-26"))  # fmt: skip
    report = parsed.report
    assert (report.rows_read, report.rows_kept, report.cases, report.activities) == (
        len(rows), len(rows), 200, 7,
    )  # fmt: skip
    assert report.dropped.model_dump() == {"unparseable_time": 0, "missing_case_or_activity": 0,
                                           "duplicate": 0}  # fmt: skip
    assert (report.dropped_share, report.single_event_cases, report.outside_window) == (0.0, 0, 0)
    assert report.date_from == "2026-03-01T22:49:00Z"  # 06:49 on Monday 2 March, Singapore
    assert not report.refused and report.refusal == ""
    assert {e.role for e in parsed.events} == {"Load controller", "Ramp"}
    assert {e.system for e in parsed.events} == {"DCS"}
    stored = json.dumps([e.model_dump() for e in parsed.events])
    assert not any(code in stored for code in ROLE_MAP)  # constraint 24
    assert all(e.end for e in parsed.events)
    by_case = [e.case_id for e in parsed.events]
    assert by_case == sorted(by_case)


def test_a_role_column_is_preferred_and_an_unmapped_resource_is_an_unknown_role() -> None:
    rows = _rows("case,step,time,user,team", "C1,Opened,2026-03-02 09:00,U1,Buyer",
                 "C1,Closed,2026-03-02 10:00,U1,", "C1,Paid,2026-03-02 11:00,U9,")  # fmt: skip
    column_map = {"case": "case_id", "step": "activity", "time": "timestamp", "user": "resource",
                  "team": "role"}  # fmt: skip
    parsed = mining.parse_log(rows, column_map, "UTC", {"U1": "Clerk", "U9": None})
    assert [e.role for e in parsed.events] == ["Buyer", "Clerk", None]
    assert parsed.report.unknown_role_events == 1
    known = mining.parse_log(rows, column_map, "UTC", {"U1": "Clerk", "U9": None},
                             known_roles={"clerk": "Clerk", "accounts clerk": "Clerk"})  # fmt: skip
    # Buyer isn't a role here, so U1's mapped role is used instead; U9 is an unknown role.
    assert [e.role for e in known.events] == ["Clerk", "Clerk", None]
    assert known.report.unknown_role_events == 1


def test_dropped_rows_are_counted_by_reason_and_attributes_kept() -> None:
    rows = _rows(
        "case_id,activity,timestamp,region",
        "C1,Opened,2026-03-02 09:00,North",
        "C1,Opened,2026-03-02 09:00,North",  # duplicate
        ",Opened,2026-03-02 09:00,North",  # no case
        "C2,,2026-03-02 09:00,North",  # no activity
        "C2,Opened,soon,North",  # unparseable time
        "C3,Opened,2026-03-02 09:00,South",
        "C3,Closed,2026-03-03 09:00,South",
        "C4,Opened,2026-03-02 09:00,South",
        "C4,Closed,2026-03-04 09:00,South",
        "C4,Paid,2026-03-04 10:00,South",
        "C5,Opened,2026-03-09 09:00,South",
        "C5,Closed,2026-03-09 10:00,South",
        "C6,Opened,2026-03-02 09:00,South",
        "C6,Closed,2026-03-02 09:30,South",
        "C7,Opened,2026-03-02 09:00,South",
        "C7,Closed,2026-03-02 09:30,South",
        "C8,Opened,2026-03-02 09:00,South",
        "C8,Closed,2026-03-02 09:30,South",
        "C9,Opened,2026-03-02 09:00,South",
        "C9,Closed,2026-03-02 09:30,South",
    )
    parsed = mining.parse_log(rows, {**CORE, "region": "case_attribute"}, "UTC", {},
                              window=("2026-03-01", "2026-03-08"))  # fmt: skip
    report = parsed.report
    assert report.dropped.model_dump() == {"unparseable_time": 1, "missing_case_or_activity": 2,
                                           "duplicate": 1}  # fmt: skip
    assert (report.rows_read, report.rows_kept, report.dropped_share) == (20, 16, 0.2)
    assert not report.refused  # 20% exactly is allowed; more is refused
    assert report.single_event_cases == 1  # C1
    assert report.outside_window == 2  # C5's two events
    assert parsed.events[0].attributes == {"region": "North"}


def test_more_than_a_fifth_of_rows_dropped_is_refused_with_the_reason() -> None:
    rows = _rows("case_id,activity,timestamp", "C1,Opened,2026-03-02 09:00",
                 "C1,Closed,later", "C2,Opened,2026-03-02 09:00", "C2,Closed,later")  # fmt: skip
    report = mining.parse_log(rows, CORE, "UTC", {}).report
    assert report.refused and report.dropped_share == 0.5
    assert report.refusal.startswith("50% of the rows can't be used (more than 20%)")


def test_a_missing_required_column_is_refused_in_plain_words() -> None:
    rows = _rows("case_id,activity", "C1,Opened")
    report = mining.parse_log(
        rows, {"case_id": "case_id", "activity": "activity"}, "UTC", {}
    ).report
    assert report.refused and report.missing_columns == ["timestamp"]
    assert report.refusal == ("The extract has no column for: timestamp. Map one, or ask for a "
                              "new extract.")  # fmt: skip
    assert report.rows_kept == 0 and report.timestamp_format == ""


def test_an_empty_file_is_refused() -> None:
    report = mining.parse_log([], CORE, "UTC", {}).report
    assert report.refused and report.refusal == "The file has no rows."
    assert report.date_from is None and report.dropped_share == 0.0
