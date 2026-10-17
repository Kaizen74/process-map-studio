"""The Variants tab's data (API_CONTRACT.md → system-variants; PRD §5.6, §3.13.4; criterion 89;
R8): each imported log's top variants read through Eric's confirmed matches and compared with the
version's As done and As documented views, its hidden work, and the steps with too few cases.
Advisory and read-only: nothing here changes the map.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import system_trace, versions
from app.db import session_scope
from app.domain.enums import ElementKind
from app.domain.graph import ElementRecord
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import View
from app.domain.system_records import (
    EventLogView,
    HiddenWorkItem,
    LogVariants,
    SystemVariants,
    VariantStep,
    VariantView,
    ViewFit,
)
from app.repositories import elements as map_repo
from app.repositories import event_logs as logs_repo
from app.repositories import versions as versions_repo
from app.services import mining
from app.services import system_variants as variant_rules
from app.services.system_variants import ViewMap

Sessions = sessionmaker[Session]

NOT_STEPS = {ElementKind.START.value, ElementKind.END.value}
VIEWS: tuple[View, ...] = ("done", "documented")


def _view_map(session: Session, version_id: str, view: View,
              keys: dict[str, str]) -> ViewMap:  # fmt: skip
    graph = versions.build_graph(session, version_id, view=view)
    if graph is None:
        return ViewMap(view, {}, [])
    labels = {keys[e.id]: e.label for e in graph.elements if e.id in keys}
    lines = [(keys[x.from_], keys[x.to]) for x in graph.edges if x.from_ in keys and x.to in keys]
    return ViewMap(view, labels, lines)


def _decisions(session: Session, log_id: str) -> tuple[dict[str, str], set[str]]:
    """Eric's confirmed matches (activity → stable key) and his hidden-work activities."""
    decided = [s for s in logs_repo.alignment(session, log_id) if s.confirmed and s.activity]
    matched = {s.activity: s.step_key for s in decided if s.status == "confirmed" and s.step_key}
    hidden = {s.activity for s in decided if s.status == "hidden_work"}
    return matched, hidden


def _main_role(session: Session, log_id: str, activity: str) -> str | None:
    rows = [r for r in logs_repo.activity_roles(session, log_id) if r[0] == activity and r[1]]
    return max(rows, key=lambda r: (r[2], r[1] or ""))[1] if rows else None


def _log(session: Session, log: EventLogView, steps: dict[str, ElementRecord],
         views: list[ViewMap]) -> LogVariants:  # fmt: skip
    matched, hidden = _decisions(session, log.id)
    labels = {k: e.label for k, e in steps.items()}
    case = next(iter(logs_repo.metrics(session, log.id, "case")), None)
    cases = case.case_count if case else 0
    shown, too_few = mining.visible(logs_repo.metrics(session, log.id, "variant"))
    variants = []
    for row in shown:
        m = row.metrics
        path = variant_rules.path(list(m["activities"]), matched, hidden)
        fits = {v.name: variant_rules.fit(path, v, labels) for v in views}
        variants.append(VariantView(
            rank=int(m["rank"]), cases=int(m["cases"]), share=float(m["share"]),
            cumulative_share=float(m["cumulative_share"]),
            path=[VariantStep(activity=p.activity,
                              element_id=steps[p.key].id if p.key in steps else None,
                              label=labels.get(p.key, "") if p.key else "", status=p.status)
                  for p in path],
            views={name: ViewFit(fits=ok, notes=notes) for name, (ok, notes) in fits.items()},
        ))  # fmt: skip
    activity_cases = {r.key: r.case_count for r in logs_repo.metrics(session, log.id, "activity")}
    moves = system_trace.moves(session, log.id)
    work = []
    for activity in sorted(hidden, key=lambda a: (-activity_cases.get(a, 0), a)):
        n = activity_cases.get(activity, 0)
        if n < mining.MINIMUM_CASES:
            continue
        after, before = variant_rules.neighbours(activity, moves, matched)
        work.append(HiddenWorkItem(
            activity=activity, cases=n, share=round(n / cases, 3) if cases else 0.0,
            role_id=_main_role(session, log.id, activity),
            after_element_id=steps[after].id if after in steps else None,
            after_label=labels.get(after, "") if after else "",
            before_element_id=steps[before].id if before in steps else None,
            before_label=labels.get(before, "") if before else "",
        ))  # fmt: skip
    return LogVariants(log_id=log.id, log_name=log.name, cases=cases, too_few=too_few,
                       variants=variants, hidden_work=work)  # fmt: skip


def _too_few_steps(session: Session, logs: list[EventLogView],
                   steps: dict[str, ElementRecord]) -> list[str]:  # fmt: skip
    """Steps with a confirmed match whose activities are recorded in fewer than 5 cases in every
    log (no figure is given for them)."""
    enough: set[str] = set()
    some: set[str] = set()
    for log in logs:
        matched, _ = _decisions(session, log.id)
        for key in set(matched.values()):
            some.add(key)
            names = {a for a, k in matched.items() if k == key}
            if logs_repo.step_figures(session, log.id, names)["cases"] >= mining.MINIMUM_CASES:
                enough.add(key)
    return [e.id for k, e in steps.items() if k in some - enough]


def variants_of(session: Session, version_id: str, engagement_id: str,
                views: tuple[View, ...] = VIEWS,
                first_only: bool = False) -> SystemVariants:  # fmt: skip
    """Every imported log's variants read through Eric's confirmed matches (also read by the
    Reality snapshot's routes, which ask only for the first log's fit with the As documented
    view: each view costs a graph build)."""
    elements = map_repo.elements(session, version_id)
    keys = {e.id: e.stable_key for e in elements}
    steps = {e.stable_key: e for e in elements
             if e.kind not in NOT_STEPS and e.review_status != "rejected"}  # fmt: skip
    logs = [log for log in logs_repo.list_for(session, engagement_id)
            if log.status == "imported"]  # fmt: skip
    if not logs:
        return SystemVariants(logs=[], too_few_steps=[])
    if first_only:
        logs = logs[:1]
    view_maps = [_view_map(session, version_id, view, keys) for view in views]
    return SystemVariants(
        logs=[_log(session, log, steps, view_maps) for log in logs],
        too_few_steps=_too_few_steps(session, logs, steps),
    )


def get_system_variants(sessions: Sessions, version_id: str) -> Result[SystemVariants]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions.VERSION_MISSING)
        return Ok(variants_of(session, version_id, version.engagement_id))
