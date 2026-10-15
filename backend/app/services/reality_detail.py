"""The four Reality views that explain why the gaps happen (PRD §3.18.3, §5.12.3; P13c): Redline
(RV4), Where the time goes (RV5), Belief vs evidence (RV6) and Typical case (RV7). Pure and
deterministic: no AI, no database. Every figure goes through the snapshot's register, so a code,
a step's time or a measured value reads the same here as on every other view (RQ9).

Rules worth knowing (DECISIONS.md, P13c):
- Redline markups are the codes' practice types on the documented steps: D1 skipped, D2 added,
  D3 other order, D4 loop, D5 goes round, D6 off-system, D7 longer, D8 waits, D11 no record,
  D12 another role. Intent types (D13, D14) and process-level ones (D9, D10) are shown elsewhere.
  At most 6 markups are drawn (control exposures always); the rest are listed.
- Where the time goes works per column (phase): the manual's minutes, practice's work and wait,
  the designed part (practice work up to the manual's minutes) and the extra work beyond it.
- Belief vs evidence: a step whose official accounts state a time and whose time the system
  measures (at least 5 cases); believed = the median stated value, never one answer.
- Typical case: the most common route that differs from the documented one (else the most
  common), at least 5 cases; each event's time is the median of those cases; never one case.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.reality import (
    Availability,
    BeliefModel,
    BeliefRow,
    CaseEvent,
    CaseLane,
    CaseModel,
    CodeView,
    Column,
    Figure,
    Markup,
    RedlineModel,
    RedlinePage,
    RedlineStep,
    Tile,
    TimeCause,
    TimeColumn,
    TimeModel,
    ViewTable,
)
from app.services import discrepancies as rules
from app.services import reality_copy as copy
from app.services import verdicts as verdict_rules
from app.services.discrepancies import StepFacts
from app.services.reality_base import PROCESS, Figures, Inputs, RouteIn, blend, step_parts

MAX_MARKUPS = 6
MAX_STEPS_PER_ROW = 12
MAX_BELIEF_ROWS = 6
MAX_LANES = 6
MAX_TOOL_LANES = 4
MAX_EVENTS = 15
SYSTEM_LANE = "system"
OFF_SYSTEM = "off-system"
MARKUP_KINDS = {
    "D1": ("skipped", "Skipped"),
    "D2": ("added", "Added"),
    "D3": ("reorder", "In another order"),
    "D4": ("loop", "Loops back"),
    "D5": ("bypass", "Goes round"),
    "D6": ("off_system", "Off-system"),
    "D7": ("longer", "Takes longer"),
    "D8": ("wait", "Waits"),
    "D11": ("no_record", "No record"),
    "D12": ("owner", "Done by another role"),
}


@dataclass(frozen=True, slots=True)
class Part:
    """One view's computed parts, before its geometry and callouts."""

    headline: str
    availability: Availability
    table: ViewTable
    order: list[str]  # the codes its callouts follow, in order


def _available(state: str = "ready", key: str = "", action: str | None = None) -> Availability:
    return Availability(state=state, message=copy.AVAILABILITY[key] if key else "", action=action)


def _ordered(steps: Sequence[StepFacts]) -> list[StepFacts]:
    return sorted(steps, key=lambda s: s.order)


# --- RV4 Redline --------------------------------------------------------------------------------


def _anchor(key: str, inputs: Inputs, documented: Sequence[StepFacts]) -> str | None:
    """The documented step a markup sits on, or the last documented step before it."""
    by_key = {s.key: s for s in inputs.facts.steps}
    step = by_key.get(key)
    if step is not None and step.in_documented:
        return key
    if step is None:
        return None
    before = [d for d in documented if d.order < step.order]
    return before[-1].key if before else (documented[0].key if documented else None)


def _markup_keys(c: CodeView, inputs: Inputs, documented: Sequence[StepFacts]) -> list[str]:
    if c.location.kind == "activity":
        after = inputs.activity_after.get(c.location.keys[0], "")
        anchor = _anchor(after, inputs, documented) if after else None
        return [anchor] if anchor else []
    keys = [k for k in (_anchor(k, inputs, documented) for k in c.location.keys) if k]
    return list(dict.fromkeys(keys))


