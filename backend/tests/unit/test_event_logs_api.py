"""System logs (API_CONTRACT.md → System records: event logs; PRD §3.13.3; criteria 83 and 84;
constraint 24): upload, column map, user IDs to roles in memory, the validation report, the
data-owner approval gate and the import job, on fixture A.11."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.actions import event_logs as actions
from app.actions import jobs as job_actions
from app.config import AppConfig
from app.db import session_scope
from app.domain.result import Err
from app.domain.system_records import ImportInput
from app.main import create_app
from app.repositories import audit
from app.repositories import event_logs as repo
from tests import fixture_engagement
from tests.uploads import wait_for_jobs

SYSTEM = Path(__file__).resolve().parents[1] / "fixtures" / "system"
LOG = (SYSTEM / "dcs_log.csv").read_bytes()
CODES: dict[str, str] = json.loads((SYSTEM / "role_map.json").read_text("utf-8"))
HEADERS = ["case_id", "activity", "timestamp", "end_timestamp", "resource", "system"]
APPROVED = {"approved_by_role": "Head of ground operations", "confirm_approval": True}


@dataclass
class Engagement:
    client: TestClient
    id: str
    roles: dict[str, str]  # name → id
    data_dir: Path

    def upload(self, content: bytes = LOG, **form: str) -> Any:
        data = {"name": "DCS extract", "system": "DCS", **form}
        files = {"file": ("log.csv", content, "text/csv")}
        return self.client.post(f"/api/engagements/{self.id}/event-logs", files=files, data=data)

    def put(self, lid: str, what: str, body: dict[str, Any]) -> Any:
        return self.client.put(f"/api/event-logs/{lid}/{what}", json=body)

    def start(self, lid: str, body: dict[str, Any] | None = None) -> Any:
        return self.client.post(f"/api/event-logs/{lid}/import", json=APPROVED | (body or {}))

    def roles_for_codes(self) -> dict[str, str | None]:
        return {code: self.roles[role] for code, role in CODES.items()}

    def ready(self, content: bytes = LOG, **form: str) -> str:
        """Uploaded, column map confirmed and user IDs mapped: the log ID."""
        uploaded = self.upload(content, **form)
        assert uploaded.status_code == 201, uploaded.text
        lid = str(uploaded.json()["id"])
        columns = uploaded.json()["column_map"]
        assert self.put(lid, "column-map", {"columns": columns}).status_code == 200
        if any(f == "resource" for f in columns.values()):
            assert self.put(lid, "role-map", {"roles": self.roles_for_codes()}).status_code == 200
        return lid


@pytest.fixture()
def engagement(settings_config: AppConfig) -> Iterator[Engagement]:
    with TestClient(create_app(settings_config)) as client:
        client.put("/api/settings/profile", json={"owner_name": "Owner"})
        built = fixture_engagement.build(client, sources=[])
        yield Engagement(client, built.engagement_id, built.roles, settings_config.data_dir)


def _csv(*lines: str) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


def _error(response: Any) -> tuple[int, str, str]:
    error = response.json()["error"]
    return response.status_code, error["code"], error["message"]


# --- the whole import on fixture A.11 (criteria 83 and 84) -----------------------------------


def test_the_fixture_imports_with_roles_and_leaves_no_user_id_anywhere(
    engagement: Engagement,
) -> None:
    client = engagement.client
    uploaded = engagement.upload(window_start="2026-03-02", window_end="2026-04-26")
    assert uploaded.status_code == 201, uploaded.text
    log = uploaded.json()
    lid = log["id"]
    assert log["status"] == "uploaded" and log["file_held"] is True
    assert list(log["column_map"].items()) == [(h, h) for h in HEADERS]  # suggested, file order
    assert log["timezone"] == "Asia/Singapore"
    assert [(r["value"], r["suggested_role_id"]) for r in log["resources"]] == [
        (code, None) for code in sorted(CODES)
    ]
    assert sum(r["events"] for r in log["resources"]) == 1063
    preview = log["validation_report"]
    assert (preview["rows_read"], preview["cases"], preview["activities"]) == (1063, 200, 7)
    assert preview["unknown_role_events"] == 1063 and not preview["refused"]

    mapped = engagement.put(lid, "column-map", {"columns": log["column_map"]})
    assert mapped.status_code == 200 and mapped.json()["status"] == "mapped"
    roles = engagement.put(lid, "role-map", {"roles": engagement.roles_for_codes()})
    assert roles.status_code == 200, roles.text
    assert roles.json()["validation_report"]["unknown_role_events"] == 0
    assert roles.json()["role_map"] == engagement.roles_for_codes()

    refused = engagement.start(lid, {"confirm_approval": False})
    assert _error(refused) == (409, "APPROVAL_REQUIRED", actions.APPROVAL)
    assert _error(engagement.start(lid, {"approved_by_role": " "}))[1] == "APPROVAL_REQUIRED"
    started = engagement.start(lid)
    assert started.status_code == 202, started.text
    wait_for_jobs(client)
    job = client.get(f"/api/jobs/{started.json()['job_id']}").json()
    assert (job["status"], job["message"]) == ("done", "Imported 1,063 events from 200 cases.")

    imported = client.get(f"/api/event-logs/{lid}").json()
    assert imported["status"] == "imported" and imported["approved_at"]
    assert imported["approved_by_role"] == "Head of ground operations"
    assert (imported["file_held"], imported["resources"], imported["role_map"]) == (False, [], {})
    report = imported["validation_report"]
    assert (report["rows_kept"], report["outside_window"], report["unknown_role_events"]) == (
        1063, 0, 0,
    )  # fmt: skip
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        events = repo.events(session, lid)
    assert len(events) == 1063
    assert {e["role_id"] for e in events} == {engagement.roles["Load controller"],
                                               engagement.roles["Ramp"]}  # fmt: skip
    assert events[0]["ts_start"] == "2026-03-01T22:49:00Z"  # 06:49 Singapore time
    assert set(events[0]) == {"case_id", "activity", "ts_start", "ts_end", "role_id",
                              "case_attributes"}  # fmt: skip
    assert actions._held(lid) is None  # the file is forgotten

    # Criterion 84: no user ID in the database, the data folder or anything the API returns.
    stored = b"".join(p.read_bytes() for p in engagement.data_dir.rglob("*") if p.is_file())
    answers = json.dumps([client.get(f"/api/event-logs/{lid}").json(),
                          client.get(f"/api/engagements/{engagement.id}/event-logs").json(),
                          client.get(f"/api/jobs/{started.json()['job_id']}").json()])  # fmt: skip
    for code in CODES:
        assert code.encode() not in stored, code
        assert code not in answers, code


def test_the_audit_trail_names_the_steps_without_user_ids(engagement: Engagement) -> None:
    lid = engagement.ready()
    assert engagement.start(lid).status_code == 202
    wait_for_jobs(engagement.client)
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        rows = audit.list_recent(session, engagement_id=engagement.id)
    actions_done = [r["action"] for r in rows if r["target_type"] == "event_log"]
    assert sorted(actions_done) == ["Confirmed column map", "Imported system log",
                                    "Uploaded system log"]  # fmt: skip
    trail = json.dumps(rows, default=str)
    assert not any(code in trail for code in CODES)
    assert '"approved_by_role": "Head of ground operations"' in trail


# --- the order of the import checks ------------------------------------------------------------


def test_the_column_map_must_be_confirmed_and_every_user_id_mapped(engagement: Engagement) -> None:
    lid = engagement.upload().json()["id"]
    assert _error(engagement.start(lid)) == (409, "COLUMN_MAP_NOT_CONFIRMED", actions.NOT_CONFIRMED)
    columns = engagement.client.get(f"/api/event-logs/{lid}").json()["column_map"]
    engagement.put(lid, "column-map", {"columns": columns})
    status, code, message = _error(engagement.start(lid))
    assert (status, code, message) == (422, "VALIDATION", actions.UNMAPPED.format(n=7))
    partial = {"LC07": engagement.roles["Load controller"], "RP31": None}
    assert engagement.put(lid, "role-map", {"roles": partial}).status_code == 200
    assert _error(engagement.start(lid))[2] == actions.UNMAPPED.format(n=5)
    everyone = {code: None for code in CODES}  # Unknown role is a choice
    assert engagement.put(lid, "role-map", {"roles": everyone}).status_code == 200
    assert engagement.start(lid).status_code == 202
    wait_for_jobs(engagement.client)
    log = engagement.client.get(f"/api/event-logs/{lid}").json()
    assert log["validation_report"]["unknown_role_events"] == 1063


def test_an_approver_role_with_a_hidden_name_is_refused(engagement: Engagement) -> None:
    added = engagement.client.post(f"/api/engagements/{engagement.id}/redaction-terms",
                                   json={"term": "Priya Nair"})  # fmt: skip
    assert added.status_code in (200, 201), added.text
    lid = engagement.ready()
    response = engagement.start(lid, {"approved_by_role": "Priya Nair, operations"})
    status, _, message = _error(response)
    assert status == 422 and "Priya" not in message
    assert response.json()["error"]["details"]["field"] == "approved_by_role"
    long = engagement.start(lid, {"approved_by_role": "x" * 121})
    assert _error(long)[0] == 422


def test_more_than_a_fifth_of_rows_unusable_is_refused(engagement: Engagement) -> None:
    content = _csv("case_id,activity,timestamp", "C1,Opened,2026-03-02 09:00",
                   "C1,Closed,later", "C2,Opened,2026-03-02 09:00", "C2,Closed,later")  # fmt: skip
    lid = engagement.ready(content)
    preview = engagement.client.get(f"/api/event-logs/{lid}").json()["validation_report"]
    assert preview["refused"] and preview["dropped"]["unparseable_time"] == 2
    status, code, message = _error(engagement.start(lid))
    assert (status, code) == (422, "IMPORT_REFUSED")
    assert message.startswith("50% of the rows can't be used")


def test_a_missing_required_column_is_refused(engagement: Engagement) -> None:
    lid = engagement.ready(_csv("case_id,activity,when", "C1,Opened,2026-03-02 09:00"))
    log = engagement.client.get(f"/api/event-logs/{lid}").json()
    assert log["column_map"]["when"] is None
    assert log["validation_report"]["missing_columns"] == ["timestamp"]
    assert _error(engagement.start(lid))[:2] == (422, "IMPORT_REFUSED")


def test_an_imported_log_cannot_change_or_be_imported_again(engagement: Engagement) -> None:
    lid = engagement.ready()
    assert engagement.start(lid).status_code == 202
    wait_for_jobs(engagement.client)
    columns = {h: h for h in HEADERS}
    assert _error(engagement.put(lid, "column-map", {"columns": columns}))[:2] == (
        409, "ALREADY_IMPORTED",
    )  # fmt: skip
    assert _error(engagement.start(lid))[:2] == (409, "ALREADY_IMPORTED")


# --- held in memory only -----------------------------------------------------------------------


def test_after_a_restart_the_file_is_gone_and_eric_uploads_again(engagement: Engagement) -> None:
    lid = engagement.ready()
    actions._forget(lid)  # what a restart does
    log = engagement.client.get(f"/api/event-logs/{lid}").json()
    assert (log["file_held"], log["resources"], log["role_map"]) == (False, [], {})
    assert log["validation_report"]["cases"] == 200  # the counts are kept
    assert _error(engagement.start(lid)) == (409, "FILE_NOT_HELD", actions.FILE_NOT_HELD)
    roles = engagement.put(lid, "role-map", {"roles": {}})
    assert _error(roles)[:2] == (409, "FILE_NOT_HELD")


def test_an_import_whose_file_has_gone_fails_in_plain_words(engagement: Engagement) -> None:
    lid = engagement.ready()
    sessions = engagement.client.app.state.sessions  # type: ignore[attr-defined]
    queued: list[str] = []
    started = actions.start_import(sessions, lid, ImportInput(**APPROVED), queued.append)
    assert not isinstance(started, Err)
    assert _error(engagement.start(lid))[:2] == (409, "IMPORT_RUNNING")
    actions._forget(lid)
    config = engagement.client.app.state.config  # type: ignore[attr-defined]
    job_actions.run_job(config, sessions, queued[0])
    job = engagement.client.get(f"/api/jobs/{queued[0]}").json()
    assert (job["status"], job["error"]) == ("failed", actions.FILE_GONE)
    assert engagement.client.get(f"/api/event-logs/{lid}").json()["status"] == "failed"


def test_an_unexpected_error_saves_no_events(
    engagement: Engagement, monkeypatch: pytest.MonkeyPatch
) -> None:
    lid = engagement.ready()

    def broken(*_: Any) -> int:
        raise RuntimeError("disk full")

    monkeypatch.setattr(repo, "add_events", broken)
    started = engagement.start(lid)
    wait_for_jobs(engagement.client)
    job = engagement.client.get(f"/api/jobs/{started.json()['job_id']}").json()
    assert (job["status"], job["error"]) == ("failed", actions.UNEXPECTED)
    assert engagement.client.get(f"/api/event-logs/{lid}").json()["status"] == "failed"
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        assert repo.event_count(session, lid) == 0
    assert actions._held(lid) is None


def test_a_large_upload_never_spills_to_a_temporary_file(
    engagement: Engagement, monkeypatch: pytest.MonkeyPatch
) -> None:
    def to_disk(*_: Any) -> None:
        raise AssertionError("the upload was written to a temporary file")

    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", to_disk)
    big = LOG + b"".join(
        f"FL{2000 + n},Plan created,2026-03-03 06:00:00,,LC07,DCS\n".encode() for n in range(60_000)
    )
    assert len(big) > 2 * 1024 * 1024
    uploaded = engagement.upload(big)
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["validation_report"]["cases"] == 60_200


def test_deleting_removes_the_log_its_events_and_the_held_file(engagement: Engagement) -> None:
    lid = engagement.ready()
    assert engagement.start(lid).status_code == 202
    wait_for_jobs(engagement.client)
    other = engagement.ready()
    for log_id in (lid, other):
        assert engagement.client.delete(f"/api/event-logs/{log_id}").status_code == 204
        assert engagement.client.get(f"/api/event-logs/{log_id}").status_code == 404
        assert actions._held(log_id) is None
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        assert repo.event_count(session, lid) == 0
    assert engagement.client.delete(f"/api/event-logs/{lid}").status_code == 404
    assert engagement.client.get(f"/api/engagements/{engagement.id}/event-logs").json() == []


# --- suggestions and corrections ---------------------------------------------------------------


def test_roles_are_suggested_from_a_role_column_or_the_value_itself(engagement: Engagement) -> None:
    content = _csv("Case ID,Event Name,Start Time,Performed by,Team",
                   "C1,Opened,2026-03-02 09:00,U1,load controller",
                   "C1,Closed,2026-03-02 10:00,U1,Load controller",
                   "C2,Opened,2026-03-02 09:00,Ramp,",
                   "C2,Closed,2026-03-02 10:00,U3,Finance")  # fmt: skip
    log = engagement.upload(content).json()
    assert log["column_map"] == {"Case ID": "case_id", "Event Name": "activity",
                                 "Start Time": "timestamp", "Performed by": "resource",
                                 "Team": "role"}  # fmt: skip
    assert {r["value"]: r["suggested_role_id"] for r in log["resources"]} == {
        "U1": engagement.roles["Load controller"], "Ramp": engagement.roles["Ramp"], "U3": None,
    }  # fmt: skip
    # "Finance" is not a role of this engagement: an unknown role, and U2 has no role at all.
    assert log["validation_report"]["unknown_role_events"] == 2


def test_eric_corrects_the_date_format_and_the_columns(engagement: Engagement) -> None:
    content = _csv("ref,step,when,region", "C1,Opened,01/02/2026 10:00,North",
                   "C1,Closed,01/03/2026 10:00,North")  # fmt: skip
    log = engagement.upload(content, timezone="UTC").json()
    lid = log["id"]
    assert log["validation_report"]["missing_columns"] == ["case_id", "timestamp"]
    columns = {"ref": "case_id", "step": "activity", "when": "timestamp",
               "region": "case_attribute"}  # fmt: skip
    mapped = engagement.put(lid, "column-map",
                            {"columns": columns, "timestamp_format": "%m/%d/%Y %H:%M"})  # fmt: skip
    assert mapped.status_code == 200, mapped.text
    body = mapped.json()
    assert body["timestamp_format"] == "%m/%d/%Y %H:%M"
    assert body["validation_report"]["date_from"] == "2026-01-02T10:00:00Z"
    assert list(body["column_map"]) == ["ref", "step", "when", "region"]
    assert engagement.start(lid).status_code == 202
    wait_for_jobs(engagement.client)
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        events = repo.events(session, lid)
    assert [e["case_attributes"] for e in events] == [{"region": "North"}] * 2


@pytest.mark.parametrize(
    ("columns", "fmt", "field", "message"),
    [
        ({"case_id": "case_id"}, None, "columns", actions.EVERY_COLUMN),
        ({**{h: h for h in HEADERS}, "extra": None}, None, "columns", actions.EVERY_COLUMN),
        ({**{h: h for h in HEADERS}, "system": "colour"}, None, "columns", actions.UNKNOWN_FIELD),
        ({**{h: h for h in HEADERS}, "end_timestamp": "timestamp"}, None, "columns",
         actions.USED_TWICE.format(fields="timestamp")),
        ({h: h for h in HEADERS}, "%Y", "timestamp_format", actions.BAD_FORMAT),
    ],
)  # fmt: skip
def test_a_column_map_with_a_problem_is_refused(
    engagement: Engagement, columns: dict[str, str | None], fmt: str | None, field: str,
    message: str,
) -> None:  # fmt: skip
    lid = engagement.upload().json()["id"]
    response = engagement.put(lid, "column-map", {"columns": columns, "timestamp_format": fmt})
    assert _error(response) == (422, "VALIDATION", message)
    assert response.json()["error"]["details"]["field"] == field


def test_a_role_map_must_use_the_files_user_ids_and_the_engagements_roles(
    engagement: Engagement,
) -> None:
    lid = engagement.upload().json()["id"]
    unknown = engagement.put(lid, "role-map", {"roles": {"ZZ99": None}})
    assert _error(unknown) == (422, "VALIDATION", actions.NOT_IN_FILE)
    elsewhere = engagement.put(lid, "role-map", {"roles": {"LC07": "not-a-role"}})
    assert _error(elsewhere) == (422, "VALIDATION", actions.NOT_A_ROLE)


@pytest.mark.parametrize(
    ("content", "form", "field", "message"),
    [
        (LOG, {"name": " "}, "name", actions.NO_NAME),
        (LOG, {"timezone": "Mars/Olympus"}, "timezone", actions.BAD_ZONE),
        (LOG, {"window_start": "2/3/2026"}, "window_start", actions.BAD_DATE),
        (LOG, {"window_start": "2026-04-01", "window_end": "2026-03-01"}, "window_end",
         actions.BACKWARDS),
        (b"", {}, "file", actions.EMPTY),
        (b"\n\n", {}, "file", actions.NO_HEADER),
        (_csv("case_id,activity,case_id", "C1,Opened,C2"), {}, "file",
         actions.SAME_HEADER.format(name="case_id")),
        (LOG, {"system": "x" * 121}, "system",
         "The system can be up to 120 characters on one line."),
    ],
)  # fmt: skip
def test_an_upload_with_a_problem_is_refused(
    engagement: Engagement, content: bytes, form: dict[str, str], field: str, message: str
) -> None:
    response = engagement.upload(content, **form)
    assert _error(response) == (422, "VALIDATION", message)
    assert response.json()["error"]["details"]["field"] == field
    assert engagement.client.get(f"/api/engagements/{engagement.id}/event-logs").json() == []


def test_a_file_over_the_limit_is_refused(
    engagement: Engagement, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(actions, "MAX_BYTES", 1000)
    assert _error(engagement.upload())[2] == actions.TOO_BIG


def test_unknown_engagements_and_logs_are_not_found(engagement: Engagement) -> None:
    client = engagement.client
    files = {"file": ("log.csv", LOG, "text/csv")}
    missing = client.post("/api/engagements/nope/event-logs", files=files, data={"name": "x"})
    assert missing.status_code == 404
    assert client.get("/api/engagements/nope/event-logs").status_code == 404
    assert client.get("/api/event-logs/nope").status_code == 404
    assert engagement.put("nope", "column-map", {"columns": {}}).status_code == 404
    assert engagement.put("nope", "role-map", {"roles": {}}).status_code == 404
    assert engagement.start("nope").status_code == 404


# --- metrics (R4; §3.13.5; criteria 85 and 94) -------------------------------------------------


def _imported(engagement: Engagement) -> str:
    lid = engagement.ready()
    assert engagement.start(lid).status_code == 202
    wait_for_jobs(engagement.client)
    return lid


def _metrics(engagement: Engagement, lid: str, scope: str) -> Any:
    return engagement.client.get(f"/api/event-logs/{lid}/metrics", params={"scope": scope})


def test_the_import_works_out_every_scope_and_hides_groups_under_five_cases(
    engagement: Engagement,
) -> None:
    lid = _imported(engagement)
    answers = {}
    for scope in ("activity", "transition", "case", "variant", "role"):
        response = _metrics(engagement, lid, scope)
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["log_id"], body["scope"], body["minimum_cases"]) == (lid, scope, 5)
        assert all(g["case_count"] >= 5 for g in body["groups"])
        answers[scope] = body
    activity = answers["activity"]["groups"]
    assert [g["key"] for g in activity][:5] == sorted(
        ["Plan created", "Special load checked", "Loading report received",
         "Weight deviation checked", "Load sheet issued"]
    )  # most events first, then by name  # fmt: skip
    assert activity[0]["metrics"]["cases_per_week"] == 25.0
    [case] = answers["case"]["groups"]
    assert (case["key"], case["label"], case["metrics"]["cases"]) == ("all", "All cases", 200)
    variants = answers["variant"]["groups"]
    assert [g["case_count"] for g in variants] == [141, 36, 19]
    assert answers["variant"]["too_few"] == 1  # the fourth variant has 4 cases
    assert [g["label"] for g in answers["role"]["groups"]] == ["Load controller", "Ramp"]
    transitions = answers["transition"]["groups"]
    assert transitions[0]["metrics"]["count"] == 200
    assert not any(code in json.dumps(answers) for code in CODES)


def test_metrics_need_an_imported_log_and_a_known_scope(engagement: Engagement) -> None:
    lid = engagement.ready()
    assert _error(_metrics(engagement, lid, "case")) == (409, "NOT_IMPORTED", actions.NOT_IMPORTED)
    assert _error(_metrics(engagement, lid, "people")) == (422, "VALIDATION", actions.BAD_SCOPE)
    assert _error(_metrics(engagement, lid, ""))[0] == 422
    assert _metrics(engagement, "nope", "case").status_code == 404


def test_deleting_a_log_removes_its_metrics(engagement: Engagement) -> None:
    lid = _imported(engagement)
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        assert repo.metrics(session, lid, "activity")
    assert engagement.client.delete(f"/api/event-logs/{lid}").status_code == 204
    with session_scope(engagement.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        assert repo.metrics(session, lid, "activity") == []


def test_the_time_zone_can_be_changed_in_the_column_step(engagement: Engagement) -> None:
    """R7: the wizard's time-zone step sends the zone with the confirmed columns."""
    log = engagement.upload().json()
    assert log["validation_report"]["date_from"] == "2026-03-01T22:49:00Z"  # Singapore
    body = {"columns": log["column_map"], "timezone": "Europe/London"}
    changed = engagement.put(log["id"], "column-map", body)
    assert changed.status_code == 200, changed.text
    assert changed.json()["timezone"] == "Europe/London"
    assert changed.json()["validation_report"]["date_from"] == "2026-03-02T06:49:00Z"
    bad = engagement.put(log["id"], "column-map", {**body, "timezone": "Mars/Olympus"})
    assert _error(bad) == (422, "VALIDATION", actions.BAD_ZONE)


def test_a_new_log_starts_with_the_time_zone_in_settings(engagement: Engagement) -> None:
    """R10: Settings → Regional sets the time zone a log gets when none is chosen."""
    client = engagement.client
    saved = client.put("/api/settings/regional", json={"default_timezone": "Europe/London"})
    assert saved.status_code == 200, saved.text
    assert engagement.upload().json()["timezone"] == "Europe/London"
    assert engagement.upload(timezone="UTC").json()["timezone"] == "UTC"  # chosen wins
