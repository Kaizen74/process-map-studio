"""System records (PRD §3.13; R2): reading an event-log extract. Pure and deterministic; no
process-mining library (PM4Py is AGPL, constraint 19).

- `read_csv`: the header and rows of a CSV extract (UTF-8; comma, semicolon, tab or bar).
- `suggest_column_map`: each header → a B.40 field by name, for Eric to confirm or correct.
- `distinct_resources`: the resource values, for the role-mapping step; held in memory only.
- `parse_log`: rows → events and the plain-language validation report. A resource becomes a role
  here and is then gone: no event carries it (constraint 24).
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

from app.domain.enums import SystemLogColumn as Field
from app.domain.system_records import DroppedRows, LogEvent, ParsedLog, ValidationReport

REQUIRED = (Field.CASE_ID.value, Field.ACTIVITY.value, Field.TIMESTAMP.value)
FIELD_WORDS = {
    Field.CASE_ID.value: ("case id", "case", "case key", "order no", "order number", "ticket",
                          "flight", "reference", "document number"),
    Field.ACTIVITY.value: ("activity", "event", "status", "step", "action", "task", "event name"),
    Field.TIMESTAMP.value: ("timestamp", "time", "start", "start time", "event time", "date time",
                            "datetime", "created at", "start timestamp"),
    Field.END_TIMESTAMP.value: ("end timestamp", "end", "end time", "completed", "finished",
                                "completed at", "end date"),
    Field.RESOURCE.value: ("resource", "user", "user id", "username", "performed by", "agent",
                           "operator", "changed by"),
    Field.ROLE.value: ("role", "team", "department", "group", "function"),
    Field.SYSTEM.value: ("system", "source system", "application", "source"),
}  # fmt: skip
MATCH = 0.82  # how alike a header must be to a field's words to be suggested
FORMATS = (
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M",
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
    "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M",
)  # fmt: skip
ISO_OFFSET = "ISO 8601 with offset"
MAX_DROPPED = 0.20  # §3.13.3 step 4: more than this and the import is refused
LABELS = {Field.CASE_ID.value: "case ID", Field.ACTIVITY.value: "activity",
          Field.TIMESTAMP.value: "timestamp"}  # fmt: skip


def read_csv(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """The header and the rows of a CSV extract; a byte-order mark is ignored."""
    text = content.decode("utf-8-sig", errors="replace")
    try:
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(
            text[:4096], delimiters=",;\t|"
        )
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [h.strip() for h in reader.fieldnames or []]
    rows = [{(k or "").strip(): (v or "").strip() for k, v in row.items() if k is not None}
            for row in reader]  # fmt: skip
    return headers, rows


def _words(text: str) -> str:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", spaced.lower()).split())


def suggest_column_map(headers: list[str]) -> dict[str, str | None]:
    """Each header → the B.40 field its name is most like (each field used once, best match
    first), or None (left out unless Eric keeps it as a case attribute)."""
    scored = []
    for header in headers:
        name = _words(header)
        for field, words in FIELD_WORDS.items():
            best = max(SequenceMatcher(None, name, w).ratio() for w in words)
            if best >= MATCH:
                scored.append((best, header, field))
    out: dict[str, str | None] = dict.fromkeys(headers)
    taken: set[str] = set()
    for _, header, field in sorted(scored, key=lambda s: -s[0]):
        if out[header] is None and field not in taken:
            out[header] = field
            taken.add(field)
    return out


def distinct_resources(
    rows: list[dict[str, str]], column_map: Mapping[str, str | None]
) -> list[str]:
    """The distinct resource values, for the role-mapping step. Held in memory only."""
    column = next((h for h, f in column_map.items() if f == Field.RESOURCE.value), None)
    if column is None:
        return []
    return sorted({row.get(column, "") for row in rows} - {""})


def detect_format(values: list[str]) -> str | None:
    """The timestamp format that reads the most of these values (ISO first on a tie), so a
    day-first and a month-first file are told apart by the values that only one can read."""
    sample = [v for v in values if v][:500]
    if not sample:
        return None
    best, best_count = None, 0
    for fmt in FORMATS:
        count = sum(1 for v in sample if _try(v, fmt) is not None)
        if count > best_count:
            best, best_count = fmt, count
    offset = sum(1 for v in sample if (iso := _iso(v)) is not None and iso.tzinfo is not None)
    if offset > best_count:
        return ISO_OFFSET
    return best


def _try(value: str, fmt: str) -> datetime | None:
    try:
        return datetime.strptime(value, fmt)
    except ValueError:
        return None


def _iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _local(value: str, fmt: str | None, zone: ZoneInfo) -> datetime | None:
    """A timestamp read in the log's time zone (an explicit offset in the value wins)."""
    if not value or fmt is None:
        return None
    parsed = _iso(value) if fmt == ISO_OFFSET else _try(value, fmt)
    if parsed is None:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=zone)


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_utc(value: str, fmt: str | None, zone: ZoneInfo) -> str | None:
    """A timestamp in the log's time zone → ISO 8601 UTC ("2026-03-02T05:49:00Z"); None when it
    can't be read."""
    moment = _local(value, fmt, zone)
    return _utc(moment) if moment else None


