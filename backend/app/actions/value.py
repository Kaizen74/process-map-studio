"""The value calculator (API_CONTRACT.md → Value calculator; PRD §3.14; criterion 90; R9b).

Role costs and the scenario assumptions are the engagement's; a step's own time and volume are
Eric's overrides on the draft. The figures are worked out on every read (no AI, nothing stored),
each with its evidence label; money is per step, phase and disposition, never per person.
"""

from __future__ import annotations

from typing import get_args

from sqlalchemy.orm import Session, sessionmaker

from app.actions import dispositions, redaction, system_trace
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.actions.settings import effective_settings
from app.config import SETTING_DEFAULTS, AppConfig
from app.db import session_scope
from app.domain.enums import ElementKind, ReviewStatus, StepDisposition, VersionState
from app.domain.models import (
    AssumptionRow,
    AssumptionsInput,
    RoleCostRow,
    RoleCostsInput,
    RoleCostsView,
    ScenarioView,
    StepValueView,
    ValueFigure,
    ValueOverrideInput,
    ValueTotalView,
    ValueView,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import View
from app.domain.system_records import SystemTraceItem
from app.repositories import audit
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import value as value_repo
from app.repositories import versions as versions_repo
from app.services import grounding
from app.services import value as rules
from app.services.value import Figure, StepInputs, StepValue

Sessions = sessionmaker[Session]

NOT_STEPS = {ElementKind.START.value, ElementKind.END.value}
ENGAGEMENT_MISSING = "That engagement doesn't exist."
NOT_A_ROLE = "Choose one of this engagement's roles."
BAD_COST = "Give an hourly cost from 0 to 100,000."
BAD_PCT = "Give a reduction from 0 to 100 percent."
NOT_A_DISPOSITION = "Choose one of the five dispositions."
BAD_TIME = "Give a time per case above 0 and up to 10,000 minutes."
BAD_VOLUME = "Give a volume above 0 and up to 1,000,000 a month."
NEEDS_NOTE = "Say where the figure comes from."
LONG_NOTE = "Keep the note to one line of up to {n} characters."
HIDDEN_NAME = "The note contains a name from your list of names to hide. Use the role instead."
BAD_VIEW = "Choose done or documented."
NOT_A_STEP = "The start and the end have no value."
NOT_A_DRAFT = "This version is published and can't be changed. Reopen it as a new draft."
VIEWS: tuple[str, ...] = get_args(View)


def _invalid(field: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field})


def _currency(config: AppConfig) -> str:
    match effective_settings(config):
        case Ok(value=values):
            return values.get("CURRENCY", SETTING_DEFAULTS["CURRENCY"]) or "SGD"
        case _:
            return SETTING_DEFAULTS["CURRENCY"]


def _note(session: Session, engagement_id: str, note: str, field: str, n: int) -> Err | None:
    if len(note) > n or "\n" in note:
        return _invalid(field, LONG_NOTE.format(n=n))
    terms = [t.term for t in redaction.name_replacements(session, engagement_id)]
    if note and grounding.scan_redaction_terms(note, terms):
        return _invalid(field, HIDDEN_NAME)
    return None


# --- Role costs and assumptions ----------------------------------------------------------------


def _role_costs(session: Session, engagement_id: str, currency: str) -> RoleCostsView:
    costs = value_repo.role_costs(session, engagement_id)
    roles = [r for r in engagements_repo.list_roles(session, engagement_id) if not r.is_system]
    roles.sort(key=lambda r: (r.lane_order is None, r.lane_order or 0, r.name))
    return RoleCostsView(currency=currency, rows=[
        RoleCostRow(role_id=r.id, role_name=r.name, hourly_cost=costs.get(r.id, (None, ""))[0],
                    note=costs.get(r.id, (None, ""))[1])
        for r in roles
    ])  # fmt: skip


def get_role_costs(config: AppConfig, sessions: Sessions,
                   engagement_id: str) -> Result[RoleCostsView]:  # fmt: skip
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok(_role_costs(session, engagement_id, _currency(config)))


def set_role_costs(config: AppConfig, sessions: Sessions, engagement_id: str,
                   body: RoleCostsInput) -> Result[RoleCostsView]:  # fmt: skip
    currency = _currency(config)
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        roles = {r.id: r.name for r in engagements_repo.list_roles(session, engagement_id)
                 if not r.is_system}  # fmt: skip
        for i, row in enumerate(body.rows):
            if row.role_id not in roles:
                return _invalid(f"rows[{i}].role_id", NOT_A_ROLE)
            if row.hourly_cost is not None and not 0 <= row.hourly_cost <= 100_000:
                return _invalid(f"rows[{i}].hourly_cost", BAD_COST)
            if bad := _note(session, engagement_id, row.note.strip(), f"rows[{i}].note", 200):
                return bad
        for row in body.rows:
            value_repo.set_role_cost(session, engagement_id, row.role_id, row.hourly_cost,
                                     currency, row.note.strip())  # fmt: skip
        if body.rows:
            audit.record(
                session, actor=actor_name(config), action="Set role costs",
                target_type="engagement", target_id=engagement_id, engagement_id=engagement_id,
                after={roles[r.role_id]: r.hourly_cost for r in body.rows},
            )  # fmt: skip
        return Ok(_role_costs(session, engagement_id, currency))


