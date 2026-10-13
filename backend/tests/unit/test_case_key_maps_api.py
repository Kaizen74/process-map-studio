"""Case-key maps (P10b R11c; API_CONTRACT.md → Case-key maps; PRD §3.13.1; constraint 24):
linking two imported logs whose systems give the same case different IDs, the end-to-end time
across both, the 5-case floor, replacing and removing a map, and the frontend sample."""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from app.actions import case_key_maps as actions
from app.db import session_scope
from app.repositories import audit
from app.services import mining
from tests.unit.test_event_logs_api import CODES, LOG, Engagement, _error
from tests.unit.test_event_logs_api import engagement as engagement  # the shared fixture
from tests.uploads import wait_for_jobs

RAMP_ACTIVITIES = {"Loading report received", "Load sheet issued"}


def ramp_log() -> bytes:
    """A second system's log for the same flights: its own case IDs (R-1000 for FL1000), only
    the ramp's two activities, no user column."""
    rows = list(csv.DictReader(io.StringIO(LOG.decode("utf-8"))))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["case_id", "activity", "timestamp", "end_timestamp", "system"])
    for row in rows:
        if row["activity"] in RAMP_ACTIVITIES:
            writer.writerow([row["case_id"].replace("FL", "R-"), row["activity"],
                             row["timestamp"], row["end_timestamp"], "Ramp"])  # fmt: skip
    return out.getvalue().encode()


def imported(engagement: Engagement, content: bytes, name: str) -> str:
    lid = engagement.ready(content, name=name)
    started = engagement.start(lid)
    assert started.status_code == 202, started.text
    wait_for_jobs(engagement.client)
    return lid


def link(
    engagement: Engagement, content: bytes, first: str, second: str, name: str = "keys.csv"
) -> Any:
    return engagement.client.post(
        f"/api/engagements/{engagement.id}/case-key-maps",
        files={"file": (name, content, "text/csv")},
        data={"from_log_id": first, "to_log_id": second},
    )


def keys(count: int, extra: str = "") -> bytes:
    lines = ["DCS flight,Ramp turnaround,Note"]
    lines += [f"FL{1000 + n},R-{1000 + n},ok" for n in range(count)]
    return ("\n".join(lines) + "\n" + extra).encode()


def test_two_logs_linked_by_case_ids_give_the_end_to_end_time(engagement: Engagement) -> None:
    dcs = imported(engagement, LOG, "DCS extract")
    ramp = imported(engagement, ramp_log(), "Ramp log")
    unknown = (
        "FL9999,R-1001,not in DCS\nFL1002,R-9999,not in Ramp\n,R-1003,empty\nFL1000,R-1000,again\n"
    )
    response = link(engagement, keys(150, unknown), dcs, ramp)
    assert response.status_code == 201, response.text
    view = response.json()
    assert (view["from_log_name"], view["to_log_name"]) == ("DCS extract", "Ramp log")
    # 150 pairs + 2 with an unknown ID; the empty one is left out and the repeat counts once.
    assert (view["pairs"], view["from_found"], view["to_found"], view["linked_cases"]) == (
        152, 151, 151, 150,
    )  # fmt: skip
    assert view["basis"] == "wait" and view["minimum_cases"] == 5
    spread = view["end_to_end"]
    assert spread["n"] == 150 and 0 < spread["median_min"] <= spread["p90_min"]
    # The end-to-end time covers both systems: at least each log's own cycle time.
    case = engagement.client.get(f"/api/event-logs/{dcs}/metrics", params={"scope": "case"}).json()
    assert spread["median_min"] >= case["groups"][0]["metrics"]["cycle_time"]["median_min"] * 0.5
    assert engagement.client.get(f"/api/engagements/{engagement.id}/case-key-maps").json() == [view]
    # No case ID in what the API returns; the audit row holds counts and log names only.
    assert "FL1000" not in json.dumps(view)
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        rows = audit.list_recent(session, engagement_id=engagement.id)
    row = next(r for r in rows if r["action"] == "Linked system logs")
    assert row["after"] == {"logs": ["DCS extract", "Ramp log"], "pairs": 152, "linked_cases": 150}
    assert "FL1000" not in json.dumps(rows, default=str)


def test_fewer_than_five_linked_cases_show_no_time(engagement: Engagement) -> None:
    dcs = imported(engagement, LOG, "DCS extract")
    ramp = imported(engagement, ramp_log(), "Ramp log")
    view = link(engagement, keys(4), dcs, ramp).json()
    assert (view["linked_cases"], view["end_to_end"]) == (4, None)
    assert link(engagement, keys(5), dcs, ramp).json()["end_to_end"]["n"] == 5


