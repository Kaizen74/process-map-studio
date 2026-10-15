"""The Reality snapshot (PRD §3.18.1, §4 Intent and Reality; API_CONTRACT.md → Reality snapshot;
P13b): gathers one version's facts, keeps the snapshot while its inputs are unchanged, and
freezes it when the version is published. No AI call is made (constraint 26).

A draft's snapshot is worked out when asked and kept by `inputs_hash`; publishing freezes it
(when the Reality views switch is on; otherwise the first request for that published version
works it out and freezes it). A frozen snapshot is never worked out again.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import discrepancies as discrepancies_action
from app.actions import system_variants
from app.actions import versions as versions_action
from app.actions.settings import switched_on
from app.config import APP_VERSION, AppConfig
from app.db import session_scope
from app.domain.enums import SourceKind, VersionState
from app.domain.models import VersionView
from app.domain.reality import RealityFigures, RealitySnapshot
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import discrepancy_items as items_repo
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import event_logs as logs_repo
from app.repositories import reality_snapshots as snapshots_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import discrepancies as rules
from app.services import mining, reality
from app.services import reality_copy as copy
from app.services.reality_layout import LAYOUT_VERSION

Sessions = sessionmaker[Session]

DOCUMENTS = {SourceKind.SOP.value, SourceKind.MANUAL.value}
INTERVIEW = SourceKind.INTERVIEW_TRANSCRIPT.value
VERSIONS = (rules.REALITY_RULES_VERSION, copy.COPY_VERSION, LAYOUT_VERSION)


def enabled(config: AppConfig) -> bool:
    return switched_on(config, "REALITY_VIEWS_ENABLED")


def _data_label(session: Session, version: VersionView) -> str:
    draft = version.state == VersionState.DRAFT.value
    published_at, published_by = versions_repo.publication(session, version.id)
    return copy.data_label(draft, version.label, published_by, published_at[:10])


Routes = tuple[tuple[reality.RouteIn, ...], int, dict[str, str], str]
Timings = dict[tuple[str, ...], list[tuple[float, ...]]]
# A log's per-case timings, kept per import: an imported log's events never change (they are
# only removed when an import fails, and a new import gets a new `approved_at`), so reading every
# event again on each snapshot read is wasted work (DECISIONS 53).
_TIMINGS: dict[tuple[str, str], Timings] = {}
_TIMINGS_KEPT = 8


def _timings(session: Session, log_id: str, imported_at: str | None) -> Timings:
    if imported_at is None:
        return mining.case_timings(logs_repo.trails(session, log_id))
    key = (log_id, imported_at)
    if key not in _TIMINGS:
        if len(_TIMINGS) >= _TIMINGS_KEPT:
            _TIMINGS.pop(next(iter(_TIMINGS)))
        _TIMINGS[key] = mining.case_timings(logs_repo.trails(session, log_id))
    return _TIMINGS[key]


def _routes(session: Session, version: VersionView, keys: dict[str, str]) -> Routes:
    found = system_variants.variants_of(session, version.id, version.engagement_id,
                                        views=("documented",), first_only=True)  # fmt: skip
    if not found.logs:
        return (), 0, {}, ""
    log = found.logs[0]  # the discrepancy engine reads the first log too
    stored = logs_repo.get(session, log.log_id)
    timings = _timings(session, log.log_id, stored.approved_at if stored else None)
    routes = tuple(
        reality.RouteIn(
            rank=v.rank, cases=v.cases, share=v.share,
            fits_documented=v.views["documented"].fits if "documented" in v.views else False,
            keys=tuple(keys.get(p.element_id or "", "") for p in v.path
                       if p.status != "hidden_work"),
            hidden=tuple(p.activity for p in v.path if p.status == "hidden_work"),
            activities=tuple(p.activity for p in v.path),
            positions=tuple(keys.get(p.element_id or "", "") for p in v.path),
            timings=tuple(timings.get(tuple(p.activity for p in v.path), ())),
        )
        for v in log.variants
    )  # fmt: skip
    after = {w.activity: keys.get(w.after_element_id or "", "") for w in log.hidden_work}
    return routes, log.too_few, after, stored.system if stored else ""


def _cycle(session: Session, version: VersionView) -> float | None:
    logs = [log for log in logs_repo.list_for(session, version.engagement_id)
            if log.status == "imported"]  # fmt: skip
    if not logs:
        return None
    case = next(iter(logs_repo.metrics(session, logs[0].id, "case")), None)
    spread = (case.metrics.get("cycle_time") or {}) if case else {}
    median = spread.get("median_min") if isinstance(spread, dict) else None
    return float(median) if median is not None and case and case.case_count >= 5 else None


def gather(session: Session, version: VersionView) -> reality.Inputs:
    """Everything the snapshot is worked out from (and only that: `inputs_hash` names it). The
    map's graphs are built once for the whole gathering (DECISIONS 53)."""
    session.info[versions_action.GRAPH_MEMO] = {}
    try:
        return _gather(session, version)
    finally:
        session.info.pop(versions_action.GRAPH_MEMO, None)


