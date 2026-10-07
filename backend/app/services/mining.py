"""System records (PRD §3.13; R2): reading an event-log extract. Pure and deterministic; no
process-mining library (PM4Py is AGPL, constraint 19).

- `read_csv`: the header and rows of a CSV extract (UTF-8; comma, semicolon, tab or bar).
- `suggest_column_map`: each header → a B.40 field by name, for Eric to confirm or correct.
- `distinct_resources`: the resource values, for the role-mapping step; held in memory only.
- `parse_log`: rows → events and the plain-language validation report. A resource becomes a role
  here and is then gone: no event carries it (constraint 24).
- `metrics`: the §3.13.5 figures per activity, transition, case, variant and role (R4);
  `visible` keeps only groups of at least 5 cases.
"""

from __future__ import annotations

import csv
import io
import math
import re
import statistics
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from difflib import SequenceMatcher
from itertools import pairwise
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.enums import SystemLogColumn as Field
from app.domain.system_records import (
    DroppedRows,
    LogEvent,
    MetricRow,
    ParsedLog,
    ValidationReport,
)

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


# --- metrics (§3.13.5; R4) ----------------------------------------------------------------------

MINIMUM_CASES = 5  # §3.13.5: a metric is shown only when it rests on at least this many cases
TOP_VARIANTS = 10
UNKNOWN_ROLE = "Unknown role"
WAIT, NOT_SEPARABLE = "wait", "not_separable"
SCOPES = ("activity", "transition", "case", "variant", "role")