def redline(inputs: Inputs, codes: Sequence[CodeView], groups: Mapping[str, verdict_rules.Group],
            place: Mapping[str, str], columns: Sequence[Column],
            figures: Figures) -> tuple[RedlineModel, Part]:  # fmt: skip
    facts = inputs.facts
    documented = [s for s in _ordered(facts.steps) if s.in_documented]
    markups: list[Markup] = []
    seen: set[tuple[str, str]] = set()  # one markup per code and type (a code may find it twice)
    for c in sorted(codes, key=lambda c: c.rank):
        group = groups.get(c.code)
        if group is None:
            continue
        keys = _markup_keys(c, inputs, documented)
        for found in sorted(group.found, key=lambda f: verdict_rules.TYPE_ORDER.index(f.type)):
            if found.type not in MARKUP_KINDS or not keys or (c.code, found.type) in seen:
                continue
            seen.add((c.code, found.type))
            kind, word = MARKUP_KINDS[found.type]
            d = found.delta
            share = figures.add(f"{c.code}.{found.type}", d.value, d.unit, d.text, d.label,
                                "incidence" if d.unit == "pct" else None)  # fmt: skip
            markups.append(Markup(code=c.code, type=found.type, kind=kind, keys=keys,
                                  label=f"{word}: {c.title}", share=share,
                                  impact_class=c.impact_class, drawn=False,
                                  tool=found.detail.get("tool", "")))  # fmt: skip
    controls = [m for m in markups if m.impact_class == verdict_rules.CONTROL]
    others = [m for m in markups if m.impact_class != verdict_rules.CONTROL]
    for m in [*controls, *others[: max(0, MAX_MARKUPS - len(controls))]]:
        m.drawn = True
    by_code = {c.code: c for c in codes}
    steps, pills = [], []
    for s in documented:
        here = [c for c in codes if c.location.kind in ("step", "run", "order") and
                s.key in c.location.keys]  # fmt: skip
        minutes: Figure | None = None
        if s.documented_min is not None:
            minutes = figures.add(f"rv2.documented.{s.key}", s.documented_min, "min",
                                  copy.minutes(s.documented_min, signed=False),
                                  rules.DOCUMENTED)  # fmt: skip
        ghost = any("D1" in c.types for c in here)
        steps.append(RedlineStep(key=s.key, label=s.label, minutes=minutes, ghost=ghost,
                                 codes=[c.code for c in here]))  # fmt: skip
        extra = [c.minutes for c in here if c.minutes is not None]
        if extra:
            total = round(sum(f.value or 0.0 for f in extra), 1)
            pills.append(figures.add(f"rv4.pill.{s.key}", total, "min", copy.minutes(total),
                                     blend([f.label for f in extra])))  # fmt: skip
    pages = _pages(documented, place, columns)
    listed = list(dict.fromkeys(m.code for m in markups if not m.drawn))
    model = RedlineModel(pages=pages, steps=steps, markups=markups, pills=pills, listed=listed)
    if not documented:
        return model, Part(headline=copy.fill("rv4.none"),
                           availability=_available("missing", "rv4.no_documents",
                                                   "upload_documents"),
                           table=_redline_table(model), order=[])  # fmt: skip
    n_control = len({m.code for m in controls})
    if not markups:
        headline = copy.fill("rv4.same")
    elif n_control:
        headline = copy.fill("rv4.changes", changes=copy.count(len(markups), "change"),
                             controls=copy.count(n_control, "code"))  # fmt: skip
    else:
        headline = copy.fill("rv4.changes_plain", changes=copy.count(len(markups), "change"))
    order = [m.code for m in markups if m.drawn and m.code in by_code]
    return model, Part(headline=headline, availability=_available(), table=_redline_table(model),
                       order=list(dict.fromkeys(order)))  # fmt: skip


