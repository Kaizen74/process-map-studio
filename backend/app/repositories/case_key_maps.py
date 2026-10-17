"""Case-key maps (PRD §3.5 `case_key_maps`, §3.13.1; R11c): pairs of case IDs linking two
imported logs. The only database access for them; a log's pairs go when the log is deleted
(foreign keys cascade)."""

from __future__ import annotations

from sqlalchemy import ColumnElement, CursorResult, delete, func, insert, or_, select
from sqlalchemy.orm import Session

from app.repositories.tables import CaseKeyMap


def _between(first: str, second: str) -> ColumnElement[bool]:
    return or_(
        (CaseKeyMap.from_log_id == first) & (CaseKeyMap.to_log_id == second),
        (CaseKeyMap.from_log_id == second) & (CaseKeyMap.to_log_id == first),
    )


def remove(session: Session, first: str, second: str) -> int:
    """The map between two logs, in either direction; how many pairs went."""
    result = session.execute(delete(CaseKeyMap).where(_between(first, second)))
    session.flush()
    return int(result.rowcount) if isinstance(result, CursorResult) else 0


def replace(
    session: Session, engagement_id: str, first: str, second: str, pairs: list[tuple[str, str]]
) -> None:
    """The pairs linking `first` to `second`, replacing any earlier map between the two."""
    remove(session, first, second)
    session.execute(
        insert(CaseKeyMap),
        [
            {"engagement_id": engagement_id, "from_log_id": first, "to_log_id": second,
             "from_case_id": a, "to_case_id": b}
            for a, b in pairs
        ],
    )  # fmt: skip
    session.flush()


def linked(session: Session, engagement_id: str) -> list[tuple[str, str, str]]:
    """(first log, second log, when linked) for each map of the engagement, oldest first."""
    rows = session.execute(
        select(CaseKeyMap.from_log_id, CaseKeyMap.to_log_id, func.min(CaseKeyMap.created_at))
        .where(CaseKeyMap.engagement_id == engagement_id)
        .group_by(CaseKeyMap.from_log_id, CaseKeyMap.to_log_id)
        .order_by(func.min(CaseKeyMap.created_at))
    )
    return [(a, b, str(at)) for a, b, at in rows]


def pairs(session: Session, first: str, second: str) -> list[tuple[str, str]]:
    rows = session.execute(
        select(CaseKeyMap.from_case_id, CaseKeyMap.to_case_id).where(
            CaseKeyMap.from_log_id == first, CaseKeyMap.to_log_id == second
        )
    )
    return [(a, b) for a, b in rows]
