"""The Reality views' snapshot (PRD §3.18, §5.12; P13b): every figure, code, headline and the
geometry of Glance (RV1), Reality stack (RV2) and Fix or keep (RV3), worked out by fixed rules
from one version's facts. Pure and deterministic: no AI, no database, no clock. The same inputs
give a byte-identical snapshot (`inputs_hash` names them).

Rules worth knowing (DECISIONS.md, P13b):
- The codes, impact classes, hours and suggested verdicts are the discrepancy engine's
  (`services/verdicts`), so a code reads the same here as on `GET /discrepancies`.
- A code's extra minutes a case are its measured hours a month over the process's cases a month;
  without a measured figure, the stated wait, the stated extra time (D7) or the added step's
  stated time. A column's minutes and hours are the sums of its codes' figures.
- A step's minutes are work plus wait: measured where the log measures them, else stated.
- "n of N steps practised as documented": documented steps also in the As done view with no
  practice discrepancy at them (a design gap is about the manual, not practice).
- Routes come from the log's variants as read through Eric's confirmed matches; every variant
  fitting the As documented view joins one As documented route.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.reality import (
    Availability,
    Band,
    Callout,
    Chips,
    CodeEvidence,
    CodeVerdict,
    CodeView,
    Column,
    EvidenceSummary,
    Figure,
    FixModel,
    FixView,
    GlanceModel,
    GlanceView,
    Legend,
    LegendImpact,
    LegendLine,
    Lens,
    LocationView,
    Placed,
    Quadrant,
    RealitySnapshot,
    RealityViews,
    Route,
    SnapshotIntent,
    StackCell,
    StackItem,
    StackModel,
    StackView,
    Tile,
    ViewTable,
)
from app.services import discrepancies as rules
from app.services import reality_copy as copy
from app.services import reality_layout as layout
from app.services import verdicts as verdict_rules
from app.services.discrepancies import Facts, StepFacts

MAX_COLUMNS = 7
MAX_TILES = 5
MAX_RIBBONS = 7
MAX_HIGHLIGHTED = 5
MAX_HIGHLIGHTED_CONTROLS = 2
MAX_CALLOUTS = 3
MAX_CIRCLES = 8
DECIDE_FIRST = 6
ROUTE_SHARE = 0.05  # §3.17.3: a route below 5% of cases joins "Other" (unless a control exposure)
CODIFY_SHOWN = {"codify", "correct", "rewrite"}
PRACTICE_TYPES = frozenset(f"D{n}" for n in range(1, 13))  # every type but the D13/D14 intent ones
ROUTE_TYPES = frozenset({"D1", "D2", "D3", "D4", "D5", "D6"})
PROCESS = "process"
NO_HOURS = "Needs system records"


# --- inputs (gathered by `actions/reality`) -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class PhaseIn:
    id: str
    name: str
    order: int


@dataclass(frozen=True, slots=True)
class RouteIn:
    """One log variant read through Eric's matches: its step keys ("" for an unmatched
    activity) and hidden-work activities, and whether it fits the As documented view."""

    rank: int
    cases: int
    share: float
    fits_documented: bool
    keys: tuple[str, ...]
    hidden: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IntentIn:
    intent_id: str
    kind: str
    text: str
    scope: str  # step · phase · process
    step_keys: tuple[str, ...]
    phase_id: str | None
    metric: str | None
    comparator: str | None
    target: float | None
    unit: str | None
    result: str  # met · not_met · unknown


@dataclass(frozen=True, slots=True)
class ItemIn:
    item_id: str
    code: str
    title: str
    verdict_decided: str | None
    verdict_note: str


@dataclass(frozen=True, slots=True)
class Inputs:
    version_id: str
    process_name: str
    draft: bool
    data_label: str
    facts: Facts
    phases: tuple[PhaseIn, ...]
    step_phase: Mapping[str, str]  # step key → phase id ("" for none)
    routes: tuple[RouteIn, ...]
    routes_other: int  # variants too rare to show (under 5 cases)
    intents: tuple[IntentIn, ...]  # confirmed statements, in the order they were added
    items: Mapping[str, ItemIn]  # by location key
    documents: int  # SOPs and manuals
    interviews: int  # ready interview transcripts
    official_sources: Mapping[str, int]  # step key → interviews whose official account times it
    activity_after: Mapping[str, str]  # hidden-work activity → the step key it follows
    volume: float | None  # the process's cases a month (measured)
    cycle_min: float | None  # median case cycle time (measured)


def inputs_hash(inputs: Inputs) -> str:
    text = json.dumps(dataclasses.asdict(inputs), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- figures ------------------------------------------------------------------------------------


class Figures:
    """Every figure of the snapshot by its ID: one value and one text everywhere (RQ9)."""

    def __init__(self) -> None:
        self.by_id: dict[str, Figure] = {}

    def add(self, fid: str, value: float | None, unit: str, text: str, label: str,
            percent_type: str | None = None) -> Figure:  # fmt: skip
        figure = Figure(id=fid, value=value, unit=unit, text=text, label=label,
                        percent_type=percent_type)  # fmt: skip
        known = self.by_id.get(fid)
        assert known is None or known == figure, f"two values for {fid}"
        self.by_id[fid] = figure
        return figure


def _blend(labels: Sequence[str]) -> str:
    found = set(labels)
    return found.pop() if len(found) == 1 else rules.MEASURED if not found else "mixed"


def step_minutes(s: StepFacts) -> tuple[float | None, str]:
    """A step's minutes a case (work and wait) and their label: measured where measured."""
    parts: list[tuple[float, str]] = []
    measured = s.time if s.time and s.time.cases >= rules.MINIMUM_CASES else None
    before = s.wait_before if s.wait_before and s.wait_before.cases >= rules.MINIMUM_CASES else None
    if s.stated_wait is not None and measured is not None:
        work = (s.done_min, rules.STATED) if s.done_min is not None else None
        wait: tuple[float, str] | None = (measured.median, rules.MEASURED)
    else:
        work = (measured.median, rules.MEASURED) if measured else (
            (s.done_min, rules.STATED) if s.done_min is not None else None)  # fmt: skip
        wait = (before.median, rules.MEASURED) if before else (
            (s.stated_wait, rules.STATED) if s.stated_wait is not None else None)  # fmt: skip
    parts = [p for p in (work, wait) if p is not None]
    if not parts:
        return None, ""
    return round(sum(v for v, _ in parts), 1), _blend([lb for _, lb in parts])