def parse_log(
    rows: list[dict[str, str]],
    column_map: Mapping[str, str | None],
    timezone: str,
    role_of: Mapping[str, str | None],
    window: tuple[str, str] | None = None,
    timestamp_format: str | None = None,
    known_roles: Mapping[str, str] | None = None,
) -> ParsedLog:
    """Rows → events, and the validation report. `role_of` maps each resource value to a role
    name (or None: unknown role); a role column's value, where it names a role, is preferred.
    `window` is the requested date range in the log's own dates; `timestamp_format` is Eric's
    correction when the detected format is wrong (for example a file whose dates are all
    ambiguous).
    `known_roles` (lower-cased name or alias → role name), when given, keeps only roles the
    engagement has: any other value is an unknown role."""
    columns: dict[str, str] = {}
    attributes: list[str] = []
    for header, field in column_map.items():
        if field == Field.CASE_ATTRIBUTE.value:
            attributes.append(header)
        elif field is not None and field not in columns:
            columns[field] = header
    missing = [f for f in REQUIRED if f not in columns]
    zone = ZoneInfo(timezone)
    start_col, end_col = columns.get(Field.TIMESTAMP.value), columns.get(Field.END_TIMESTAMP.value)
    fmt = timestamp_format or (detect_format([r.get(start_col, "") for r in rows]) if start_col
                               else None)  # fmt: skip
    end_fmt = timestamp_format or (detect_format([r.get(end_col, "") for r in rows]) if end_col
                                   else None)  # fmt: skip

    def cell(row: dict[str, str], field: str) -> str:
        header = columns.get(field)
        return row.get(header, "").strip() if header else ""

    dropped = DroppedRows()
    events: list[LogEvent] = []
    seen: set[tuple[str, str, str]] = set()
    outside = 0
    if not missing:
        for row in rows:
            case, activity = cell(row, Field.CASE_ID.value), cell(row, Field.ACTIVITY.value)
            if not case or not activity:
                dropped.missing_case_or_activity += 1
                continue
            moment = _local(cell(row, Field.TIMESTAMP.value), fmt, zone)
            if moment is None:
                dropped.unparseable_time += 1
                continue
            start = _utc(moment)
            if (case, activity, start) in seen:
                dropped.duplicate += 1
                continue
            seen.add((case, activity, start))
            day = moment.astimezone(zone).date().isoformat()
            if window and not window[0] <= day <= window[1]:
                outside += 1
            role = _known(cell(row, Field.ROLE.value), known_roles) or _known(
                role_of.get(cell(row, Field.RESOURCE.value)), known_roles
            )
            events.append(LogEvent(
                case_id=case, activity=activity, start=start,
                end=to_utc(cell(row, Field.END_TIMESTAMP.value), end_fmt, zone),
                role=role or None, system=cell(row, Field.SYSTEM.value),
                attributes={h: row.get(h, "") for h in attributes},
            ))  # fmt: skip
    events.sort(key=lambda e: (e.case_id, e.start))
    return ParsedLog(events=events, report=_report(rows, events, dropped, missing, fmt, outside))


def _known(role: str | None, known_roles: Mapping[str, str] | None) -> str | None:
    """The role as the engagement names it, or None (unknown) when the engagement has no such
    role; without `known_roles`, any non-empty value."""
    if not role or known_roles is None:
        return role or None
    return known_roles.get(role.lower())


def _report(
    rows: list[dict[str, str]],
    events: list[LogEvent],
    dropped: DroppedRows,
    missing: list[str],
    fmt: str | None,
    outside: int,
) -> ValidationReport:
    per_case: dict[str, int] = {}
    for e in events:
        per_case[e.case_id] = per_case.get(e.case_id, 0) + 1
    lost = dropped.unparseable_time + dropped.missing_case_or_activity + dropped.duplicate
    share = round(lost / len(rows), 3) if rows else 0.0
    starts = [e.start for e in events]
    if missing:
        names = ", ".join(LABELS[f] for f in missing)
        refusal = f"The extract has no column for: {names}. Map one, or ask for a new extract."
    elif not rows:
        refusal = "The file has no rows."
    elif share > MAX_DROPPED:
        refusal = (f"{round(share * 100)}% of the rows can't be used (more than 20%); see why "
                   "below and ask for a corrected extract.")  # fmt: skip
    else:
        refusal = ""
    return ValidationReport(
        rows_read=len(rows),
        rows_kept=len(events),
        cases=len(per_case),
        activities=len({e.activity for e in events}),
        date_from=min(starts) if starts else None,
        date_to=max(starts) if starts else None,
        dropped=dropped,
        dropped_share=share,
        single_event_cases=sum(1 for n in per_case.values() if n == 1),
        unknown_role_events=sum(1 for e in events if e.role is None),
        outside_window=outside,
        timestamp_format=fmt or "",
        missing_columns=missing,
        refused=bool(refusal),
        refusal=refusal,
    )
