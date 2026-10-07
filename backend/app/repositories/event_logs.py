"""System logs and their events (PRD §3.5 `event_logs`, `events`; §3.13; R3): the only database
access. Events have no user column: only a role (constraint 24)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.domain.system_records import EventLogView, MetricRow, ValidationReport
from app.repositories.tables import Event, EventLog, MiningMetric


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


def event_count(session: Session, log_id: str) -> int:
    return int(session.scalar(select(func.count()).where(Event.log_id == log_id)) or 0)


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