# --- codes --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Coded:
    group: verdict_rules.Group
    item: ItemIn
    impact: str
    hours: float


def _number(code: str) -> int:
    return int(code[1:]) if code[1:].isdigit() else 0


def coded_groups(inputs: Inputs) -> tuple[list[Coded], list[verdict_rules.Group]]:
    """The drawn locations with their codes (in code order) and the process-level ones."""
    facts = inputs.facts
    found = [f for f in rules.detect(facts) if f.shown]
    groups = verdict_rules.group(found, facts)
    coded = []
    for g in groups:
        item = inputs.items.get(g.location_key)
        if g.kind == PROCESS or item is None:
            continue
        impact = verdict_rules.impact(g, facts) or verdict_rules.WORKAROUND
        coded.append(Coded(g, item, impact, verdict_rules.hours(g, facts)))
    coded.sort(key=lambda c: _number(c.item.code))
    return coded, [g for g in groups if g.kind == PROCESS]


def _rank(coded: Sequence[Coded]) -> dict[str, int]:
    ordered = sorted(coded, key=lambda c: (verdict_rules.IMPACT_ORDER.index(c.impact), -c.hours,
                                           _number(c.item.code)))  # fmt: skip
    return {c.item.code: n for n, c in enumerate(ordered, start=1)}


def _code_minutes(c: Coded, inputs: Inputs, figures: Figures) -> Figure | None:
    fid = f"{c.item.code}.minutes"
    if c.hours > 0 and inputs.volume:
        value = round(c.hours * 60 / inputs.volume, 1)
        return figures.add(fid, value, "min", f"{copy.minutes(value)} a case", rules.MEASURED)
    by_key = {s.key: s for s in inputs.facts.steps}
    for f in c.group.found:
        if f.type in ("D7", "D8") and f.delta.unit == "min" and f.delta.value is not None:
            return figures.add(fid, f.delta.value, "min", f"{copy.minutes(f.delta.value)} a case",
                               f.delta.label)  # fmt: skip
        step = by_key.get(f.keys[0]) if f.keys else None
        if f.type == "D2" and step is not None:
            stated, label = step_minutes(step)
            if stated is not None:
                return figures.add(fid, stated, "min", f"{copy.minutes(stated)} a case", label)
    return None


def _evidence(c: Coded, facts: Facts) -> CodeEvidence:
    steps = [s for s in facts.steps if s.key in c.group.keys]
    cases = [f.cases for f in c.group.found if f.cases is not None]
    measured = any(f.delta.label == rules.MEASURED for f in c.group.found)
    system = max(cases) if cases and measured else None
    if c.group.kind == "activity":
        system = system or next((w.cases for w in facts.hidden if w.activity == c.group.keys[0]),
                                None)  # fmt: skip
    documents = max((s.documents for s in steps), default=0)
    interviews = max((s.described_in for s in steps), default=0)
    return CodeEvidence(
        documents=documents, interviews=interviews, system_cases=system,
        chips=Chips(documents=documents > 0, interviews=interviews > 0, system=bool(system)),
        sentence=copy.evidence_sentence(documents, interviews, system),
    )  # fmt: skip


def _verdict(c: Coded, facts: Facts) -> CodeVerdict:
    suggested, reason = verdict_rules.verdict(c.group, facts)
    decided = c.item.verdict_decided
    return CodeVerdict(suggested=suggested, decided=decided, shown=decided or suggested,
                       status="confirmed" if decided else "suggested", reason=reason,
                       note=c.item.verdict_note)  # fmt: skip


def _h(c: CodeView) -> float:
    """A code's hours a month (0 without system records)."""
    return c.hours.value or 0.0 if c.hours is not None else 0.0


def _delta(c: Coded, figures: Figures) -> Figure:
    first = sorted(c.group.found, key=lambda f: verdict_rules.TYPE_ORDER.index(f.type))[0]
    d = first.delta
    return figures.add(f"{c.item.code}.delta", d.value, d.unit, d.text, d.label,
                       "incidence" if d.unit == "pct" else None)  # fmt: skip


# --- columns ------------------------------------------------------------------------------------


def _step_columns(inputs: Inputs) -> tuple[list[Column], dict[str, str]]:
    """The shared axis before trimming: phases, or up to 7 usual-route steps (§3.18.2)."""
    steps = sorted(inputs.facts.steps, key=lambda s: s.order)
    phases = sorted(inputs.phases, key=lambda p: p.order)
    if len(phases) >= 2:
        columns = [Column(id=p.id, name=p.name, kind="phase", step_keys=[]) for p in phases]
        own = {s.key: inputs.step_phase.get(s.key, "") for s in steps}
    else:
        usual = [s for s in steps if s.usual_route and s.in_done][:MAX_COLUMNS]
        columns = [Column(id=s.key, name=s.label, kind="step", step_keys=[]) for s in usual]
        own = {s.key: s.key for s in usual}
    ids = {c.id for c in columns}
    place: dict[str, str] = {}
    last = columns[0].id if columns else PROCESS
    for s in steps:
        if own.get(s.key) in ids:
            last = own[s.key]
        place[s.key] = last if own.get(s.key) not in ids else own[s.key]
    for c in columns:
        c.step_keys = [s.key for s in steps if place[s.key] == c.id]
    return columns, place