def _pages(documented: Sequence[StepFacts], place: Mapping[str, str],
           columns: Sequence[Column]) -> list[RedlinePage]:  # fmt: skip
    """One row of at most 12 documented steps, paged by phase beyond that (§3.18.2)."""
    if not documented:
        return []
    if len(documented) <= MAX_STEPS_PER_ROW:
        keys = [s.key for s in documented]
        return [RedlinePage(id="all", name="Every documented step", step_keys=keys)]
    names = {c.id: c.name for c in columns}
    runs: list[tuple[str, list[str]]] = []  # consecutive steps in one column
    for s in documented:
        column = place.get(s.key, PROCESS)
        if runs and runs[-1][0] == column:
            runs[-1][1].append(s.key)
        else:
            runs.append((column, [s.key]))
    pages: list[RedlinePage] = []
    seen: dict[str, int] = {}
    for column, keys in runs:
        for start in range(0, len(keys), MAX_STEPS_PER_ROW):
            n = seen[column] = seen.get(column, 0) + 1
            name = names.get(column, "Other steps") + (" (continued)" if n > 1 else "")
            page_id = column if n == 1 else f"{column}-{n}"
            pages.append(RedlinePage(id=page_id, name=name,
                                     step_keys=keys[start:start + MAX_STEPS_PER_ROW]))  # fmt: skip
    return pages


def _redline_table(model: RedlineModel) -> ViewTable:
    labels = {s.key: s.label for s in model.steps}
    rows = [[m.code, m.label, ", ".join(labels.get(k, k) for k in m.keys), m.share.text,
             m.share.label, "drawn" if m.drawn else "listed"] for m in model.markups]  # fmt: skip
    return ViewTable(columns=["Code", "Change", "On or after", "Share", "Label", "On the view"],
                     rows=rows)  # fmt: skip


# --- RV5 Where the time goes --------------------------------------------------------------------


def time(inputs: Inputs, codes: Sequence[CodeView], columns: Sequence[Column],
         place: Mapping[str, str], figures: Figures) -> tuple[TimeModel, Part]:  # fmt: skip
    facts = inputs.facts
    steps = _ordered(facts.steps)
    out: list[TimeColumn] = []
    complete = True
    for col in [c for c in columns if c.kind != PROCESS]:
        mine = [s for s in steps if place.get(s.key) == col.id]
        documented = [s for s in mine if s.in_documented]
        timed = [s.documented_min for s in documented if s.kind == "activity"]
        has_manual = bool(documented) and all(v is not None for v in timed)
        manual_value = sum(s.documented_min or 0.0 for s in documented)
        works = [p for s in mine if s.in_done for p in [step_parts(s)[0]] if p is not None]
        waits = [p for s in mine if s.in_done for p in [step_parts(s)[1]] if p is not None]
        col_complete = has_manual and all(step_parts(s)[0] is not None for s in mine
                                          if s.in_done and s.kind == "activity")  # fmt: skip
        complete = complete and col_complete
        fid = f"rv5.{{}}.{col.id}"
        manual = figures.add(fid.format("manual"), round(manual_value, 1), "min",
                             copy.minutes(manual_value, signed=False),
                             rules.DOCUMENTED) if has_manual else None  # fmt: skip
        work_value = round(sum(v for v, _ in works), 1)
        work = figures.add(fid.format("work"), work_value, "min",
                           copy.minutes(work_value, signed=False),
                           blend([lb for _, lb in works])) if works else None  # fmt: skip
        wait_value = round(sum(v for v, _ in waits), 1)
        wait = figures.add(fid.format("wait"), wait_value, "min",
                           copy.minutes(wait_value, signed=False),
                           blend([lb for _, lb in waits])) if waits else None  # fmt: skip
        designed = extra = None
        if manual is not None and work is not None:
            d = round(min(work_value, manual_value), 1)
            e = round(max(0.0, work_value - manual_value), 1)
            designed = figures.add(fid.format("designed"), d, "min",
                                   copy.minutes(d, signed=False), "mixed")  # fmt: skip
            extra = figures.add(fid.format("extra"), e, "min", copy.minutes(e), "mixed")
        out.append(TimeColumn(column_id=col.id, name=col.name, manual=manual, work=work,
                              wait=wait, designed=designed, extra=extra,
                              complete=col_complete))  # fmt: skip
    manual_total = practice_total = multiplier = None
    manuals = [c.manual for c in out if c.manual is not None]
    if manuals:
        v = round(sum(f.value or 0.0 for f in manuals), 1)
        manual_total = figures.add("rv5.manual_total", v, "min",
                                   copy.minutes(v, signed=False), rules.DOCUMENTED)  # fmt: skip
    practice = [f for c in out for f in (c.work, c.wait) if f is not None]
    if practice:
        v = round(sum(f.value or 0.0 for f in practice), 1)
        practice_total = figures.add("rv5.practice_total", v, "min",
                                     copy.minutes(v, signed=False),
                                     blend([f.label for f in practice]))  # fmt: skip
    if complete and manual_total and practice_total and manual_total.value:
        x = (practice_total.value or 0.0) / manual_total.value
        multiplier = figures.add("rv5.multiplier", round(x, 1), "x", copy.times(x), "mixed")
    causes = sorted((TimeCause(code=c.code, title=c.title, minutes=c.minutes) for c in codes
                     if c.minutes is not None and (c.minutes.value or 0) > 0),
                    key=lambda t: (-(t.minutes.value or 0.0), t.code))  # fmt: skip
    model = TimeModel(columns=out, manual_total=manual_total, practice_total=practice_total,
                      multiplier=multiplier, complete=complete, causes=causes)  # fmt: skip
    added = [(((c.extra.value or 0.0) if c.extra else 0.0) + ((c.wait.value or 0.0)
               if c.wait else 0.0), c) for c in out]  # fmt: skip
    best = max(added, key=lambda t: t[0], default=(0.0, None))
    if best[1] is None or best[0] <= 0:
        headline = copy.fill("rv5.none")
    elif best[1].wait and (best[1].wait.value or 0) > 0:
        headline = copy.fill("rv5.added", phase=best[1].name, added_min=f"{best[0]:.0f}",
                             wait_min=f"{best[1].wait.value or 0:.0f}")  # fmt: skip
    else:
        headline = copy.fill("rv5.added_work", phase=best[1].name, added_min=f"{best[0]:.0f}")
    availability = _available() if complete else _available("partial", "rv5.no_times", None)
    return model, Part(headline=headline, availability=availability, table=_time_table(model),
                       order=[t.code for t in causes])  # fmt: skip


