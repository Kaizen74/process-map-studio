"""System logs (API_CONTRACT.md → System records: event logs; PRD §3.13.3; criteria 83, 84; R3).

Upload → column map → user IDs to roles → validation report → data-owner approval → import job.

The uploaded file is held in this process's memory only (`_HELD`), never written to disk or the
database, because it may carry user IDs (constraint 24). Its user IDs and the role map live only
there; the import writes events with a role and then forgets the file. After a restart the file
is gone and Eric uploads it again.
"""

from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import BinaryIO
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions.engagements import ENGAGEMENT_MISSING, actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import SystemLogColumn
from app.domain.models import RoleView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.system_records import (
    ColumnMapInput,
    EventLogView,
    ImportInput,
    ImportStarted,
    MetricsView,
    ParsedLog,
    ResourceRow,
    RoleMapInput,
)
from app.repositories import audit
from app.repositories import engagements as engagements_repo
from app.repositories import event_logs as repo
from app.repositories import jobs as jobs_repo
from app.services import grounding, mining

Sessions = sessionmaker[Session]
Enqueue = Callable[[str], None]

IMPORT_JOB = "event_log_import"
MAX_BYTES = 100 * 1024 * 1024
DEFAULT_TIMEZONE = "Asia/Singapore"  # PRD §3.4 DEFAULT_TIMEZONE; the Settings card comes with R10
MAX_TEXT = 120
FIELDS = {f.value for f in SystemLogColumn}
ONCE = FIELDS - {SystemLogColumn.CASE_ATTRIBUTE.value}
RESOURCE = SystemLogColumn.RESOURCE.value
ROLE = SystemLogColumn.ROLE.value

LOG_MISSING = "That system log doesn't exist."
NO_NAME = "Give the log a name."
EMPTY = "The file is empty."
TOO_BIG = "The file is larger than 100 MB."
NO_HEADER = "The file has no header row."
SAME_HEADER = "Two columns have the same name: {name}. Rename one and upload again."
BAD_ZONE = "Choose a time zone from the list, for example Asia/Singapore."
BAD_DATE = "Use a date like 2026-03-02."
BACKWARDS = "The window starts after it ends."
HIDDEN_NAME = "{what} contains a name from your list of names to hide. Use the role instead."
FILE_NOT_HELD = (
    "The file is no longer held: the app was restarted since it was uploaded. Upload it again "
    "(it is kept in memory only, so user IDs are never saved)."
)
ALREADY_IMPORTED = "This log is already imported. Delete it and upload again to change it."
IMPORT_RUNNING = "This log is being imported. Wait for the import to finish."
EVERY_COLUMN = "Give a field (or none) for every column of the file, once each."
UNKNOWN_FIELD = "Choose a field from the list for every column."
USED_TWICE = "Each field can be used for one column only: {fields}."
BAD_FORMAT = "Choose a date format from the list."
NOT_A_ROLE = "Choose one of this engagement's roles."
NOT_IN_FILE = "That user ID isn't in the file."
APPROVAL = (
    "Tick that the data owner approved this extract for this purpose, and give the approver's role."
)
NOT_CONFIRMED = "Confirm the column map first."
UNMAPPED = "Choose a role or Unknown role for every user ID ({n} left)."
FILE_GONE = "The import stopped: the file is no longer held (the app restarted). Upload it again."
NOT_IMPORTED = "Import the log first: its figures are worked out during the import."
BAD_SCOPE = "Choose activity, transition, case, variant or role."
UNEXPECTED = (
    "Something went wrong while importing this log. No events were saved. Upload the file "
    "again, or use Copy details to report it."
)


@dataclass
class _Held:
    """An uploaded file waiting for its import: memory only."""

    headers: list[str]
    rows: list[dict[str, str]]
    timestamp_format: str | None = None
    role_map: dict[str, str | None] = field(default_factory=dict)


_HELD: dict[str, _Held] = {}
_LOCK = threading.Lock()


def _held(log_id: str) -> _Held | None:
    with _LOCK:
        return _HELD.get(log_id)