def _moment(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _minutes(earlier: str, later: str) -> float:
    return (_moment(later) - _moment(earlier)).total_seconds() / 60


def spread(values: list[float]) -> dict[str, float | int] | None:
    """Median and 90th percentile in minutes (one decimal), or None without values. The 90th
    percentile interpolates linearly between the closest ranks."""
    if not values:
        return None
    ordered = sorted(values)
    position = 0.9 * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    p90 = ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    return {"median_min": round(statistics.median(ordered), 1), "p90_min": round(p90, 1),
            "n": len(ordered)}  # fmt: skip


def _share(part: int, whole: int) -> float:
    return round(part / whole, 3) if whole else 0.0


def _row(scope: str, key: str, label: str, cases: int, metrics: dict[str, Any]) -> MetricRow:
    return MetricRow(scope=scope, key=key, label=label, case_count=cases, metrics=metrics)


def metrics(events: list[LogEvent], timezone: str) -> list[MetricRow]:
    """Every metric group of a log (§3.13.5), whatever its size; showing only groups of at least
    MINIMUM_CASES cases is the reader's job. `events` are sorted by case, then start."""
    zone = ZoneInfo(timezone)
    timed = bool(events) and all(e.end for e in events)
    basis = WAIT if timed else NOT_SEPARABLE
    by_case: dict[str, list[LogEvent]] = {}
    for e in events:
        by_case.setdefault(e.case_id, []).append(e)
    rows = _activity_rows(by_case, zone, timed, basis, _weeks(events, zone))
    rows += _transition_rows(by_case, timed, basis)
    variant_rows, exception_share = _variant_rows(by_case)
    rows.append(_case_row(events, by_case, timed, basis, exception_share, len(variant_rows)))
    rows += variant_rows[:TOP_VARIANTS]
    rows += _role_rows(by_case, timed)
    return rows


def _weeks(events: list[LogEvent], zone: ZoneInfo) -> int:
    """How many weeks the log covers: its first to last day, in whole weeks (at least 1)."""
    if not events:
        return 1
    days = {_moment(e.start).astimezone(zone).date() for e in events}
    return max(1, math.ceil(((max(days) - min(days)).days + 1) / 7))


def _activity_rows(by_case: dict[str, list[LogEvent]], zone: ZoneInfo, timed: bool,
                   basis: str, weeks: int) -> list[MetricRow]:  # fmt: skip
    events: Counter[str] = Counter()
    cases: dict[str, set[str]] = {}
    months: dict[str, dict[str, list[str]]] = {}  # activity → month → case IDs (one per event)
    work: dict[str, list[float]] = {}
    wait: dict[str, list[float]] = {}
    repeated: Counter[str] = Counter()
    for case, trail in by_case.items():
        seen: Counter[str] = Counter(e.activity for e in trail)
        repeated.update(a for a, n in seen.items() if n > 1)
        for i, e in enumerate(trail):
            events[e.activity] += 1
            cases.setdefault(e.activity, set()).add(case)
            month = _moment(e.start).astimezone(zone).strftime("%Y-%m")
            months.setdefault(e.activity, {}).setdefault(month, []).append(case)
            if timed and e.end:
                work.setdefault(e.activity, []).append(_minutes(e.start, e.end))
            if i:
                before = trail[i - 1]
                wait.setdefault(e.activity, []).append(
                    _minutes(before.end if timed and before.end else before.start, e.start)
                )
    rows = []
    for activity in sorted(events, key=lambda a: (-events[a], a)):
        n = len(cases[activity])
        shown, hidden = [], 0
        for month, ids in sorted(months[activity].items()):
            if len(set(ids)) >= MINIMUM_CASES:
                shown.append({"month": month, "events": len(ids), "cases": len(set(ids))})
            else:
                hidden += 1
        rows.append(_row("activity", activity, activity, n, {
            "activity": activity, "events": events[activity], "cases": n,
            "cases_per_week": round(n / weeks, 1),
            "cases_per_month": round(n / weeks * 52 / 12, 1), "months": shown,
            "months_too_few": hidden, "work": spread(work.get(activity, [])),
            "wait_before": spread(wait.get(activity, [])), "basis": basis,
            "rework_cases": repeated[activity], "rework_share": _share(repeated[activity], n),
        }))  # fmt: skip
    return rows


def _transition_rows(by_case: dict[str, list[LogEvent]], timed: bool,
                     basis: str) -> list[MetricRow]:  # fmt: skip
    elapsed: dict[tuple[str, str], list[float]] = {}
    cases: dict[tuple[str, str], set[str]] = {}
    handoffs: Counter[tuple[str, str]] = Counter()
    for case, trail in by_case.items():
        for a, b in pairwise(trail):
            pair = (a.activity, b.activity)
            start = a.end if timed and a.end else a.start
            elapsed.setdefault(pair, []).append(_minutes(start, b.start))
            cases.setdefault(pair, set()).add(case)
            if a.role and b.role and a.role != b.role:
                handoffs[pair] += 1
    rows = []
    for pair in sorted(elapsed, key=lambda p: (-len(elapsed[p]), p)):
        label = f"{pair[0]} → {pair[1]}"
        rows.append(_row("transition", label, label, len(cases[pair]), {
            "from_activity": pair[0], "to_activity": pair[1], "count": len(elapsed[pair]),
            "cases": len(cases[pair]), "elapsed": spread(elapsed[pair]), "basis": basis,
            "handoffs": handoffs[pair],
        }))  # fmt: skip
    return rows


def _variant_rows(by_case: dict[str, list[LogEvent]]) -> tuple[list[MetricRow], float]:
    """Every variant, most common first (ties by sequence), and the exception share."""
    sequences = Counter(tuple(e.activity for e in trail) for trail in by_case.values())
    total = len(by_case)
    ordered = sorted(sequences, key=lambda s: (-sequences[s], s))
    rows, covered = [], 0
    for rank, sequence in enumerate(ordered, start=1):
        covered += sequences[sequence]
        rows.append(_row("variant", str(rank), f"Variant {rank}", sequences[sequence], {
            "rank": rank, "activities": list(sequence), "cases": sequences[sequence],
            "share": _share(sequences[sequence], total), "cumulative_share": _share(covered, total),
        }))  # fmt: skip
    usual = sequences[ordered[0]] if ordered else 0
    return rows, _share(total - usual, total)


def _case_row(events: list[LogEvent], by_case: dict[str, list[LogEvent]], timed: bool,
              basis: str, exception_share: float, variants: int) -> MetricRow:  # fmt: skip
    cycle, rework, handoffs = [], 0, 0
    for trail in by_case.values():
        last = trail[-1].end if timed and trail[-1].end else max(e.start for e in trail)
        cycle.append(_minutes(trail[0].start, last))
        activities = [e.activity for e in trail]
        rework += len(set(activities)) < len(activities)
        handoffs += sum(1 for a, b in pairwise(trail)
                        if a.role and b.role and a.role != b.role)  # fmt: skip
    total = len(by_case)
    starts = [e.start for e in events]
    return _row("case", "all", "All cases", total, {
        "cases": total, "events": len(events), "activities": len({e.activity for e in events}),
        "date_from": min(starts) if starts else None, "date_to": max(starts) if starts else None,
        "cycle_time": spread(cycle), "basis": basis, "rework_cases": rework,
        "rework_share": _share(rework, total), "handoffs": handoffs,
        "handoffs_per_case": round(handoffs / total, 2) if total else 0.0,
        "variants": variants, "exception_share": exception_share,
    })  # fmt: skip


def _role_rows(by_case: dict[str, list[LogEvent]], timed: bool) -> list[MetricRow]:
    events: Counter[str] = Counter()
    cases: dict[str, set[str]] = {}
    activities: dict[str, set[str]] = {}
    work: dict[str, list[float]] = {}
    for case, trail in by_case.items():
        for e in trail:
            role = e.role or UNKNOWN_ROLE
            events[role] += 1
            cases.setdefault(role, set()).add(case)
            activities.setdefault(role, set()).add(e.activity)
            if timed and e.end:
                work.setdefault(role, []).append(_minutes(e.start, e.end))
    return [
        _row(
            "role",
            role,
            role,
            len(cases[role]),
            {
                "role": role,
                "events": events[role],
                "cases": len(cases[role]),
                "activities": sorted(activities[role]),
                "work": spread(work.get(role, [])),
            },
        )
        for role in sorted(events, key=lambda r: (-events[r], r))
    ]


def visible(rows: list[MetricRow]) -> tuple[list[MetricRow], int]:
    """The groups that may be shown (at least MINIMUM_CASES cases) and how many may not."""
    shown = [r for r in rows if r.case_count >= MINIMUM_CASES]
    return shown, len(rows) - len(shown)