def _gather(session: Session, version: VersionView) -> reality.Inputs:
    facts, confirmed = discrepancies_action.gather(session, version)
    view = discrepancies_action.discrepancies_of(session, version, facts)  # gives new codes
    evaluations = {e.intent_id: e.result for e in view.intents}
    items = {i.location_key: reality.ItemIn(item_id=i.id, code=i.code, title=i.title,
                                            verdict_decided=i.verdict_decided,
                                            verdict_note=i.verdict_note)
             for i in items_repo.for_engagement(session, version.engagement_id)}  # fmt: skip
    elements = map_repo.elements(session, version.id)
    keys = {e.id: e.stable_key for e in elements}
    phases = map_repo.phases(session, version.id)
    phase_ids = {p.name: p.id for p in phases}
    step_phase = {e.stable_key: e.phase_id or "" for e in elements}
    on_step = {i.intent_id: i.step_keys for i in facts.intents}
    intents = tuple(
        reality.IntentIn(
            intent_id=i.id, kind=i.kind, text=i.text, scope=i.scope,
            step_keys=tuple(on_step.get(i.id, ())),
            phase_id=phase_ids.get(i.phase_name or "") if i.scope == "phase" else None,
            metric=i.metric, comparator=i.comparator, target=i.target_value, unit=i.unit,
            result=evaluations.get(i.id, "unknown"),
        )
        for i in confirmed
    )  # fmt: skip
    routes, too_few, after, system_name = _routes(session, version, keys)
    kinds = [(k, status) for _, k, status in sources_repo.kinds(session, version.engagement_id)]
    engagement = engagements_repo.get(session, version.engagement_id)
    volumes = [s.per_month for s in facts.steps if s.per_month]
    return reality.Inputs(
        version_id=version.id, process_name=engagement.name if engagement else "",
        draft=version.state == VersionState.DRAFT.value,
        data_label=_data_label(session, version), facts=facts,
        phases=tuple(reality.PhaseIn(p.id, p.name, p.sort_order) for p in phases),
        step_phase=step_phase, routes=routes, routes_other=too_few, intents=intents,
        items=items,
        documents=sum(1 for k, s in kinds if k in DOCUMENTS and s == "ready"),
        interviews=sum(1 for k, s in kinds if k == INTERVIEW and s == "ready"),
        official_sources={s.key: s.official_sources for s in facts.steps if s.official_sources},
        activity_after=after, volume=max(volumes) if volumes else None,
        cycle_min=_cycle(session, version), system_name=system_name,
        starts_outside=bool(engagement and engagement.trigger_external),
        ends_outside=bool(engagement and engagement.end_point_external),
    )  # fmt: skip


def snapshot_of(session: Session, version: VersionView) -> RealitySnapshot:
    """The version's snapshot: the frozen one, the kept one while its inputs are unchanged, or a
    fresh one (frozen at once for a published version)."""
    stored = snapshots_repo.get(session, version.id)
    if stored is not None and stored.frozen:
        return RealitySnapshot.model_validate(stored.payload)
    inputs = gather(session, version)
    digest = reality.inputs_hash(inputs)
    if (
        stored is not None
        and stored.inputs_hash == digest
        and stored.app_version == APP_VERSION
        and (stored.payload.get("rules_version"), stored.payload.get("copy_version"),
             stored.payload.get("layout_version")) == VERSIONS
    ):  # fmt: skip
        return RealitySnapshot.model_validate(stored.payload)
    frozen = version.state != VersionState.DRAFT.value
    snapshot = reality.build(inputs, APP_VERSION, frozen=frozen)
    snapshots_repo.save(session, version.id, snapshots_repo.Stored(
        payload=snapshot.model_dump(mode="json"), inputs_hash=digest,
        rules_version=rules.REALITY_RULES_VERSION, app_version=APP_VERSION, frozen=frozen,
    ))  # fmt: skip
    return snapshot


def freeze(session: Session, version: VersionView) -> None:
    """Publishing: work the snapshot out under the published label and freeze it."""
    snapshot_of(session, version)


def get_reality(sessions: Sessions, version_id: str) -> Result[RealitySnapshot]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        return Ok(snapshot_of(session, version))


# --- what Leadership reads from the snapshot (G17) ----------------------------------------------


def leadership_figures(session: Session, version: VersionView) -> RealityFigures:
    snapshot = snapshot_of(session, version)
    return RealityFigures(data_label=snapshot.data_label, tiles=snapshot.tiles)
