"""Matching an imported log's activities to the current map's steps (API_CONTRACT.md → Alignment
of log activities to map steps; PRD §3.13.4; criterion 86; R5a).

The deterministic pass (`services/log_alignment.propose`) is worked out on every read and never
stored. Stored rows are Claude's suggestions (unconfirmed) and Eric's decisions (confirmed). Only
confirmed rows are ever used by the map (R5b). A stored row names its step by element, read back
by stable key, so a decision survives a new map version.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.actions import lenses, redaction
from app.actions.engagements import actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import AlignmentStatus, ElementKind, ReviewStatus
from app.domain.models import NameReplacement
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.system_records import (
    AlignmentInput,
    AlignmentRow,
    AlignmentStored,
    AlignmentSummary,
    AlignmentView,
    EventLogView,
    SuggestStarted,
)
from app.pipeline import sr_align
from app.pipeline.context import ai_context
from app.repositories import audit
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import event_logs as repo
from app.repositories import jobs as jobs_repo
from app.repositories import versions as versions_repo
from app.services import log_alignment as matching
from app.services.log_alignment import ActivityInfo, StepInfo

Sessions = sessionmaker[Session]
Enqueue = Callable[[str], None]

ALIGN_JOB = "event_log_alignment"
PROPOSED = AlignmentStatus.PROPOSED.value
CONFIRMED = AlignmentStatus.CONFIRMED.value
HIDDEN_WORK = AlignmentStatus.HIDDEN_WORK.value
NO_RECORD = AlignmentStatus.NO_SYSTEM_RECORD.value
NOT_STEPS = {ElementKind.START.value, ElementKind.END.value}

LOG_MISSING = "That system log doesn't exist."
NOT_IMPORTED = "Import the log first: its figures are worked out during the import."
NO_MAP = "Draft the map first: the log's activities are matched to its steps."
NOTHING_TO_SUGGEST = "Every activity already has a match or a decision."
NOT_IN_LOG = "That activity isn't in the log."
NOT_A_STEP = "Choose a step of the current map."
BAD_STATUS = "Choose confirmed, hidden_work or no_system_record."
SHAPE = {
    CONFIRMED: "A confirmed match needs an activity of the log and a step of the map.",
    HIDDEN_WORK: "Hidden work is an activity of the log with no step.",
    NO_RECORD: "No system record is a step of the map with no activity.",
}
HAS_RECORD = "{step} has a system record: {activity} is matched to it."
NO_MATCH = "No step shares its words."
NO_ACTIVITY = "No system activity is matched to it."
UNEXPECTED = (
    "Something went wrong while asking Claude for matches. Nothing was saved. Try again, or use "
    "Copy details to report it."
)
SUGGESTED = "Claude suggested {n} {matches}."
LEFT_OUT = (
    " {n} {suggestions} left out: {it} named an activity or step that isn't in the log or on the "
    "map."
)


@dataclass
class _Map:
    """The log, the current map's steps and what is stored, read once per request."""

    log: EventLogView
    version_id: str
    activities: list[ActivityInfo]  # most events first
    steps: list[StepInfo]  # map order
    ids: dict[str, str]  # stable key → element ID (current version)
    stored: list[AlignmentStored]

    def label(self, key: str | None) -> str:
        return next((s.label for s in self.steps if s.key == key), "")

    def key_of(self, element_id: str | None) -> str | None:
        return next((k for k, i in self.ids.items() if i == element_id), None)


