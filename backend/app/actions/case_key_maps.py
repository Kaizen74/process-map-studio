"""Case-key maps (API_CONTRACT.md → Case-key maps; PRD §3.13.1; R11c): linking two imported
logs whose systems give the same case different IDs, and the end-to-end time across both.
Deterministic, no AI. The file is read in memory; only the two case IDs per pair are stored."""

from __future__ import annotations

from typing import BinaryIO

from sqlalchemy.orm import Session, sessionmaker

from app.actions.engagements import ENGAGEMENT_MISSING, actor_name
from app.actions.event_logs import read_upload
from app.config import AppConfig
from app.db import session_scope
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.system_records import CaseKeyMapView, EventLogView
from app.repositories import audit
from app.repositories import case_key_maps as repo
from app.repositories import engagements as engagements_repo
from app.repositories import event_logs as logs_repo
from app.services import mining

Sessions = sessionmaker[Session]

BAD_LOGS = "Choose two different imported logs of this engagement."
NOT_LINKED = "Those two logs aren't linked."


def _view(
    session: Session, logs: dict[str, EventLogView], first: str, second: str, created_at: str
) -> CaseKeyMapView:
    pairs = repo.pairs(session, first, second)
    found_first, found_second, spans = mining.linked_cases(
        pairs, logs_repo.case_bounds(session, first), logs_repo.case_bounds(session, second)
    )
    both_timed = logs_repo.has_end_times(session, first) and logs_repo.has_end_times(
        session, second
    )
    shown = len(spans) >= mining.MINIMUM_CASES  # never a figure for fewer than 5 cases
    return CaseKeyMapView(
        from_log_id=first,
        from_log_name=logs[first].name,
        to_log_id=second,
        to_log_name=logs[second].name,
        pairs=len(pairs),
        from_found=found_first,
        to_found=found_second,
        linked_cases=len(spans),
        end_to_end=mining.spread(spans) if shown else None,
        basis="wait" if both_timed else "not_separable",
        minimum_cases=mining.MINIMUM_CASES,
        created_at=created_at,
    )


def _logs(session: Session, engagement_id: str) -> dict[str, EventLogView]:
    return {log.id: log for log in logs_repo.list_for(session, engagement_id)}


def upload_map(
    config: AppConfig, sessions: Sessions, engagement_id: str, *, stream: BinaryIO,
    from_log_id: str, to_log_id: str,
) -> Result[CaseKeyMapView]:  # fmt: skip
    """Link two imported logs with a file of case-ID pairs (replacing an earlier map)."""
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        logs = _logs(session, engagement_id)
        for field, log_id in (("from_log_id", from_log_id), ("to_log_id", to_log_id)):
            log = logs.get(log_id)
            if log is None or log.status != "imported" or from_log_id == to_log_id:
                return Err(ErrorKind.VALIDATION, BAD_LOGS, {"field": field})
        match read_upload(stream):
            case Err() as err:
                return err
            case Ok(value=content):
                pass
        match mining.read_extract(content):
            case Err() as err:
                return err
            case Ok(value=(headers, rows)):
                pass
        match mining.case_key_pairs(headers, rows):
            case Err() as err:
                return err
            case Ok(value=pairs):
                pass
        repo.replace(session, engagement_id, from_log_id, to_log_id, pairs)
        created = next(at for a, b, at in repo.linked(session, engagement_id)
                       if (a, b) == (from_log_id, to_log_id))  # fmt: skip
        view = _view(session, logs, from_log_id, to_log_id, created)
        audit.record(
            session, actor=actor_name(config), action="Linked system logs",
            target_type="event_log", target_id=from_log_id, engagement_id=engagement_id,
            after={"logs": [view.from_log_name, view.to_log_name], "pairs": view.pairs,
                   "linked_cases": view.linked_cases},
        )  # fmt: skip
        return Ok(view)


def list_maps(sessions: Sessions, engagement_id: str) -> Result[list[CaseKeyMapView]]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        logs = _logs(session, engagement_id)
        return Ok(
            [_view(session, logs, a, b, at) for a, b, at in repo.linked(session, engagement_id)]
        )


def delete_map(
    config: AppConfig, sessions: Sessions, engagement_id: str, from_log_id: str, to_log_id: str
) -> Result[None]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        logs = _logs(session, engagement_id)
        if from_log_id not in logs or to_log_id not in logs:
            return Err(ErrorKind.NOT_FOUND, NOT_LINKED)
        if repo.remove(session, from_log_id, to_log_id) == 0:
            return Err(ErrorKind.NOT_FOUND, NOT_LINKED)
        audit.record(
            session, actor=actor_name(config), action="Removed case-key map",
            target_type="event_log", target_id=from_log_id, engagement_id=engagement_id,
            before={"logs": [logs[from_log_id].name, logs[to_log_id].name]},
        )  # fmt: skip
        return Ok(None)