def _forget(log_id: str) -> None:
    with _LOCK:
        _HELD.pop(log_id, None)


def _invalid(field_name: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field_name})


def _conflict(code: str, message: str) -> Err:
    return Err(ErrorKind.CONFLICT, message, api_code=code)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# --- roles ------------------------------------------------------------------------------------


def _role_names(roles: list[RoleView]) -> dict[str, str]:
    """Lower-cased role name or alias → the role's name."""
    names: dict[str, str] = {}
    for role in roles:
        for word in (role.name, *role.aliases):
            names.setdefault(word.strip().lower(), role.name)
    return names


def _column(column_map: dict[str, str | None], wanted: str) -> str | None:
    return next((h for h, f in column_map.items() if f == wanted), None)


def _resources(held: _Held, column_map: dict[str, str | None],
               roles: list[RoleView]) -> list[ResourceRow]:  # fmt: skip
    """Each user ID in the file, how many rows carry it and a suggested role (memory only)."""
    column = _column(column_map, RESOURCE)
    if column is None:
        return []
    role_column = _column(column_map, ROLE)
    names, by_name = _role_names(roles), {r.name: r.id for r in roles}
    counts: Counter[str] = Counter()
    stated: dict[str, Counter[str]] = {}
    for row in held.rows:
        value = row.get(column, "").strip()
        if not value:
            continue
        counts[value] += 1
        role = names.get(row.get(role_column, "").strip().lower()) if role_column else None
        if role:
            stated.setdefault(value, Counter())[role] += 1
    out = []
    for value in sorted(counts):
        named = stated[value].most_common(1)[0][0] if value in stated else names.get(value.lower())
        suggested = by_name.get(named) if named else None
        out.append(ResourceRow(value=value, events=counts[value], suggested_role_id=suggested))
    return out


def _parse(held: _Held, log: EventLogView, roles: list[RoleView]) -> ParsedLog:
    names = {r.id: r.name for r in roles}
    role_of = {value: names.get(rid) if rid else None for value, rid in held.role_map.items()}
    window = (log.window_start, log.window_end) if log.window_start and log.window_end else None
    return mining.parse_log(
        held.rows, log.column_map, log.timezone, role_of, window=window,
        timestamp_format=held.timestamp_format, known_roles=_role_names(roles),
    )  # fmt: skip


def _refresh(session: Session, log: EventLogView, held: _Held) -> EventLogView:
    """Store the new preview report (counts only)."""
    roles = engagements_repo.list_roles(session, log.engagement_id)
    report = _parse(held, log, roles).report
    return repo.update(session, log.id, {"validation_report": report.model_dump()})


def _full(session: Session, log: EventLogView) -> EventLogView:
    """The log as the API returns it: with what is held in memory, while it is held."""
    held = _held(log.id) if log.status != "imported" else None
    if held is None:
        return log
    roles = engagements_repo.list_roles(session, log.engagement_id)
    return log.model_copy(update={
        "file_held": True, "timestamp_format": held.timestamp_format,
        "resources": _resources(held, log.column_map, roles), "role_map": dict(held.role_map),
    })  # fmt: skip


# --- upload -----------------------------------------------------------------------------------


def _text(session: Session, engagement_id: str, field_name: str, value: str,
          what: str) -> Result[str]:  # fmt: skip
    text = value.strip()
    if len(text) > MAX_TEXT or "\n" in text:
        return _invalid(field_name, f"{what} can be up to {MAX_TEXT} characters on one line.")
    hidden = [t.term for t in redaction.name_replacements(session, engagement_id)]
    if grounding.scan_redaction_terms(text, hidden):  # the name itself is never echoed
        return _invalid(field_name, HIDDEN_NAME.format(what=what))
    return Ok(text)


def _day(field_name: str, value: str) -> Result[str | None]:
    text = value.strip()
    if not text:
        return Ok(None)
    try:
        if len(text) != 10:
            raise ValueError(text)
        return Ok(date.fromisoformat(text).isoformat())
    except ValueError:
        return _invalid(field_name, BAD_DATE)