def _code_column(c: Coded, place: Mapping[str, str], inputs: Inputs) -> str:
    g = c.group
    if g.kind == "activity":
        after = inputs.activity_after.get(g.keys[0], "")
        return place.get(after, PROCESS)
    keys = [k for k in g.keys if k in place]
    return place[keys[0]] if keys else PROCESS


def _trim(columns: list[Column], codes: Sequence[CodeView]) -> tuple[list[Column], str]:
    """At most 7 columns: those with a control exposure, then those losing most hours."""
    if len(columns) <= MAX_COLUMNS:
        return columns, ""
    control = {c.column_id for c in codes if c.control}
    lost: dict[str, float] = {}
    for c in codes:
        lost[c.column_id or ""] = lost.get(c.column_id or "", 0.0) + _h(c)
    order = {c.id: n for n, c in enumerate(columns)}
    ranked = sorted(columns, key=lambda c: (c.id not in control, -lost.get(c.id, 0.0), order[c.id]))
    kept = {c.id for c in ranked[: max(MAX_COLUMNS, len(control))]}
    hidden = len(columns) - len(kept)
    note = copy.fill("columns.hidden", n=copy.count(hidden, "phase"))
    return [c for c in columns if c.id in kept], note


# --- tiles (§3.18.5) ----------------------------------------------------------------------------


def _practised(inputs: Inputs, codes: Sequence[CodeView]) -> tuple[int, int]:
    documented = [s for s in inputs.facts.steps if s.in_documented]
    touched = {k for c in codes if set(c.types) & PRACTICE_TYPES for k in c.location.keys}
    n = sum(1 for s in documented if s.in_done and s.key not in touched)
    return n, len(documented)


def _documented_share(inputs: Inputs) -> float | None:
    if not inputs.routes:
        return None
    return sum(r.share for r in inputs.routes if r.fits_documented)


def _designed_total(facts: Facts) -> float | None:
    """The manual's designed minutes a case: only when every documented activity states a time
    (an incomplete total is a missing input, never an estimate)."""
    documented = [s for s in facts.steps if s.in_documented]
    activities = [s for s in documented if s.kind == "activity"]
    if not activities or any(s.documented_min is None for s in activities):
        return None
    return sum(s.documented_min or 0.0 for s in documented)


def _done_total(inputs: Inputs) -> tuple[float | None, str]:
    if inputs.cycle_min is not None:
        return inputs.cycle_min, rules.MEASURED
    values = [step_minutes(s) for s in inputs.facts.steps if s.in_done and s.usual_route]
    known = [(v, lb) for v, lb in values if v is not None]
    if not known:
        return None, ""
    return sum(v for v, _ in known), _blend([lb for _, lb in known])


def _beyond(s: StepFacts) -> tuple[float | None, str]:
    """A step's minutes to set against its documented time: the wait when its accounts state one
    (as D7 and D14 compare it), else its work and wait."""
    if s.stated_wait is not None:
        wait = rules.measured_wait(s)
        if wait is not None and wait.cases >= rules.MINIMUM_CASES:
            return wait.median, rules.MEASURED
        return s.stated_wait, rules.STATED
    return step_minutes(s)


def _hours_beyond(facts: Facts) -> tuple[float, str] | None:
    """The sum of max(0, done - documented minutes) times volume, over steps with a measured
    volume and a documented time (an added step's documented time is 0)."""
    total, labels = 0.0, []
    for s in facts.steps:
        if not s.in_done or not s.per_month:
            continue
        done, label = _beyond(s)
        designed = s.documented_min if s.in_documented else 0.0
        if done is None or designed is None:
            continue
        total += max(0.0, done - designed) * s.per_month / 60
        labels.append({"stated": "estimated"}.get(label, label))
    if not labels:
        return None
    return round(total, 1), _blend(labels)


def tiles(inputs: Inputs, codes: Sequence[CodeView], process: Sequence[verdict_rules.Group],
          groups: Mapping[str, verdict_rules.Group], figures: Figures) -> list[Tile]:  # fmt: skip
    facts = inputs.facts
    out: list[Tile] = []
    share = _documented_share(inputs)
    if share is not None:
        f = figures.add("rv1.documented_share", round(100 * share, 1), "pct", copy.pct(share),
                        rules.MEASURED, "variant_share")  # fmt: skip
        out.append(Tile(figure=f, caption="of cases follow the manual"))
    else:
        n, total = _practised(inputs, codes)
        if total:
            f = figures.add("rv1.practised", float(n), "count", f"{n} of {total}", rules.STATED)
            out.append(Tile(figure=f, caption="steps practised as documented"))
    designed = _designed_total(facts)
    done, _ = _done_total(inputs)
    if designed and done is not None:
        x = done / designed
        f = figures.add("rv1.multiplier", round(x, 1), "x", copy.times(x), "mixed")
        out.append(Tile(figure=f, caption="the designed time a case"))
    controls = [(fd.incidence, fd.type, c) for c in codes for fd in _found_of(c, groups)
                if fd.type in ("D5", "D11") and fd.incidence is not None]  # fmt: skip
    if controls:
        incidence, kind, c = max(controls, key=lambda t: (t[0] or 0.0, -_number(t[2].code)))
        value = incidence or 0.0
        f = figures.add("rv1.control_share", round(100 * value, 1), "pct", copy.pct(value),
                        rules.MEASURED, "incidence")  # fmt: skip
        words = "without a record" if kind == "D11" else "go round a control"
        out.append(Tile(figure=f, caption=f"of cases {words} ({c.code})"))
    target = next((i for i in facts.intents if i.met_share is not None), None)
    if target is not None and target.met_share is not None:
        f = figures.add("rv1.target_met", round(100 * target.met_share, 1), "pct",
                        copy.pct(target.met_share), target.label or rules.MEASURED,
                        "incidence")  # fmt: skip
        out.append(Tile(figure=f, caption="of cases meet a confirmed target"))
    beyond = _hours_beyond(facts)
    if beyond is not None:
        f = figures.add("rv1.hours_beyond", beyond[0], "h", copy.hours(beyond[0]), beyond[1])
        out.append(Tile(figure=f, caption="beyond the designed time"))
    beliefs = [fd for g in process for fd in g.found if fd.type == "D10" and fd.delta.value]
    if beliefs:
        top = max(beliefs, key=lambda fd: fd.delta.value or 0.0)
        value = top.delta.value or 0.0
        f = figures.add("rv1.belief_gap", value, "x", copy.times(value), rules.MEASURED)
        out.append(Tile(figure=f, caption="between belief and measured time"))
    return out[:MAX_TILES]


