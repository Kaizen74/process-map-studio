"""System logs and their events (PRD §3.5 `event_logs`, `events`; §3.13; R3): the only database
access. Events have no user column: only a role (constraint 24)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete as delete_rows
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.domain.system_records import AlignmentStored, EventLogView, MetricRow, ValidationReport
from app.repositories.tables import ActivityAlignment, Element, Event, EventLog, MiningMetric


def _view(row: EventLog) -> EventLogView:
    report = row.validation_report or None
    return EventLogView(
        id=row.id,
        engagement_id=row.engagement_id,
        name=row.name,
        system=row.system,
        timezone=row.timezone,
        window_start=row.window_start,
        window_end=row.window_end,
        status=row.status,
        column_map=dict(row.column_map or {}),
        validation_report=ValidationReport.model_validate(report) if report else None,
        approved_by_role=row.approved_by_role,
        approved_at=row.approved_at,
        created_at=row.created_at,
    )


def create(session: Session, engagement_id: str, fields: dict[str, Any]) -> EventLogView:
    row = EventLog(engagement_id=engagement_id, **fields)
    session.add(row)
    session.flush()
    return _view(row)


def get(session: Session, log_id: str) -> EventLogView | None:
    row = session.get(EventLog, log_id)
    return _view(row) if row else None


def list_for(session: Session, engagement_id: str) -> list[EventLogView]:
    rows = session.scalars(
        select(EventLog)
        .where(EventLog.engagement_id == engagement_id)
        .order_by(EventLog.created_at, EventLog.id)
    )
    return [_view(r) for r in rows]


def update(session: Session, log_id: str, fields: dict[str, Any]) -> EventLogView:
    row = session.get(EventLog, log_id)
    assert row is not None
    for name, value in fields.items():
        setattr(row, name, value)
    session.flush()
    return _view(row)


def delete(session: Session, log_id: str) -> bool:
    """The log; its events, metrics and alignment go with it (foreign keys cascade)."""
    row = session.get(EventLog, log_id)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def add_events(session: Session, log_id: str, events: list[dict[str, Any]]) -> int:
    """Write the events in one statement: case_id, activity, ts_start, ts_end, role_id and
    case_attributes per event."""
    if events:
        session.execute(insert(Event), [{"log_id": log_id, **e} for e in events])
    return len(events)


def delete_events(session: Session, log_id: str) -> None:
    """The log's events and figures (an import that didn't finish, R12)."""
    session.execute(delete_rows(Event).where(Event.log_id == log_id))
    session.execute(delete_rows(MiningMetric).where(MiningMetric.log_id == log_id))
    session.flush()


def event_count(session: Session, log_id: str) -> int:
    return int(session.scalar(select(func.count()).where(Event.log_id == log_id)) or 0)


def case_bounds(session: Session, log_id: str) -> dict[str, tuple[str, str]]:
    """Per case: its first event start and its last event end (or start), UTC stamps (R11c)."""
    rows = session.execute(
        select(
            Event.case_id,
            func.min(Event.ts_start),
            func.max(func.coalesce(Event.ts_end, Event.ts_start)),
        )
        .where(Event.log_id == log_id)
        .group_by(Event.case_id)
    )
    return {case: (str(start), str(end)) for case, start, end in rows}


def has_end_times(session: Session, log_id: str) -> bool:
    found = session.scalar(
        select(Event.id).where(Event.log_id == log_id, Event.ts_end.is_not(None)).limit(1)
    )
    return found is not None


def events(session: Session, log_id: str) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Event).where(Event.log_id == log_id).order_by(Event.case_id, Event.ts_start)
    )
    return [
        {"case_id": r.case_id, "activity": r.activity, "ts_start": r.ts_start,
         "ts_end": r.ts_end, "role_id": r.role_id, "case_attributes": r.case_attributes}
        for r in rows
    ]  # fmt: skip


def add_metrics(session: Session, log_id: str, rows: list[MetricRow]) -> None:
    """Store the log's metric groups; the order within a scope is kept as `order`."""
    if rows:
        session.execute(insert(MiningMetric), [
            {"log_id": log_id, "scope": r.scope, "key": r.key, "case_count": r.case_count,
             "metrics": {"label": r.label, "order": n, "values": r.metrics}}
            for n, r in enumerate(rows)
        ])  # fmt: skip