def _zone(value: str) -> Result[str]:
    text = value.strip() or DEFAULT_TIMEZONE
    try:
        ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError):
        return _invalid("timezone", BAD_ZONE)
    return Ok(text)


def _read(stream: BinaryIO) -> Result[bytes]:
    content = stream.read(MAX_BYTES + 1)
    if not content:
        return _invalid("file", EMPTY)
    if len(content) > MAX_BYTES:
        return _invalid("file", TOO_BIG)
    return Ok(content)


def upload_log(
    config: AppConfig, sessions: Sessions, engagement_id: str, *, stream: BinaryIO, name: str,
    system: str = "", timezone: str = "", window_start: str = "", window_end: str = "",
) -> Result[EventLogView]:  # fmt: skip
    """Hold the file in memory, suggest the column map and preview the report."""
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        if not name.strip():
            return _invalid("name", NO_NAME)
        checked: dict[str, str | None] = {}
        for result, key in (
            (_text(session, engagement_id, "name", name, "The name"), "name"),
            (_text(session, engagement_id, "system", system, "The system"), "system"),
            (_zone(timezone), "timezone"),
            (_day("window_start", window_start), "window_start"),
            (_day("window_end", window_end), "window_end"),
        ):
            match result:
                case Err() as err:
                    return err
                case Ok(value=value):
                    checked[key] = value
        start, end = checked["window_start"], checked["window_end"]
        if start and end and start > end:
            return _invalid("window_end", BACKWARDS)
        match _read(stream):
            case Err() as err:
                return err
            case Ok(value=content):
                pass
        headers, rows = mining.read_csv(content)
        if not any(headers):
            return _invalid("file", NO_HEADER)
        twice = sorted({h for h in headers if headers.count(h) > 1})
        if twice:
            return _invalid("file", SAME_HEADER.format(name=twice[0]))
        log = repo.create(session, engagement_id, {
            **checked, "file_ref": "", "status": "uploaded",
            "column_map": mining.suggest_column_map(headers),
        })  # fmt: skip
        held = _Held(headers=headers, rows=rows)
        with _LOCK:
            _HELD[log.id] = held
        log = _refresh(session, log, held)
        audit.record(
            session, actor=actor_name(config), action="Uploaded system log",
            target_type="event_log", target_id=log.id, engagement_id=engagement_id,
            after={"name": log.name, "system": log.system},
        )  # fmt: skip
        return Ok(_full(session, log))


# --- reading and deleting ---------------------------------------------------------------------


def list_logs(sessions: Sessions, engagement_id: str) -> Result[list[EventLogView]]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok([_full(session, log) for log in repo.list_for(session, engagement_id)])


def get_log(sessions: Sessions, log_id: str) -> Result[EventLogView]:
    with session_scope(sessions) as session:
        log = repo.get(session, log_id)
        if log is None:
            return Err(ErrorKind.NOT_FOUND, LOG_MISSING)
        return Ok(_full(session, log))


def delete_log(config: AppConfig, sessions: Sessions, log_id: str) -> Result[None]:
    with session_scope(sessions) as session:
        log = repo.get(session, log_id)
        if log is None:
            return Err(ErrorKind.NOT_FOUND, LOG_MISSING)
        repo.delete(session, log_id)
        audit.record(
            session, actor=actor_name(config), action="Deleted system log",
            target_type="event_log", target_id=log_id, engagement_id=log.engagement_id,
            before={"name": log.name, "status": log.status},
        )  # fmt: skip
    _forget(log_id)
    return Ok(None)


# --- mapping ----------------------------------------------------------------------------------


def _editable(session: Session, log_id: str) -> Result[tuple[EventLogView, _Held]]:
    """The log and its held file, if both can still change."""
    log = repo.get(session, log_id)
    if log is None:
        return Err(ErrorKind.NOT_FOUND, LOG_MISSING)
    if log.status == "imported":
        return _conflict("ALREADY_IMPORTED", ALREADY_IMPORTED)
    held = _held(log_id)
    if held is None:
        return _conflict("FILE_NOT_HELD", FILE_NOT_HELD)
    if log_id in jobs_repo.unfinished_targets(session, IMPORT_JOB):
        return _conflict("IMPORT_RUNNING", IMPORT_RUNNING)
    return Ok((log, held))