def _found_of(c: CodeView, groups: Mapping[str, verdict_rules.Group]) -> Sequence[rules.Found]:
    g = groups.get(c.code)
    return g.found if g is not None else ()


# --- RV1 Glance ---------------------------------------------------------------------------------


def _route_codes(route: RouteIn, inputs: Inputs, codes: Sequence[CodeView]) -> list[str]:
    by_key = {s.key: s for s in inputs.facts.steps}
    seen: dict[str, int] = {}
    for k in route.keys:
        if k:
            seen[k] = seen.get(k, 0) + 1
    repeated = {k for k, n in seen.items() if n > 1}
    added = {k for k in seen if k in by_key and not by_key[k].in_documented}
    missing = {s.key for s in inputs.facts.steps
               if s.in_documented and s.recorded and s.key not in seen}  # fmt: skip
    out = []
    for c in codes:
        keys, types = set(c.location.keys), set(c.types)
        if (
            (c.location.kind == "activity" and c.location.keys[0] in route.hidden)
            or (keys & repeated and "D4" in types)
            or (keys & added and "D2" in types)
            or (keys & missing and types & {"D1", "D5"})
        ):
            out.append(c.code)
    return out


def _route_name(route: RouteIn, inputs: Inputs) -> str:
    labels = {s.key: s.label for s in inputs.facts.steps}
    documented = {s.key for s in inputs.facts.steps if s.in_documented}
    seen: list[str] = []
    for k in route.keys:
        if k and k in seen:
            return f"Repeats {labels.get(k, k)}"
        seen.append(k)
    if route.hidden:
        return f"Adds {route.hidden[0]}"
    added = [k for k in route.keys if k and k not in documented]
    if added:
        return f"Adds {labels.get(added[0], added[0])}"
    recorded = [s for s in inputs.facts.steps if s.in_documented and s.recorded]
    skipped = [s for s in recorded if s.key not in route.keys]
    if skipped:
        return f"Skips {skipped[0].label}"
    return f"Route {route.rank}"


def _first_impact(code_ids: Sequence[str], by_code: Mapping[str, CodeView]) -> str | None:
    impacts = [by_code[c].impact_class for c in code_ids if c in by_code]
    return min(impacts, key=verdict_rules.IMPACT_ORDER.index) if impacts else None


def glance(inputs: Inputs, codes: Sequence[CodeView], figures: Figures) -> GlanceModel:
    by_code = {c.code: c for c in codes}
    share = _documented_share(inputs)
    if share is not None:
        routes: list[Route] = [Route(
            id="documented", name="As documented", documented=True,
            share=figures.by_id["rv1.documented_share"], codes=[], impact_class=None,
            other_count=0)]  # fmt: skip
        others = [r for r in inputs.routes if not r.fits_documented]
        own: list[tuple[RouteIn, list[str]]] = []
        rest: list[tuple[RouteIn, list[str]]] = []
        for r in sorted(others, key=lambda r: (-r.share, r.rank)):
            found = _route_codes(r, inputs, codes)
            control = any(by_code[c].control for c in found)
            big = r.share >= ROUTE_SHARE and len(own) < MAX_RIBBONS - 2
            (own if big or control else rest).append((r, found))
        for r, found in own:
            f = figures.add(f"rv1.route.{r.rank}", round(100 * r.share, 1), "pct",
                            copy.pct(r.share), rules.MEASURED, "variant_share")  # fmt: skip
            routes.append(Route(id=f"route-{r.rank}", name=_route_name(r, inputs),
                                documented=False, share=f, codes=found,
                                impact_class=_first_impact(found, by_code),
                                other_count=0))  # fmt: skip
        listed = sum(r.share for r in inputs.routes)
        other = sum(r.share for r, _ in rest) + max(0.0, 1.0 - listed)
        n = len(rest) + inputs.routes_other
        if n and other > 0:
            f = figures.add("rv1.route.other", round(100 * other, 1), "pct", copy.pct(other),
                            rules.MEASURED, "variant_share")  # fmt: skip
            found = sorted({c for _, cs in rest for c in cs}, key=_number)
            routes.append(Route(id="other", name=f"Other: {copy.count(n, 'rarer route')}",
                                documented=False, share=f, codes=found,
                                impact_class=_first_impact(found, by_code),
                                other_count=n))  # fmt: skip
        routes = [routes[0], *sorted(routes[1:], key=lambda r: -(r.share.value or 0.0))]
        return GlanceModel(basis="cases", routes=routes)
    n, total = _practised(inputs, codes)
    if not total:
        return GlanceModel(basis="steps", routes=[])
    routes = [Route(id="documented", name="As documented", documented=True,
                    share=figures.by_id["rv1.practised"], codes=[], impact_class=None,
                    other_count=0)]  # fmt: skip
    deviations = sorted((c for c in codes if set(c.types) & ROUTE_TYPES),
                        key=lambda c: c.rank)[: MAX_RIBBONS - 1]  # fmt: skip
    for c in sorted(deviations, key=lambda c: _number(c.code)):
        k = max(1, len(c.location.keys))
        f = figures.add(f"rv1.route.{c.code}", float(k), "count", f"{copy.of(k, total, 'step')}",
                        rules.STATED)  # fmt: skip
        routes.append(Route(id=f"code-{c.code}", name=c.title, documented=False, share=f,
                            codes=[c.code], impact_class=c.impact_class,
                            other_count=0))  # fmt: skip
    return GlanceModel(basis="steps", routes=routes)