def metrics(session: Session, log_id: str, scope: str) -> list[MetricRow]:
    rows = session.scalars(
        select(MiningMetric).where(MiningMetric.log_id == log_id, MiningMetric.scope == scope)
    )
    ordered = sorted(rows, key=lambda r: int(r.metrics.get("order", 0)))
    return [
        MetricRow(scope=r.scope, key=r.key, label=str(r.metrics.get("label", r.key)),
                  case_count=r.case_count, metrics=dict(r.metrics.get("values", {})))
        for r in ordered
    ]  # fmt: skip


def activity_roles(session: Session, log_id: str) -> list[tuple[str, str | None, int, int]]:
    """(activity, role_id, events, cases) per activity and role: role-level counts only."""
    rows = session.execute(
        select(
            Event.activity, Event.role_id, func.count(), func.count(func.distinct(Event.case_id))
        )
        .where(Event.log_id == log_id)
        .group_by(Event.activity, Event.role_id)
    )
    return [(a, r, int(n), int(c)) for a, r, n, c in rows]


def activity_cases(session: Session, log_id: str) -> dict[str, int]:
    """Distinct cases per activity."""
    rows = session.execute(
        select(Event.activity, func.count(func.distinct(Event.case_id)))
        .where(Event.log_id == log_id)
        .group_by(Event.activity)
    )
    return {a: int(c) for a, c in rows}


def alignment(session: Session, log_id: str) -> list[AlignmentStored]:
    """Stored decisions and suggestions, each step given by its stable key."""
    rows = session.execute(
        select(ActivityAlignment, Element.stable_key)
        .outerjoin(Element, Element.id == ActivityAlignment.element_id)
        .where(ActivityAlignment.log_id == log_id)
        .order_by(ActivityAlignment.created_at, ActivityAlignment.id)
    )
    return [
        AlignmentStored(activity=r.activity, step_key=key, status=r.status, reason=r.reason,
                        confirmed=r.confirmed_at is not None)
        for r, key in rows
    ]  # fmt: skip


def replace_alignment(session: Session, log_id: str, activities: set[str], step_ids: set[str],
                      rows: list[dict[str, Any]]) -> None:  # fmt: skip
    """Remove the stored rows of these activities and the no-record rows of these steps (any
    version: matched by stable key), then add `rows`."""
    if activities:
        session.execute(delete_rows(ActivityAlignment).where(
            ActivityAlignment.log_id == log_id, ActivityAlignment.activity.in_(activities)
        ))  # fmt: skip
    if step_ids:
        keys = select(Element.stable_key).where(Element.id.in_(step_ids))
        same = select(Element.id).where(Element.stable_key.in_(keys))
        session.execute(delete_rows(ActivityAlignment).where(
            ActivityAlignment.log_id == log_id, ActivityAlignment.activity == "",
            ActivityAlignment.element_id.in_(same),
        ))  # fmt: skip
    for row in rows:
        session.add(ActivityAlignment(log_id=log_id, **row))
    session.flush()


def confirmed_matches(
    session: Session, engagement_id: str
) -> list[tuple[EventLogView, dict[str, str]]]:
    """Each imported log of the engagement with Eric's confirmed matches (activity → stable key);
    logs without any are left out."""
    out = []
    for log in list_for(session, engagement_id):
        if log.status != "imported":
            continue
        rows = session.execute(
            select(ActivityAlignment.activity, Element.stable_key)
            .join(Element, Element.id == ActivityAlignment.element_id)
            .where(ActivityAlignment.log_id == log.id, ActivityAlignment.status == "confirmed",
                   ActivityAlignment.confirmed_at.is_not(None))
        )  # fmt: skip
        matched = {activity: key for activity, key in rows if activity}
        if matched:
            out.append((log, matched))
    return out


def step_figures(session: Session, log_id: str, activities: set[str]) -> dict[str, int]:
    """Cases and events of a step's activities, and the cases where they occur more than once."""
    where = (Event.log_id == log_id, Event.activity.in_(activities))
    cases, events = session.execute(
        select(func.count(func.distinct(Event.case_id)), func.count()).where(*where)
    ).one()
    repeated = select(Event.case_id).where(*where).group_by(Event.case_id).having(func.count() > 1)
    rework = session.scalar(select(func.count()).select_from(repeated.subquery()))
    return {"cases": int(cases), "events": int(events), "rework_cases": int(rework or 0)}