def _checked_columns(held: _Held, body: ColumnMapInput) -> Result[dict[str, str | None]]:
    if set(body.columns) != set(held.headers):
        return _invalid("columns", EVERY_COLUMN)
    if any(f is not None and f not in FIELDS for f in body.columns.values()):
        return _invalid("columns", UNKNOWN_FIELD)
    used = Counter(f for f in body.columns.values() if f in ONCE)
    twice = sorted(f for f, n in used.items() if n > 1)
    if twice:
        return _invalid("columns", USED_TWICE.format(fields=", ".join(twice)))
    allowed = {*mining.FORMATS, mining.ISO_OFFSET}
    if body.timestamp_format is not None and body.timestamp_format not in allowed:
        return _invalid("timestamp_format", BAD_FORMAT)
    return Ok({h: body.columns[h] for h in held.headers})  # in file order


def set_column_map(config: AppConfig, sessions: Sessions, log_id: str,
                   body: ColumnMapInput) -> Result[EventLogView]:  # fmt: skip
    with session_scope(sessions) as session:
        match _editable(session, log_id):
            case Err() as err:
                return err
            case Ok(value=(log, held)):
                pass
        match _checked_columns(held, body):
            case Err() as err:
                return err
            case Ok(value=columns):
                pass
        changes: dict[str, object] = {"column_map": columns, "status": "mapped"}
        if body.timezone is not None:
            match _zone(body.timezone):
                case Err() as err:
                    return err
                case Ok(value=zone):
                    changes["timezone"] = zone
        log = repo.update(session, log_id, changes)
        held.timestamp_format = body.timestamp_format
        roles = engagements_repo.list_roles(session, log.engagement_id)
        values = {r.value for r in _resources(held, columns, roles)}
        held.role_map = {v: rid for v, rid in held.role_map.items() if v in values}
        log = _refresh(session, log, held)
        audit.record(
            session, actor=actor_name(config), action="Confirmed column map",
            target_type="event_log", target_id=log_id, engagement_id=log.engagement_id,
            after={"columns": columns, "timestamp_format": body.timestamp_format,
                   "timezone": log.timezone},
        )  # fmt: skip
        return Ok(_full(session, log))


def set_role_map(sessions: Sessions, log_id: str, body: RoleMapInput) -> Result[EventLogView]:
    """User IDs → roles, held in memory with the file; never saved or audited by value."""
    with session_scope(sessions) as session:
        match _editable(session, log_id):
            case Err() as err:
                return err
            case Ok(value=(log, held)):
                pass
        roles = engagements_repo.list_roles(session, log.engagement_id)
        values = {r.value for r in _resources(held, log.column_map, roles)}
        if any(v not in values for v in body.roles):
            return _invalid("roles", NOT_IN_FILE)
        ids = {r.id for r in roles}
        if any(rid is not None and rid not in ids for rid in body.roles.values()):
            return _invalid("roles", NOT_A_ROLE)
        held.role_map = dict(body.roles)
        return Ok(_full(session, _refresh(session, log, held)))


# --- import -----------------------------------------------------------------------------------