def test_a_new_file_replaces_the_map_and_remove_unlinks_the_logs(engagement: Engagement) -> None:
    dcs = imported(engagement, LOG, "DCS extract")
    ramp = imported(engagement, ramp_log(), "Ramp log")
    link(engagement, keys(20), dcs, ramp)
    swapped = "Ramp,DCS\n" + "".join(f"R-{1000 + n},FL{1000 + n}\n" for n in range(30))
    again = link(engagement, swapped.encode(), ramp, dcs).json()  # the other way round
    assert (again["from_log_name"], again["pairs"], again["linked_cases"]) == ("Ramp log", 30, 30)
    listed = engagement.client.get(f"/api/engagements/{engagement.id}/case-key-maps").json()
    assert [m["pairs"] for m in listed] == [30]
    url = f"/api/engagements/{engagement.id}/case-key-maps"
    assert (
        engagement.client.delete(url, params={"from_log_id": dcs, "to_log_id": ramp}).status_code
        == 204
    )
    assert engagement.client.get(url).json() == []
    gone = engagement.client.delete(url, params={"from_log_id": dcs, "to_log_id": ramp})
    assert _error(gone) == (404, "NOT_FOUND", actions.NOT_LINKED)
    # Deleting a log removes its maps.
    link(engagement, keys(10), dcs, ramp)
    assert engagement.client.delete(f"/api/event-logs/{ramp}").status_code == 204
    assert engagement.client.get(url).json() == []


def test_an_excel_key_file_is_read_like_a_csv(engagement: Engagement) -> None:
    from openpyxl import Workbook

    dcs = imported(engagement, LOG, "DCS extract")
    ramp = imported(engagement, ramp_log(), "Ramp log")
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["DCS", "Ramp"])
    for n in range(12):
        sheet.append([f"FL{1000 + n}", f"R-{1000 + n}"])
    out = io.BytesIO()
    book.save(out)
    assert link(engagement, out.getvalue(), dcs, ramp, "keys.xlsx").json()["linked_cases"] == 12


def test_a_map_needs_two_different_imported_logs_and_a_usable_file(
    engagement: Engagement,
) -> None:
    dcs = imported(engagement, LOG, "DCS extract")
    held = engagement.upload(ramp_log(), name="Ramp log").json()["id"]  # uploaded, not imported
    assert _error(link(engagement, keys(5), dcs, held)) == (422, "VALIDATION", actions.BAD_LOGS)
    same = link(engagement, keys(5), dcs, dcs)
    assert _error(same) == (422, "VALIDATION", actions.BAD_LOGS)
    assert same.json()["error"]["details"]["field"] == "from_log_id"
    ramp = imported(engagement, ramp_log(), "Ramp log 2")
    for content, message in (
        (b"Only one column\nFL1000\n", mining.NEED_TWO),
        (b"Case,Case\nFL1000,R-1000\n", mining.SAME_NAMES),
        (b"DCS,Ramp\n,\n", mining.NO_PAIRS),
        (b"", "The file is empty."),
    ):
        assert _error(link(engagement, content, dcs, ramp))[2] == message
    missing = engagement.client.get("/api/engagements/nope/case-key-maps")
    assert missing.status_code == 404


def test_the_frontend_case_key_sample_matches_the_backend(engagement: Engagement) -> None:
    """frontend/tests/fixtures/case_key_maps.json: the logs and the map as the backend sends them
    (R11c), for the System records screen tests. Not a PRD baseline; no user ID in it.
    Rewritten with PMS_UPDATE_GOLDEN=1."""
    from tests.golden.test_golden_baselines import FRONTEND_FIXTURES, matches_baseline

    dcs = imported(engagement, LOG, "DCS extract")
    ramp = imported(engagement, ramp_log(), "Ramp log")
    link(engagement, keys(150), dcs, ramp)
    client = engagement.client
    bundle = {
        "logs": client.get(f"/api/engagements/{engagement.id}/event-logs").json(),
        "maps": client.get(f"/api/engagements/{engagement.id}/case-key-maps").json(),
    }
    text = json.dumps(bundle)
    assert not any(code in text for code in CODES)  # constraint 24: no user ID in the sample
    when = r'"\1": "2026-10-13T00:00:00+00:00"'
    fixed = json.loads(re.sub(r'"(created_at|approved_at)": "[^"]+"', when, text))
    matches_baseline("case_key_maps.json", fixed, FRONTEND_FIXTURES)