def _time_table(model: TimeModel) -> ViewTable:
    def text(f: Figure | None) -> str:
        return f"{f.text} ({f.label})" if f is not None else "No time stated"

    rows = [[c.name, text(c.manual), text(c.work), text(c.wait), text(c.extra)]
            for c in model.columns]  # fmt: skip
    suffix = "" if model.complete else ", incomplete"
    rows.append(["Whole process", text(model.manual_total) + suffix,
                 text(model.practice_total) + suffix, "",
                 model.multiplier.text if model.multiplier else "incomplete"])  # fmt: skip
    return ViewTable(columns=["Column", "The manual", "Work in practice", "Waiting",
                              "Extra work"], rows=rows)  # fmt: skip


# --- RV6 Belief vs evidence ---------------------------------------------------------------------


def belief(inputs: Inputs, codes: Sequence[CodeView],
           figures: Figures) -> tuple[BeliefModel, Part]:  # fmt: skip
    facts = inputs.facts
    rows: list[BeliefRow] = []
    by_key = {k: c for c in codes for k in c.location.keys}
    compared = 0
    for s in _ordered(facts.steps):
        b = rules.belief(s)
        if b is None:
            continue
        compared += 1
        if b.factor < rules.BELIEF_FACTOR:  # the D10 threshold: a row is a belief gap
            continue
        n = min(inputs.official_sources.get(s.key, 1), max(inputs.interviews, 1))
        direction = "longer" if b.measured >= b.believed else "shorter"
        code = by_key.get(s.key)
        rows.append(BeliefRow(
            key=s.key, label=s.label,
            believed=figures.add(f"rv2.belief.{s.key}", b.believed, "min",
                                 copy.minutes(b.believed, signed=False), rules.STATED),
            measured=figures.add(f"rv6.measured.{s.key}", round(b.measured, 1), "min",
                                 copy.minutes(b.measured, signed=False), rules.MEASURED),
            gap=figures.add(f"rv6.gap.{s.key}", round(b.factor, 1), "x",
                            f"{copy.times(b.factor)} {direction}", rules.MEASURED),
            direction=direction,
            prevalence=f"stated in {copy.of(n, inputs.interviews, 'interview')}",
            code=code.code if code else None, impact_class=code.impact_class if code else None,
        ))  # fmt: skip
    rows.sort(key=lambda r: (-(r.gap.value or 0.0), r.key))
    rows = rows[:MAX_BELIEF_ROWS]
    model = BeliefModel(rows=rows, note=copy.fill("rv6.note"), method=copy.fill("rv6.method"))
    if not facts.total_cases:
        availability = _available("missing", "rv6.no_log", "import_log")
    elif not compared:
        availability = _available("missing", "rv6.no_belief", None)
    else:
        availability = _available()
    if rows:
        top = rows[0]
        headline = copy.fill("rv6.gap", step=top.label, measured=top.measured.text,
                             believed=top.believed.text)  # fmt: skip
    elif compared:
        headline = copy.fill("rv6.close", factor=copy.times(rules.BELIEF_FACTOR),
                             steps=copy.count(compared, "step"))  # fmt: skip
    else:
        headline = copy.fill("rv6.none")
    table = ViewTable(columns=["Step", "Believed", "Measured", "Gap", "How belief is known"],
                      rows=[[r.label, f"{r.believed.text} ({r.believed.label})",
                             f"{r.measured.text} ({r.measured.label})", r.gap.text,
                             r.prevalence] for r in rows])  # fmt: skip
    order = [r.code for r in rows if r.code]
    return model, Part(headline=headline, availability=availability, table=table,
                       order=list(dict.fromkeys(order)))  # fmt: skip