def start_import(sessions: Sessions, log_id: str, body: ImportInput,
                 enqueue: Enqueue) -> Result[ImportStarted]:  # fmt: skip
    """Check the approval and the report, then queue the import job (§3.13.3 steps 4 and 5)."""
    with session_scope(sessions) as session:
        match _editable(session, log_id):
            case Err() as err:
                return err
            case Ok(value=(log, held)):
                pass
        if not body.confirm_approval or not body.approved_by_role.strip():
            return _conflict("APPROVAL_REQUIRED", APPROVAL)
        match _text(session, log.engagement_id, "approved_by_role", body.approved_by_role,
                    "The approver's role"):  # fmt: skip
            case Err() as err:
                return err
            case Ok(value=approver):
                pass
        if log.status == "uploaded":
            return _conflict("COLUMN_MAP_NOT_CONFIRMED", NOT_CONFIRMED)
        roles = engagements_repo.list_roles(session, log.engagement_id)
        left = [r for r in _resources(held, log.column_map, roles) if r.value not in held.role_map]
        if left:
            return _invalid("roles", UNMAPPED.format(n=len(left)))
        report = _parse(held, log, roles).report
        if report.refused:
            return Err(ErrorKind.VALIDATION, report.refusal, api_code="IMPORT_REFUSED")
        repo.update(session, log_id, {"approved_by_role": approver})
        job = jobs_repo.create(
            session, engagement_id=log.engagement_id, job_type=IMPORT_JOB, target_id=log_id
        )
    enqueue(job.id)
    return Ok(ImportStarted(job_id=job.id, log_id=log_id))


def run_import(config: AppConfig, sessions: Sessions, job_id: str) -> Result[str]:
    """The import job: events with roles only, the final report, then the file is forgotten."""
    with session_scope(sessions) as session:
        job = jobs_repo.get(session, job_id)
        log = repo.get(session, job.target_id or "") if job else None
        if log is None:
            return Err(ErrorKind.NOT_FOUND, LOG_MISSING)
        held = _held(log.id)
        if held is None:
            repo.update(session, log.id, {"status": "failed"})
            return Err(ErrorKind.CONFLICT, FILE_GONE)
        roles = engagements_repo.list_roles(session, log.engagement_id)
        parsed = _parse(held, log, roles)
        if parsed.report.refused:
            failed = {"status": "failed", "validation_report": parsed.report.model_dump()}
            repo.update(session, log.id, failed)
            _forget(log.id)
            return Err(ErrorKind.VALIDATION, parsed.report.refusal)
        by_name = {r.name: r.id for r in roles}
        count = repo.add_events(session, log.id, [
            {"case_id": e.case_id, "activity": e.activity, "ts_start": e.start, "ts_end": e.end,
             "role_id": by_name.get(e.role) if e.role else None, "case_attributes": e.attributes}
            for e in parsed.events
        ])  # fmt: skip
        repo.add_metrics(session, log.id, mining.metrics(parsed.events, log.timezone))
        report = parsed.report
        repo.update(session, log.id, {"status": "imported", "approved_at": _now(),
                                      "validation_report": report.model_dump()})  # fmt: skip
        audit.record(
            session, actor=actor_name(config), action="Imported system log",
            target_type="event_log", target_id=log.id, engagement_id=log.engagement_id,
            after={"events": count, "cases": report.cases, "activities": report.activities,
                   "approved_by_role": log.approved_by_role},
        )  # fmt: skip
    _forget(log.id)
    return Ok(f"Imported {count:,} events from {report.cases:,} cases.")


def mark_failed(sessions: Sessions, log_id: str) -> None:
    """After an unexpected error in the import job: the log is failed and the file let go."""
    with session_scope(sessions) as session:
        if repo.get(session, log_id) is not None:
            repo.update(session, log_id, {"status": "failed"})
    _forget(log_id)


def get_metrics(sessions: Sessions, log_id: str, scope: str) -> Result[MetricsView]:
    """The stored metrics of one scope; groups under 5 cases are only counted (§3.13.5)."""
    if scope not in mining.SCOPES:
        return _invalid("scope", BAD_SCOPE)
    with session_scope(sessions) as session:
        log = repo.get(session, log_id)
        if log is None:
            return Err(ErrorKind.NOT_FOUND, LOG_MISSING)
        if log.status != "imported":
            return _conflict("NOT_IMPORTED", NOT_IMPORTED)
        shown, too_few = mining.visible(repo.metrics(session, log_id, scope))
    return Ok(MetricsView(log_id=log_id, scope=scope, minimum_cases=mining.MINIMUM_CASES,
                          groups=shown, too_few=too_few))  # fmt: skip