def _invalid(message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": "rows"})


def _conflict(code: str, message: str) -> Err:
    return Err(ErrorKind.CONFLICT, message, api_code=code)


def _activities(session: Session, log_id: str, role_names: dict[str, str]) -> list[ActivityInfo]:
    events: Counter[str] = Counter()
    by_role: dict[str, Counter[str]] = {}
    for activity, role_id, n, _ in repo.activity_roles(session, log_id):
        events[activity] += n
        if role_id and role_id in role_names:
            by_role.setdefault(activity, Counter())[role_names[role_id]] += n
    cases = repo.activity_cases(session, log_id)

    def usual(activity: str) -> str | None:
        counts = by_role.get(activity)
        return min(counts, key=lambda r: (-counts[r], r)) if counts else None

    return [ActivityInfo(name=a, events=events[a], cases=cases.get(a, 0), role=usual(a))
            for a in sorted(events, key=lambda a: (-events[a], a))]  # fmt: skip


def _load(sessions: Sessions, log_id: str) -> Result[_Map]:
    with session_scope(sessions) as session:
        log = repo.get(session, log_id)
        if log is None:
            return Err(ErrorKind.NOT_FOUND, LOG_MISSING)
        if log.status != "imported":
            return _conflict("NOT_IMPORTED", NOT_IMPORTED)
        map_id = versions_repo.current_map_id(session, log.engagement_id)
        if map_id is None:
            return _conflict("NO_MAP", NO_MAP)
        role_names = {r.id: r.name for r in engagements_repo.list_roles(session, log.engagement_id)}
        rejected = ReviewStatus.REJECTED.value
        elements = [e for e in map_repo.elements(session, map_id)
                    if e.kind not in NOT_STEPS and e.review_status != rejected]  # fmt: skip
        activities = _activities(session, log_id, role_names)
        stored = repo.alignment(session, log_id)
    terms: dict[str, list[str]] = {}
    match lenses.get_glossary(sessions, map_id):
        case Ok(value=entries):
            for entry in entries:
                for label in entry.steps:
                    terms.setdefault(label, []).append(entry.term)
        case Err():
            pass
    steps = [StepInfo(key=e.stable_key, label=e.label, kind=e.kind,
                      lane_role=role_names.get(e.lane_role_id or ""),
                      terms=tuple(terms.get(e.label, [])))
             for e in elements]  # fmt: skip
    ids = {e.stable_key: e.id for e in elements}
    return Ok(_Map(log, map_id, activities, steps, ids, stored))


def _table(m: _Map) -> AlignmentView:
    """The app's proposals, Claude's suggestions and Eric's decisions as one table."""
    proposals = matching.propose(m.activities, m.steps)
    stored = {s.activity: s for s in m.stored if s.activity}
    rows: list[AlignmentRow] = []
    for a in m.activities:
        s = stored.get(a.name)
        usable = s is not None and (s.status == HIDDEN_WORK or s.step_key in m.ids)
        if s is not None and usable:
            key = s.step_key if s.status != HIDDEN_WORK else None
            status = (
                HIDDEN_WORK if s.status == HIDDEN_WORK else (CONFIRMED if s.confirmed else PROPOSED)
            )
            rows.append(AlignmentRow(
                activity=a.name, element_id=m.ids.get(key or ""), element_label=m.label(key),
                status=status, confirmed=s.confirmed, reason=s.reason,
                proposed_by="eric" if s.confirmed else "claude", events=a.events, cases=a.cases,
            ))  # fmt: skip
        elif a.name in proposals:
            p = proposals[a.name]
            rows.append(AlignmentRow(
                activity=a.name, element_id=m.ids[p.key], element_label=m.label(p.key),
                status=PROPOSED, confirmed=False, reason=p.reason, proposed_by="app",
                events=a.events, cases=a.cases,
            ))  # fmt: skip
        else:
            rows.append(AlignmentRow(
                activity=a.name, element_id=None, element_label="", status=HIDDEN_WORK,
                confirmed=False, reason=NO_MATCH, proposed_by="app", events=a.events,
                cases=a.cases,
            ))  # fmt: skip
    matched = {r.element_id for r in rows if r.element_id}
    no_record = {s.step_key: s for s in m.stored if not s.activity and s.status == NO_RECORD}
    for step in m.steps:
        decided = no_record.get(step.key)
        if decided is None and m.ids[step.key] in matched:
            continue
        rows.append(AlignmentRow(
            activity="", element_id=m.ids[step.key], element_label=step.label, status=NO_RECORD,
            confirmed=decided is not None and decided.confirmed,
            reason=decided.reason if decided else NO_ACTIVITY,
            proposed_by="eric" if decided else "app", events=0, cases=0,
        ))  # fmt: skip
    activity_rows = [r for r in rows if r.activity]
    summary = AlignmentSummary(
        activities=len(m.activities),
        matched=sum(1 for r in activity_rows if r.element_id),
        hidden_work=sum(1 for r in activity_rows if r.status == HIDDEN_WORK),
        no_system_record=sum(1 for r in rows if r.status == NO_RECORD),
        waiting=sum(1 for r in rows if not r.confirmed),
    )
    return AlignmentView(log_id=m.log.id, version_id=m.version_id, rows=rows, summary=summary)


def get_alignment(sessions: Sessions, log_id: str) -> Result[AlignmentView]:
    match _load(sessions, log_id):
        case Err() as err:
            return err
        case Ok(value=m):
            return Ok(_table(m))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def set_alignment(config: AppConfig, sessions: Sessions, log_id: str,
                  body: AlignmentInput) -> Result[AlignmentView]:  # fmt: skip
    """Eric's decisions: each replaces any earlier decision or suggestion for its activity (or,
    for no system record, its step)."""
    match _load(sessions, log_id):
        case Err() as err:
            return err
        case Ok(value=m):
            pass
    names = {a.name for a in m.activities}
    element_ids = set(m.ids.values())
    current = {r.activity: r for r in _table(m).rows if r.activity}
    for choice in body.rows:
        if choice.status not in SHAPE:
            return _invalid(BAD_STATUS)
        if choice.activity and choice.activity not in names:
            return _invalid(NOT_IN_LOG)
        if choice.element_id is not None and choice.element_id not in element_ids:
            return _invalid(NOT_A_STEP)
        needs = {CONFIRMED: (True, True), HIDDEN_WORK: (True, False), NO_RECORD: (False, True)}
        if needs[choice.status] != (bool(choice.activity), choice.element_id is not None):
            return _invalid(SHAPE[choice.status])
    # The confirmed matches once these decisions apply: none may point at a no-record step.
    matched = {r.activity: r.element_id for r in current.values()
               if r.confirmed and r.status == CONFIRMED}  # fmt: skip
    for choice in body.rows:
        if choice.activity:
            matched.pop(choice.activity, None)
            if choice.status == CONFIRMED:
                matched[choice.activity] = choice.element_id
    for choice in body.rows:
        if choice.status == NO_RECORD:
            taken = next((a for a, e in matched.items() if e == choice.element_id), None)
            if taken is not None:
                step = m.label(m.key_of(choice.element_id))
                return _invalid(HAS_RECORD.format(step=step, activity=taken))
    now = _now()
    rows, lines = [], []
    for choice in body.rows:
        same = current.get(choice.activity)
        reason = same.reason if same and same.element_id == choice.element_id else ""
        rows.append({"activity": choice.activity, "element_id": choice.element_id,
                     "status": choice.status, "reason": reason, "confirmed_at": now})  # fmt: skip
        step = m.label(m.key_of(choice.element_id))
        lines.append(f"{choice.activity} → {step}" if choice.status == CONFIRMED
                     else f"{choice.activity} → hidden work" if choice.status == HIDDEN_WORK
                     else f"{step} → no system record")  # fmt: skip
    activities = {c.activity for c in body.rows if c.activity}
    # A step newly matched loses any earlier "no system record" decision.
    steps = {c.element_id for c in body.rows if c.element_id}
    with session_scope(sessions) as session:
        repo.replace_alignment(session, log_id, activities, {s for s in steps if s}, rows)
        audit.record(
            session, actor=actor_name(config), action="Confirmed system alignment",
            target_type="event_log", target_id=log_id, engagement_id=m.log.engagement_id,
            after={"rows": lines},
        )  # fmt: skip
    return get_alignment(sessions, log_id)


# --- Claude's pass (SR_align) -----------------------------------------------------------------


def _unmatched(m: _Map) -> list[ActivityInfo]:
    """Activities still without a step and without Eric's decision."""
    waiting = {r.activity for r in _table(m).rows
               if r.activity and not r.confirmed
               and (r.status == HIDDEN_WORK or r.proposed_by == "claude")}  # fmt: skip
    return [a for a in m.activities if a.name in waiting]


def start_suggest(sessions: Sessions, log_id: str, enqueue: Enqueue) -> Result[SuggestStarted]:
    match _load(sessions, log_id):
        case Err() as err:
            return err
        case Ok(value=m):
            pass
    if not _unmatched(m):
        return _conflict("NOTHING_TO_SUGGEST", NOTHING_TO_SUGGEST)
    with session_scope(sessions) as session:
        job = jobs_repo.create(
            session, engagement_id=m.log.engagement_id, job_type=ALIGN_JOB, target_id=log_id
        )
    enqueue(job.id)
    return Ok(SuggestStarted(job_id=job.id, log_id=log_id))


def _hidden(
    m: _Map, unmatched: list[ActivityInfo], names: list[NameReplacement],
    glossary: list[dict[str, str]],
) -> tuple[sr_align.AlignInput, dict[str, str]]:  # fmt: skip
    """What Claude sees, with hidden names replaced, and each sent activity name → the real one."""
    sent = {redaction.hide(a.name, names): a.name for a in unmatched}
    data = sr_align.AlignInput(
        activities=[ActivityInfo(redaction.hide(a.name, names), a.events, a.cases, a.role)
                    for a in unmatched],
        steps=[StepInfo(s.key, redaction.hide(s.label, names), s.kind, s.lane_role)
               for s in m.steps],
        glossary=glossary,
    )  # fmt: skip
    return data, sent


def run_suggest(config: AppConfig, sessions: Sessions, job_id: str) -> Result[str]:
    """The alignment job: Claude's suggestions, checked, stored as unconfirmed proposals."""
    with session_scope(sessions) as session:
        job = jobs_repo.get(session, job_id)
    match _load(sessions, (job.target_id or "") if job else ""):
        case Err() as err:
            return err
        case Ok(value=m):
            pass
    unmatched = _unmatched(m)
    if not unmatched:
        return Ok(NOTHING_TO_SUGGEST)
    match ai_context(config):
        case Err() as err:
            return err
        case Ok(value=ctx):
            pass
    with session_scope(sessions) as session:
        names = redaction.name_replacements(session, m.log.engagement_id)
    glossary: list[dict[str, str]] = []
    match lenses.get_glossary(sessions, m.version_id):
        case Ok(value=entries):
            glossary = [{"term": e.term, "plain_meaning": e.plain_meaning} for e in entries]
        case Err():
            pass
    data, sent = _hidden(m, unmatched, names, glossary)
    match sr_align.suggest(sessions, ctx, data, job_id):
        case Err() as err:
            return err
        case Ok(value=suggestions):
            pass
    kept, left_out = matching.check_suggestions(suggestions, sent, m.ids)
    rows = [{"activity": sent[s.activity], "element_id": m.ids[s.key], "status": PROPOSED,
             "reason": s.reason, "confirmed_at": None} for s in kept]  # fmt: skip
    with session_scope(sessions) as session:
        repo.replace_alignment(session, m.log.id, {a.name for a in unmatched}, set(), rows)
    message = SUGGESTED.format(n=len(kept), matches="match" if len(kept) == 1 else "matches")
    if left_out:
        message += LEFT_OUT.format(
            n=left_out,
            suggestions="suggestion was" if left_out == 1 else "suggestions were",
            it="it" if left_out == 1 else "they",
        )
    return Ok(message)