# --- RV7 Typical case ---------------------------------------------------------------------------


def typical_route(inputs: Inputs) -> RouteIn | None:
    """The most common route that differs from the documented one with at least 5 cases with
    timings, else the most common such route (§3.18.3); never fewer than 5 cases."""
    usable = [r for r in inputs.routes if len(r.timings) >= rules.MINIMUM_CASES]
    usable.sort(key=lambda r: (-r.cases, r.rank))
    differing = [r for r in usable if not r.fits_documented]
    chosen = differing or usable
    return chosen[0] if chosen else None


def _median(values: Sequence[float]) -> float:
    return round(float(statistics.median(values)), 1)


def case(inputs: Inputs, codes: Sequence[CodeView], figures: Figures,
         route_name: str) -> tuple[CaseModel, Part]:  # fmt: skip
    facts = inputs.facts
    route = typical_route(inputs)
    empty = CaseModel(route_name="", cases=0, label="", lanes=[], events=[],
                      designed_finish=None, promise=None, actual_finish=None, tiles=[])  # fmt: skip
    if route is None:
        return empty, Part(headline=copy.fill("rv7.records", tools=copy.count(0, "tool"),
                                              missing=copy.count(0, "step")),
                           availability=_available("missing", "rv7.no_log", "import_log"),
                           table=ViewTable(columns=[], rows=[]), order=[])  # fmt: skip
    assert len(route.timings) >= rules.MINIMUM_CASES  # a composite, never one case
    by_key = {s.key: s for s in facts.steps}
    labels = {s.key: s.label for s in facts.steps}
    system = inputs.system_name or "System of record"
    lanes: list[CaseLane] = [CaseLane(id=SYSTEM_LANE, name=system, kind="system")]
    events: list[CaseEvent] = []
    tools: list[str] = []
    positions = len(route.activities)
    for i in range(positions):
        key = route.positions[i] if i < len(route.positions) else ""
        name = labels.get(key, "") if key else route.activities[i]
        minutes = _median([t[i] for t in route.timings if len(t) > i])
        f = figures.add(f"rv7.event.{i}", minutes, "min", copy.minutes(minutes, signed=False),
                        rules.MEASURED)  # fmt: skip
        events.append(CaseEvent(key=key or None, label=name, lane_id=SYSTEM_LANE, minutes=f,
                                recorded=True))  # fmt: skip
        # Off-system steps the As done view places right after this one (D6, never timed).
        for line in facts.done_lines:
            nxt = by_key.get(line.target)
            if line.source != key or nxt is None or nxt.recorded is not False or not nxt.in_done:
                continue
            tool = nxt.tools[0] if nxt.tools else OFF_SYSTEM
            if tool not in tools:
                tools.append(tool)
            events.append(CaseEvent(key=nxt.key, label=nxt.label, lane_id=f"tool:{tool}",
                                    minutes=None, recorded=False))  # fmt: skip
    for tool in tools[:MAX_TOOL_LANES]:
        if tool == OFF_SYSTEM:  # no tool named for it: off-system work, never counted as a tool
            lanes.append(CaseLane(id=f"tool:{tool}", name="Off-system work", kind="off_system"))
        else:
            lanes.append(CaseLane(id=f"tool:{tool}", name=tool.capitalize(), kind="tool"))
    kept = {lane.id for lane in lanes}
    events = [e for e in events if e.lane_id in kept][:MAX_EVENTS]
    lanes = lanes[:MAX_LANES]
    finish = _median([t[-1] for t in route.timings if t])
    actual = figures.add("rv7.actual_finish", finish, "min", copy.minutes(finish, signed=False),
                         rules.MEASURED)  # fmt: skip
    designed_value = _designed(facts.steps)
    designed = figures.add("rv7.designed_finish", designed_value, "min",
                           copy.minutes(designed_value, signed=False),
                           rules.DOCUMENTED) if designed_value else None  # fmt: skip
    target = next((i for i in inputs.intents if i.metric == "cycle_time_min" and i.target), None)
    promise = figures.add("rv7.promise", target.target, "min",
                          copy.minutes(target.target, signed=False),
                          rules.TARGET) if target and target.target else None  # fmt: skip
    tool_lanes = sum(1 for lane in lanes if lane.kind == "tool")
    missing = sum(1 for e in events if not e.recorded)
    tiles = [Tile(figure=figures.add("rv7.tools", float(tool_lanes), "count",
                                     copy.count(tool_lanes, "tool"), rules.STATED),
                  caption="touched outside the system"),
             Tile(figure=figures.add("rv7.missing", float(missing), "count",
                                     copy.count(missing, "step"), rules.STATED),
                  caption="without a system record")]  # fmt: skip
    late_basis = promise or designed
    if late_basis is not None:
        late = finish - (late_basis.value or 0.0)
        tiles.insert(1, Tile(figure=figures.add("rv7.late", round(late, 1), "min",
                                                copy.minutes(late), "mixed"),
                             caption="after the promise" if promise else
                             "after the designed time"))  # fmt: skip
        slot = "rv7.promise" if promise else "rv7.designed"
        headline = copy.fill(slot, tools=copy.count(tool_lanes, "tool"),
                             late=copy.minutes(late, signed=False))  # fmt: skip
    else:
        headline = copy.fill("rv7.records", tools=copy.count(tool_lanes, "tool"),
                             missing=copy.count(missing, "step"))  # fmt: skip
    n = len(route.timings)
    model = CaseModel(route_name=route_name, cases=n,
                      label=copy.fill("rv7.label", cases=copy.count(n, "case")), lanes=lanes,
                      events=events, designed_finish=designed, promise=promise,
                      actual_finish=actual, tiles=tiles)  # fmt: skip
    lane_names = {lane.id: lane.name for lane in lanes}
    table = ViewTable(columns=["Event", "Where", "Minutes since the case started"],
                      rows=[[e.label, lane_names.get(e.lane_id, ""),
                             e.minutes.text if e.minutes else "no time recorded"]
                            for e in events])  # fmt: skip
    route_keys = {k for k in route.positions if k}
    order = [c.code for c in sorted(codes, key=lambda c: c.rank)
             if set(c.location.keys) & route_keys]  # fmt: skip
    return model, Part(headline=headline, availability=_available(), table=table, order=order)


def _designed(steps: Sequence[StepFacts]) -> float | None:
    documented = [s for s in steps if s.in_documented]
    activities = [s for s in documented if s.kind == "activity"]
    if not activities or any(s.documented_min is None for s in activities):
        return None
    return round(sum(s.documented_min or 0.0 for s in documented), 1)