def _glance_headline(inputs: Inputs, codes: Sequence[CodeView], tiles_: Sequence[Tile],
                     groups: Mapping[str, verdict_rules.Group]) -> str:  # fmt: skip
    facts = inputs.facts
    figures = {t.figure.id: t.figure for t in tiles_}
    share = figures.get("rv1.documented_share")
    if share is not None:
        first = copy.fill("rv1.share_none") if not share.value else copy.fill(
            "rv1.share", documented_share=share.text)  # fmt: skip
    elif not any(s.in_documented for s in facts.steps):
        n = sum(1 for s in facts.steps if s.in_done)
        first = copy.fill("rv1.no_manual", steps=copy.count(n, "step")) if n else ""
    else:
        done_only = sum(1 for s in facts.steps if s.in_done and not s.in_documented)
        documented_only = sum(1 for s in facts.steps if s.in_documented and not s.in_done)
        if not codes and not done_only and not documented_only:
            first = copy.fill("rv1.same")
        else:
            first = copy.fill(
                "rv1.steps",
                done_only=f"{copy.count(done_only, 'step')} "
                f"{copy.verb(done_only, 'happens', 'happen')}",
                documented_only=copy.count(documented_only, "step"),
            )
    second = ""
    control = figures.get("rv1.control_share")
    if control is not None:
        top = control_codes(codes, groups)[0]
        c = next(c for c in codes if c.code == top)
        slot = "rv1.no_record" if "D11" in c.types else "rv1.bypass"
        second = copy.fill(slot, control_share=control.text, control_name=c.title)
    elif (x := figures.get("rv1.multiplier")) is not None and (x.value or 0) >= 1.5:
        second = copy.fill("rv1.multiplier", multiplier=x.text)
    return copy.headline(first, second)


def control_codes(codes: Sequence[CodeView],
                  groups: Mapping[str, verdict_rules.Group]) -> list[str]:  # fmt: skip
    """Codes with a D5 or D11, the largest incidence first (the control tile's code first)."""
    found = [(fd.incidence or 0.0, c.code) for c in codes for fd in _found_of(c, groups)
             if fd.type in ("D5", "D11")]  # fmt: skip
    return [code for _, code in sorted(found, key=lambda t: (-t[0], _number(t[1])))]


# --- RV2 Reality stack --------------------------------------------------------------------------


def _intent_column(i: IntentIn, columns: Sequence[Column], place: Mapping[str, str]) -> str:
    ids = {c.id for c in columns}
    if i.scope == "phase" and i.phase_id in ids:
        return str(i.phase_id)
    for k in i.step_keys:
        if place.get(k) in ids:
            return place[k]
    return PROCESS


def _target_text(i: IntentIn) -> str:
    if i.target is None:
        return ""
    words = {"at_most": "at most", "at_least": "at least", "equals": "equal to"}
    unit = {"lead_time_min": " minutes before", "cycle_time_min": " min", "step_time_min": " min",
            "wait_min": " min", "straight_through_pct": "%", "recorded_pct": "%"}  # fmt: skip
    return f"target {words.get(i.comparator or '', '')} {i.target:g}{unit.get(i.metric or '', '')}"