def _assumptions(session: Session, engagement_id: str) -> list[AssumptionRow]:
    stored = value_repo.assumptions(session, engagement_id)
    return [
        AssumptionRow(disposition=d, reduction_pct=stored[d][0], note=stored[d][1])
        if d in stored
        else AssumptionRow(disposition=d, reduction_pct=pct, note="", default=True)
        for d, pct in rules.DEFAULT_REDUCTION.items()
    ]


def get_assumptions(sessions: Sessions, engagement_id: str) -> Result[list[AssumptionRow]]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok(_assumptions(session, engagement_id))


def set_assumptions(config: AppConfig, sessions: Sessions, engagement_id: str,
                    body: AssumptionsInput) -> Result[list[AssumptionRow]]:  # fmt: skip
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        for i, row in enumerate(body.rows):
            if row.disposition not in rules.DEFAULT_REDUCTION:
                return _invalid(f"rows[{i}].disposition", NOT_A_DISPOSITION)
            if not 0 <= row.reduction_pct <= 100:
                return _invalid(f"rows[{i}].reduction_pct", BAD_PCT)
            if bad := _note(session, engagement_id, row.note.strip(), f"rows[{i}].note", 200):
                return bad
        for row in body.rows:
            value_repo.set_assumption(session, engagement_id, row.disposition,
                                      row.reduction_pct, row.note.strip())  # fmt: skip
        if body.rows:
            audit.record(
                session, actor=actor_name(config), action="Set value assumptions",
                target_type="engagement", target_id=engagement_id, engagement_id=engagement_id,
                after={r.disposition: r.reduction_pct for r in body.rows},
            )  # fmt: skip
        return Ok(_assumptions(session, engagement_id))


# --- The value of a version's steps ------------------------------------------------------------


def _measured(items: list[SystemTraceItem]) -> tuple[Figure | None, Figure | None]:
    """Time per case and volume per month from the busiest log matched to the step."""
    if not items:
        return None, None
    t = max(items, key=lambda i: (i.cases, i.log_name))
    volume = Figure(round(t.cases_per_month, 1), rules.MEASURED,
                    f"{t.log_name}: {t.cases_per_week:g} cases a week")  # fmt: skip
    work = (t.work or {}).get("median_min")
    if work is None or not t.cases:
        return None, volume
    per_case = t.events / t.cases
    source = f"{t.log_name}: median work {float(work):g} min, {per_case:.1f} times per case"
    time = Figure(round(float(work) * per_case, 1), rules.MEASURED, source)
    return time, volume


def _figure(value: float | None, label: str, source: str) -> Figure | None:
    return Figure(round(value, 1), label, source) if value is not None and value > 0 else None


def _out(f: Figure | None) -> ValueFigure | None:
    return ValueFigure(value=f.value, label=f.label, source=f.source) if f else None


def _total(t: rules.Total, phase_id: str | None = None, name: str = "") -> ValueTotalView:
    return ValueTotalView(phase_id=phase_id, name=name, hours_per_month=t.hours,
                          cost_per_month=t.cost, evidence=t.label, steps_counted=t.counted,
                          steps_missing=t.missing,
                          steps_without_cost=t.counted - t.costed)  # fmt: skip