def stack(inputs: Inputs, columns: Sequence[Column], place: Mapping[str, str],
          codes: Sequence[CodeView], figures: Figures) -> tuple[StackModel, list[str]]:  # fmt: skip
    facts = inputs.facts
    ids = [c.id for c in columns]
    has_log = facts.total_cases > 0
    steps = sorted(facts.steps, key=lambda s: s.order)
    cells: dict[str, dict[str, list[StackItem]]] = {b: {c: [] for c in ids} for b in copy.BANDS}

    def item(band: str, column: str, **kw: object) -> None:
        base: dict[str, object] = {"key": None, "figure": None, "code": None,
                                   "impact_class": None, "result": None, "note": ""}  # fmt: skip
        base.update(kw)
        cells[band].setdefault(column, []).append(StackItem.model_validate(base))

    for i in inputs.intents:
        item("promise", _intent_column(i, columns, place), kind="intent", key=i.intent_id,
             label=i.text, result=i.result, note=_target_text(i))  # fmt: skip
    believed = 0
    for s in steps:
        if not s.official_min or s.key not in place:
            continue
        value = sorted(s.official_min)[len(s.official_min) // 2]
        believed += 1
        n = min(inputs.official_sources.get(s.key, 1), max(inputs.interviews, 1))
        f = figures.add(f"rv2.belief.{s.key}", value, "min", copy.minutes(value, signed=False),
                        rules.STATED, None)  # fmt: skip
        item("belief", place[s.key], kind="belief", key=s.key, label=s.label, figure=f,
             note=f"stated in {copy.of(n, inputs.interviews, 'interview')}")  # fmt: skip
    for s in steps:
        if s.in_documented and s.key in place:
            designed: Figure | None = None
            if s.documented_min is not None:
                designed = figures.add(f"rv2.documented.{s.key}", s.documented_min, "min",
                                       copy.minutes(s.documented_min, signed=False),
                                       rules.DOCUMENTED)  # fmt: skip
            item("documented", place[s.key], kind="documented_step", key=s.key, label=s.label,
                 figure=designed, note="" if designed else "No time stated")  # fmt: skip
    for s in steps:
        if s.in_done and s.key in place:
            done, label = step_minutes(s)
            practice: Figure | None = None
            if done is not None:
                practice = figures.add(f"rv2.done.{s.key}", done, "min",
                                       copy.minutes(done, signed=False), label)  # fmt: skip
            item("done", place[s.key], kind="done_step", key=s.key, label=s.label, figure=practice,
                 note="added in practice" if not s.in_documented else
                 ("" if practice else "No time stated"))  # fmt: skip
    highlighted, listed = _highlight(codes)
    for c in sorted(codes, key=lambda c: c.rank):
        if c.code in highlighted and c.column_id in ids:
            band = "documented" if c.location.kind == "design" else "done"  # its fix is the manual
            item(band, c.column_id or PROCESS, kind="branch", label=c.title, figure=c.delta,
                 code=c.code, impact_class=c.impact_class, note=c.delta.text)  # fmt: skip
    lost: dict[str, tuple[float, float]] = {}
    for col in [*ids, PROCESS]:
        mine = list(codes) if col == PROCESS else [c for c in codes if c.column_id == col]
        minutes = [c.minutes for c in mine if c.minutes is not None]
        total_min = round(sum(m.value or 0.0 for m in minutes), 1)
        total_h = round(sum(_h(c) for c in mine), 1)
        lost[col] = (total_h, total_min)
        if minutes:
            f = figures.add(
                f"rv2.minutes.{col}",
                total_min,
                "min",
                f"{copy.minutes(total_min)} a case",
                _blend([m.label for m in minutes]),
            )
            item("consequence", col, kind="minutes", label="Extra minutes a case", figure=f)
        if has_log:
            f = figures.add(f"rv2.hours.{col}", total_h, "h", copy.hours(total_h), rules.MEASURED)
            item("consequence", col, kind="hours", label="Hours a month", figure=f)
    names = {c.id: c.name for c in columns}
    ranked = sorted((c for c in ids), key=lambda c: (-lost[c][0], -lost[c][1], ids.index(c)))
    lens = None
    if ranked and (lost[ranked[0]][0] > 0 or lost[ranked[0]][1] > 0):
        lens = Lens(column_id=ranked[0], label=copy.fill("lens", column=names[ranked[0]]))
    bands = []
    documents_ready = any(s.in_documented for s in facts.steps)
    for band, name in copy.BANDS.items():
        state, message, evidence = "ready", "", ""
        if band == "promise":
            evidence = copy.count(len(inputs.intents), "confirmed statement")
            if not inputs.intents:
                state, message = "missing", copy.AVAILABILITY["rv2.no_intent"]
        elif band == "belief":
            evidence = f"{copy.of(believed, inputs.interviews, 'interview')} state a time" if (
                inputs.interviews) else "no interview"  # fmt: skip
            if not believed:
                state, message = "missing", copy.AVAILABILITY["rv2.no_belief"]
        elif band == "documented":
            evidence = copy.count(inputs.documents, "document")
            if not documents_ready:
                state, message = "missing", copy.AVAILABILITY["rv2.no_documents"]
        elif band == "done":
            parts = [copy.count(inputs.interviews, "interview")]
            if has_log:
                parts.append(copy.count(facts.total_cases, "case"))
            evidence = " · ".join(parts)
        else:
            evidence = (f"measured from {copy.count(facts.total_cases, 'case')}" if has_log
                        else "stated times")  # fmt: skip
            if not has_log:
                state, message = "partial", copy.AVAILABILITY["rv2.no_log"]
        bands.append(Band(id=band, name=name, evidence=evidence, state=state, message=message,
                          cells=[StackCell(column_id=c, items=cells[band].get(c, []))
                                 for c in [*ids, PROCESS]]))  # fmt: skip
    headline = _stack_headline(codes, lens, lost, names)
    return StackModel(bands=bands, lens=lens, highlighted=highlighted, listed=listed), [headline]


def _highlight(codes: Sequence[CodeView]) -> tuple[list[str], list[str]]:
    """At most 5 branches drawn, at most 2 of them control exposures; the rest stay listed."""
    ranked = sorted(codes, key=lambda c: c.rank)
    out: list[str] = []
    controls = 0
    for c in ranked:
        if len(out) >= MAX_HIGHLIGHTED:
            break
        if c.control:
            if controls >= MAX_HIGHLIGHTED_CONTROLS:
                continue
            controls += 1
        out.append(c.code)
    return out, [c.code for c in ranked if c.code not in out]


def _stack_headline(codes: Sequence[CodeView], lens: Lens | None,
                    lost: Mapping[str, tuple[float, float]],
                    names: Mapping[str, str]) -> str:  # fmt: skip
    if not codes:
        return copy.fill("rv2.same")
    if lens is None:
        return copy.fill("rv2.no_time", gaps=copy.count(len(codes), "gap"))
    hours, minutes = lost[lens.column_id]
    phase = names[lens.column_id]
    if hours > 0:
        return copy.fill("rv2.hotspot", phase=phase, added_min=f"{minutes:.0f}",
                         hours=f"{hours:.0f}")  # fmt: skip
    return copy.fill("rv2.hotspot_minutes", phase=phase, added_min=f"{minutes:.0f}")


# --- RV3 Fix or keep ----------------------------------------------------------------------------


def _zone(c: CodeView) -> str:
    shown = c.verdict.shown if c.verdict else None
    return shown if shown in CODIFY_SHOWN else "ask"


def fix(inputs: Inputs, codes: Sequence[CodeView], figures: Figures) -> FixModel:
    ranked = sorted(codes, key=lambda c: c.rank)
    drawn = [c for c in ranked if c.control] + [c for c in ranked if not c.control]
    drawn = sorted(drawn[: max(MAX_CIRCLES, sum(1 for c in ranked if c.control))],
                   key=lambda c: c.rank)  # fmt: skip
    circles = [Placed(code=c.code, zone=_zone(c)) for c in drawn]
    return FixModel(
        quadrants=[Quadrant(id=q, name=n, meaning=m) for q, (n, m) in copy.QUADRANTS.items()],
        circles=circles, ask=[p.code for p in circles if p.zone == "ask"],
        decide_first=[c.code for c in ranked], limit=DECIDE_FIRST, note=copy.fill("rv3.note"),
    )  # fmt: skip


def _fix_headline(inputs: Inputs, codes: Sequence[CodeView]) -> str:
    if not codes:
        return copy.fill("rv3.same")
    zones = [_zone(c) for c in codes]
    n = {z: zones.count(z) for z in ("codify", "correct", "rewrite", "ask")}
    if not inputs.intents:
        return copy.fill("rv3.no_intent", ask=copy.count(len(codes), "gap"),
                         ask_wait=copy.verb(len(codes), "waits", "wait"))  # fmt: skip
    kinds = {i.kind for c in codes if _zone(c) == "correct"
             for i in inputs.intents if i.intent_id in _intent_ids(c, inputs)}  # fmt: skip
    intent_kind = copy.INTENT_KINDS.get(next(iter(kinds)), "the intent") if len(kinds) == 1 else (
        "the intent")  # fmt: skip
    correct = {
        "correct": copy.count(n["correct"], "gap"),
        "correct_verb": copy.verb(n["correct"], "puts", "put"),
        "intent_kind": intent_kind,
    }
    codify = {"codify": copy.count(n["codify"], "gap"),
              "codify_verb": copy.verb(n["codify"], "protects", "protect")}  # fmt: skip
    if n["correct"] and n["codify"]:
        return copy.fill("rv3.both", **correct, **codify)
    if n["correct"]:
        return copy.fill("rv3.correct", **correct)
    if n["codify"]:
        return copy.fill("rv3.codify", **codify)
    if n["rewrite"]:
        return copy.fill("rv3.rewrite", rewrite=copy.count(n["rewrite"], "gap"),
                         rewrite_verb=copy.verb(n["rewrite"], "lies", "lie"))  # fmt: skip
    return copy.fill("rv3.ask", ask=copy.count(n["ask"], "gap"),
                     ask_verb=copy.verb(n["ask"], "needs", "need"),
                     ask_pronoun=copy.verb(n["ask"], "it", "they"))  # fmt: skip


def _intent_ids(c: CodeView, inputs: Inputs) -> set[str]:
    keys = set(c.location.keys)
    return {i.intent_id for i in inputs.intents if set(i.step_keys) & keys}


# --- callouts and tables ------------------------------------------------------------------------


def _callout(c: CodeView) -> Callout:
    lines = [copy.fill("callout.code", code=c.code, title=c.title, delta=c.delta.text)]
    if c.control:
        lines.append(copy.fill("callout.control"))
    else:
        figures = [f.text for f in (c.minutes, c.hours) if f is not None and f.value]
        if figures:
            lines.append(copy.fill("callout.figures", figures="; ".join(figures)))
    return Callout(code=c.code, impact_class=c.impact_class, lines=lines)


def _callouts(codes: Sequence[CodeView], order: Sequence[str]) -> list[Callout]:
    by_code = {c.code: c for c in codes}
    return [_callout(by_code[k]) for k in order if k in by_code][:MAX_CALLOUTS]


def _decide_callouts(codes: Sequence[CodeView]) -> list[Callout]:
    ranked = sorted(codes, key=lambda c: c.rank)
    if not ranked:
        return []
    first = ranked[0]
    lines = [copy.fill("callout.decide", code=first.code, title=first.title)]
    if first.verdict and first.verdict.reason:
        lines.append(copy.fill("callout.reason", reason=first.verdict.reason))
    out = [Callout(code=first.code, impact_class=first.impact_class, lines=lines)]
    out += [_callout(c) for c in ranked[1:] if c.control][: MAX_CALLOUTS - 1]
    return out


def _glance_table(model: GlanceModel) -> ViewTable:
    head = ["Route", "Share of cases" if model.basis == "cases" else "Steps", "Label", "Codes"]
    rows = [[r.name, r.share.text, r.share.label, " ".join(r.codes)] for r in model.routes]
    return ViewTable(columns=head, rows=rows)


def _item_text(i: StackItem) -> str:
    name = f"{i.code} {i.label}" if i.code else i.label
    parts = []
    if i.figure is not None:
        parts.append(f"{i.figure.text} ({i.figure.label})")
    if i.result:
        parts.append({"met": "met", "not_met": "not met", "unknown": "not known yet"}[i.result])
    if i.note and i.kind != "branch":
        parts.append(i.note)
    return f"{name}: {', '.join(parts)}" if parts else name


def _stack_table(model: StackModel, columns: Sequence[Column]) -> ViewTable:
    names = {c.id: c.name for c in columns} | {PROCESS: "Whole process"}
    head = ["Band", *[names[c.column_id] for c in model.bands[0].cells]] if model.bands else []
    rows = []
    for b in model.bands:
        rows.append([b.name, *["; ".join(_item_text(i) for i in cell.items)
                               or (b.message if b.state == "missing" else "")
                               for cell in b.cells]])  # fmt: skip
    return ViewTable(columns=head, rows=rows)


def _fix_table(codes: Sequence[CodeView]) -> ViewTable:
    names = {q: n for q, (n, _) in copy.QUADRANTS.items()}
    rows = []
    for c in sorted(codes, key=lambda c: c.rank):
        v = c.verdict
        rows.append([c.code, c.title, names[_zone(c)],
                     f"{v.shown} ({v.status})" if v and v.shown else "",
                     v.reason if v else "", c.hours.text if c.hours else NO_HOURS,
                     c.evidence.sentence])  # fmt: skip
    return ViewTable(columns=["Code", "Title", "Zone", "Verdict", "Reason", "Hours a month",
                              "Evidence"], rows=rows)  # fmt: skip


# --- the snapshot -------------------------------------------------------------------------------


def _codes(inputs: Inputs, coded: Sequence[Coded], place: Mapping[str, str],
           figures: Figures) -> list[CodeView]:  # fmt: skip
    facts = inputs.facts
    ranks = _rank(coded)
    out = []
    for c in coded:
        word, glyph = copy.IMPACT_WORDS[c.impact]
        hours = None
        if facts.total_cases:  # hours come from measured figures only: none without a log
            hours = figures.add(f"{c.item.code}.hours", c.hours, "h", copy.hours(c.hours),
                                rules.MEASURED)  # fmt: skip
        out.append(CodeView(
            code=c.item.code, item_id=c.item.item_id, title=c.item.title, types=c.group.types,
            impact_class=c.impact, impact_word=word, glyph=glyph,
            impact_note=verdict_rules.POTENTIAL if c.impact == verdict_rules.CONTROL else "",
            location=LocationView(kind=c.group.kind, keys=list(c.group.keys)),
            element_ids=[s.element_id for s in facts.steps if s.key in c.group.keys],
            column_id=_code_column(c, place, inputs), delta=_delta(c, figures),
            minutes=_code_minutes(c, inputs, figures), hours=hours,
            verdict=_verdict(c, facts), evidence=_evidence(c, facts),
            control=c.impact == verdict_rules.CONTROL, shown=c.group.shown,
            rank=ranks[c.item.code],
        ))  # fmt: skip
    return out


def _availability(state: str = "ready", key: str = "", action: str | None = None) -> Availability:
    return Availability(state=state, message=copy.AVAILABILITY[key] if key else "", action=action)


def build(inputs: Inputs, app_version: str, frozen: bool) -> RealitySnapshot:
    figures = Figures()
    facts = inputs.facts
    coded, process = coded_groups(inputs)
    columns, place = _step_columns(inputs)
    codes = _codes(inputs, coded, place, figures)
    columns, note = _trim(columns, codes)
    kept = {c.id for c in columns}
    for c in codes:
        if c.column_id not in kept and c.column_id != PROCESS:
            c.column_id = None  # in a phase not shown: listed beside the view
    place = {k: v for k, v in place.items() if v in kept}
    groups = {c.item.code: c.group for c in coded}
    tiles_ = tiles(inputs, codes, process, groups, figures)
    cases = facts.total_cases or None
    has_documents = any(s.in_documented for s in facts.steps)

    model1 = glance(inputs, codes, figures)
    if not has_documents:
        a1 = _availability("partial", "rv1.no_documents", "upload_documents")
    elif not facts.total_cases:
        a1 = _availability("partial", "rv1.no_log", "import_log")
    else:
        a1 = _availability()
    order1 = control_codes(codes, groups) + [c.code for c in sorted(codes, key=lambda c: c.rank)]
    rv1 = GlanceView(
        id="rv1", title=copy.title("rv1", inputs.process_name),
        headline=_glance_headline(inputs, codes, tiles_, groups),
        callouts=_callouts(codes, list(dict.fromkeys(order1))), availability=a1,
        table=_glance_table(model1), glance=model1,
        geometry=layout.glance(model1),
    )  # fmt: skip

    model2, [headline2] = stack(inputs, columns, place, codes, figures)
    missing = [b for b in model2.bands if b.state != "ready"]
    a2 = _availability()
    if not has_documents:
        a2 = _availability("partial", "rv2.no_documents", "upload_documents")
    elif not inputs.intents:
        a2 = _availability("partial", "rv2.no_intent", "add_intent")
    elif missing and not facts.total_cases:
        a2 = _availability("partial", "rv2.no_log", "import_log")
    rv2 = StackView(
        id="rv2", title=copy.title("rv2", inputs.process_name), headline=headline2,
        callouts=_callouts(codes, model2.highlighted), availability=a2,
        table=_stack_table(model2, columns), stack=model2,
        geometry=layout.stack(model2, columns),
    )  # fmt: skip

    model3 = fix(inputs, codes, figures)
    a3 = _availability() if inputs.intents else _availability("partial", "rv3.no_intent",
                                                              "add_intent")  # fmt: skip
    by_code = {c.code: c for c in codes}
    rv3 = FixView(
        id="rv3", title=copy.title("rv3", inputs.process_name),
        headline=_fix_headline(inputs, codes), callouts=_decide_callouts(codes),
        availability=a3, table=_fix_table(codes), fix=model3,
        geometry=layout.fix(model3, {k: _h(c) for k, c in by_code.items()}),
    )  # fmt: skip

    legend = Legend(
        impacts=[LegendImpact(impact_class=k, word=w, glyph=g)
                 for k, (w, g) in copy.IMPACT_WORDS.items()],
        lines=[LegendLine(style=s, meaning=m) for s, m in copy.LINES],
        scales=[rv1.geometry.scale_note, rv3.geometry.scale_note],
        data_label=inputs.data_label,
    )  # fmt: skip
    return RealitySnapshot(
        version_id=inputs.version_id, rules_version=rules.REALITY_RULES_VERSION,
        copy_version=copy.COPY_VERSION, layout_version=layout.LAYOUT_VERSION,
        app_version=app_version, inputs_hash=inputs_hash(inputs), frozen=frozen,
        draft=inputs.draft, process_name=inputs.process_name, data_label=inputs.data_label,
        evidence=EvidenceSummary(documents=inputs.documents, interviews=inputs.interviews,
                                 cases=cases, text=copy.evidence_text(inputs.documents,
                                                                      inputs.interviews, cases)),
        figures=dict(sorted(figures.by_id.items())), tiles=tiles_,
        columns=[*columns, Column(id=PROCESS, name="Whole process", kind=PROCESS, step_keys=[])],
        columns_note=note, codes=codes,
        intents=[SnapshotIntent(id=i.intent_id, kind=i.kind, text=i.text, scope=i.scope,
                                step_keys=list(i.step_keys), result=i.result,
                                target=_target_text(i)) for i in inputs.intents],
        views=RealityViews(rv1=rv1, rv2=rv2, rv3=rv3), legend=legend,
    )  # fmt: skip


def serialise(snapshot: RealitySnapshot) -> str:
    """The snapshot as canonical JSON (sorted keys): the byte-identical form (G17)."""
    return json.dumps(snapshot.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