def _value(config: AppConfig, session: Session, version_id: str, view: str) -> ValueView | None:
    version = versions_repo.get(session, version_id)
    graph = versions_action.build_graph(session, version_id, view=view)  # type: ignore[arg-type]
    if version is None or graph is None:
        return None
    records = {r.id: r for r in map_repo.elements(session, version_id)}
    disposed = {d.element_id: d for d in dispositions.views(session, version)}
    traces: dict[str, list[SystemTraceItem]] = {}
    for item in system_trace.items_for(session, version):
        traces.setdefault(item.element_id, []).append(item)
    costs = value_repo.role_costs(session, version.engagement_id)
    reductions = {
        a.disposition: a.reduction_pct for a in _assumptions(session, version.engagement_id)
    }
    roles = {r.id: r.name for r in graph.roles}
    phases = {p.id: p.name for p in graph.phases}
    values: list[tuple[StepValue, StepValueView]] = []
    for e in graph.elements:
        record = records.get(e.id)
        if e.kind in NOT_STEPS or record is None or e.review_status == ReviewStatus.REJECTED.value:
            continue
        time, volume = _measured(traces.get(e.id, []))
        stated = f"Stated: {e.time.text}" if e.time.text else "Stated work time"
        d = disposed.get(e.id)
        step = StepInputs(
            element_id=e.id, measured_time=time,
            estimated_time=_figure(e.time.work_min, rules.ESTIMATED, stated),
            override_time=_figure(record.time_override_min, rules.ASSUMED,
                                  f"Your figure: {record.value_override_note or ''}".strip()),
            measured_volume=volume,
            override_volume=_figure(record.volume_override_month, rules.ASSUMED,
                                    f"Your figure: {record.value_override_note or ''}".strip()),
            hourly_cost=costs[e.lane_role_id][0] if e.lane_role_id in costs else None,
            role_name=roles.get(e.lane_role_id or "", ""),
            disposition=(d.disposition or d.suggested) if d else StepDisposition.KEEP_HUMAN.value,
            chosen=bool(d and d.disposition),
        )  # fmt: skip
        v = rules.step_value(step, reductions)
        values.append((v, StepValueView(
            element_id=e.id, label=e.label, phase_id=e.phase_id,
            phase_name=phases.get(e.phase_id or "", ""), role_name=step.role_name,
            time=_out(v.time), volume=_out(v.volume), hours_per_month=v.hours,
            cost_per_month=v.cost, evidence=v.label, missing=v.missing,
            disposition=v.disposition, chosen=v.chosen, reduction_pct=v.reduction_pct,
            hours_released=v.hours_released, cost_released=v.cost_released,
        )))  # fmt: skip
    plain = [v for v, _ in values]
    by_phase = rules.totals(plain, {v.element_id: out.phase_id for v, out in values})
    overall = rules.Total()
    for v in plain:
        overall.add(v)
    scenario = rules.scenarios(plain)
    return ValueView(
        currency=_currency(config), view=view, potential=rules.POTENTIAL,
        steps=[out for _, out in values],
        phases=[_total(by_phase[p.id], p.id, p.name) for p in graph.phases if p.id in by_phase],
        totals=_total(overall),
        scenarios=[ScenarioView(disposition=d, reduction_pct=reductions[d], steps=int(s["steps"]),
                                hours_per_month=float(s["hours"]),
                                hours_released=float(s["hours_released"]),
                                cost_released=float(s["cost_released"]))
                   for d, s in scenario.items()],
    )  # fmt: skip


def _row(config: AppConfig, session: Session, version_id: str, element_id: str,
         view: str) -> StepValueView | None:  # fmt: skip
    found = _value(config, session, version_id, view)
    return next((s for s in found.steps if s.element_id == element_id), None) if found else None


def get_value(config: AppConfig, sessions: Sessions, version_id: str,
              view: str = "done") -> Result[ValueView]:  # fmt: skip
    if view not in VIEWS:
        return _invalid("view", BAD_VIEW)
    with session_scope(sessions) as session:
        found = _value(config, session, version_id, view)
        if found is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        return Ok(found)


def set_override(config: AppConfig, sessions: Sessions, element_id: str,
                 body: ValueOverrideInput) -> Result[StepValueView]:  # fmt: skip
    note = body.note.strip()
    if body.time_min is not None and not 0 < body.time_min <= 10_000:
        return _invalid("time_min", BAD_TIME)
    if body.volume_month is not None and not 0 < body.volume_month <= 1_000_000:
        return _invalid("volume_month", BAD_VOLUME)
    setting = body.time_min is not None or body.volume_month is not None
    if setting and not note:
        return _invalid("note", NEEDS_NOTE)
    with session_scope(sessions) as session:
        version_id = map_repo.element_version_id(session, element_id)
        version = versions_repo.get(session, version_id) if version_id else None
        record = map_repo.element(session, element_id)
        if version is None or record is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.ELEMENT_MISSING)
        if version.state != VersionState.DRAFT.value:
            return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
        if record.kind in NOT_STEPS:
            return _invalid("element_id", NOT_A_STEP)
        if bad := _note(session, version.engagement_id, note, "note", 300):
            return bad
        before = {"time_min": record.time_override_min,
                  "volume_month": record.volume_override_month,
                  "note": record.value_override_note or ""}  # fmt: skip
        after = {"time_min": body.time_min, "volume_month": body.volume_month,
                 "note": note if setting else ""}  # fmt: skip
        if before != after:
            map_repo.update_element(session, element_id, {
                "time_override_min": body.time_min, "volume_override_month": body.volume_month,
                "value_override_note": after["note"] or None,
            })  # fmt: skip
            audit.record(
                session, actor=actor_name(config), action="Set value override",
                target_type="element", target_id=element_id,
                engagement_id=version.engagement_id, version_id=version.id,
                before=before, after=after,
            )  # fmt: skip
        found = _value(config, session, version.id, "done")
        row = next((s for s in found.steps if s.element_id == element_id), None) if found else None
        if row is None:  # a step only in the documented view
            found = _value(config, session, version.id, "documented")
            row = (
                next((s for s in found.steps if s.element_id == element_id), None)
                if found
                else None
            )
        if row is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.ELEMENT_MISSING)
        return Ok(row)
