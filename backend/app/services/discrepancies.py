"""The discrepancy engine (PRD §3.17.1-3.17.3; P13a). Pure and deterministic: no AI, no database.

Every difference between intent, documents, belief and practice is classified into one of
fourteen types (B.48) with an explicit delta and its figure label (B.50). The thresholds are one
versioned rule set (`REALITY_RULES_VERSION`, G15): changing any of them re-runs the golden
baselines and is logged in DECISIONS.md first.

Rules worth knowing (DECISIONS.md, P13a-3):
- Silence is never a skipped step (constraint 4): D1 needs a log, a confirmed "no system record"
  with no lived account, or a lived claim saying it is not done.
- A control here is a documented one: an approval of the As documented view, or a step with a
  risk flag or covered by a confirmed control objective. An added approval is not a control
  exposure (§3.17.4), so D5 and D11 are about documented controls.
- D5 needs the control to be recorded: a control with a confirmed "no system record" can't be
  seen being routed around; it is D11 (no record) instead.
- D6 "between recorded neighbours": a run of unrecorded done-view steps entered from a recorded
  step by a sequence line (not on a decision's exception branch) and leaving to a recorded step.
- A step's measured time is its main system activity's duration (end - start), the figure the
  panel and the estimate-gap rule compare with the stated time. When the step's accounts state a
  wait, that duration is the step's measured wait; otherwise the wait is the time before it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.domain.enums import FigureLabel

REALITY_RULES_VERSION = "2"  # 2: Glance's hours tile is the stack's time lost (2026-10-20)
MINIMUM_CASES = 5  # constraint 24: no case share from fewer cases
SHOW_SHARE = 0.05  # §3.17.3: drawn from 5% of cases (control exposures at any frequency)
SKIP_SHARE = 0.05  # D1 (a): absent in at least 5% of the cases reaching the next step
REWORK_SHARE = 0.10  # D4: measured rework of at least 10% on a step
LONGER = 0.50  # D7: done time more than 50% over the documented time (as estimate_gap)
WAIT_MIN = 5.0  # D8: a median wait of at least 5 minutes
VARIANT_SHARE = 0.05  # D9: at least two system variants of at least 5% of cases each
BELIEF_FACTOR = 1.5  # D10: believed and measured differ by a factor of 1.5 or more
BELIEF_POINTS = 10.0  # D10 for shares: at least 10 points apart
# D6: unofficial tools a lived account may name (codebook tier 2). "load sheet" is the product.
TOOL_WORDS = ("spreadsheet", "excel", "email", "e-mail", "chat", "whatsapp", "text message",
              "paper", "printout", "print-out", "notebook", "whiteboard", "local file",
              "sheet")  # fmt: skip
NOT_TOOLS = ("load sheet", "loadsheet")
SEQUENCE_LINES = frozenset({"sequence", "handoff"})
REWORK_LINES = frozenset({"rework", "reject"})
NARRATION = "narration_order"
TIMES = "\u00d7"  # the multiplication sign, as in "1.4 times"
MEASURED, STATED = FigureLabel.MEASURED.value, FigureLabel.STATED.value
DOCUMENTED, TARGET = FigureLabel.DOCUMENTED.value, FigureLabel.TARGET.value


@dataclass(frozen=True, slots=True)
class Measure:
    median: float
    p90: float | None
    cases: int


@dataclass(frozen=True, slots=True)
class StepFacts:
    """One step of the version (in either view), with what the sources and the log say."""

    key: str
    element_id: str
    label: str
    kind: str  # activity · decision · approval
    order: int  # process order (done view first, then the documented-only steps)
    in_done: bool
    in_documented: bool
    usual_route: bool = False
    risk_flag: str | None = None
    divergence_types: tuple[str, ...] = ()
    documented_owner: str = ""
    done_owner: str = ""
    described_in: int = 0  # practice interviews whose verified accounts describe it
    lived_accounts: int = 0  # verified lived claims on it
    not_done_quotes: int = 0  # verified lived claims stating it is not done
    documented_min: float | None = None  # stated documented duration
    done_min: float | None = None  # stated lived duration
    stated_wait: float | None = None  # stated lived wait
    official_min: tuple[float, ...] = ()  # official accounts' stated times (belief)
    official_sources: int = 0  # interviews whose official accounts state a time for it
    tools: tuple[str, ...] = ()  # unofficial tools named on it
    # System records (None: no imported log covers the step).
    recorded: bool | None = None  # True: matched to an activity; False: confirmed no record
    cases: int = 0  # cases where the step is recorded
    reach_next: int = 0  # cases reaching the step after it (for D1 (a))
    skipped: int = 0  # of those, cases without this step
    rework_cases: int = 0
    time: Measure | None = None  # the main activity's duration
    wait_before: Measure | None = None
    artefact_support: bool = False  # an executed artefact records it
    per_month: float | None = None  # cases a month passing the step (measured)
    stated_reason: bool = False  # a lived account states why it is done this way
    documents: int = 0  # documents whose verified claims describe it


@dataclass(frozen=True, slots=True)
class Line:
    source: str  # step key
    target: str
    kind: str
    basis: str = ""


@dataclass(frozen=True, slots=True)
class HiddenWork:
    activity: str
    cases: int
    per_month: float | None = None
    minutes: float | None = None  # its median duration


@dataclass(frozen=True, slots=True)
class IntentOnStep:
    """A confirmed intent statement and what it covers (with its evaluation, when it has one)."""

    intent_id: str
    kind: str
    step_keys: tuple[str, ...]
    metric: str | None = None
    comparator: str | None = None
    target: float | None = None
    result: str = "unknown"  # met · not_met · unknown
    actual: float | None = None
    label: str | None = None
    met_share: float | None = None
    cases: int | None = None
    documented: float | None = None
    documented_meets: bool | None = None


@dataclass(frozen=True, slots=True)
class DesignConflict:
    """A confirmed IX_compare design gap (D13), at the steps its statement covers."""

    conflict_id: str
    intent_id: str
    step_keys: tuple[str, ...]
    text: str


@dataclass(frozen=True, slots=True)
class Facts:
    steps: Sequence[StepFacts]
    done_lines: Sequence[Line] = ()
    documented_lines: Sequence[Line] = ()
    hidden: Sequence[HiddenWork] = ()
    variants: Sequence[int] = ()  # system variants' case counts, most common first
    total_cases: int = 0  # cases in the log(s) (0: no log)
    interviews: int = 0  # practice interviews
    intents: Sequence[IntentOnStep] = ()
    conflicts: Sequence[DesignConflict] = ()
    contradictions: Mapping[str, str] = field(default_factory=dict)  # step key → system note


@dataclass(frozen=True, slots=True)
class Delta:
    value: float | None
    unit: str  # pct · min · x · count · ""
    label: str  # B.50
    text: str  # plain words


@dataclass(frozen=True, slots=True)
class Found:
    """One detected discrepancy of one type at one location."""

    type: str  # B.48
    keys: tuple[str, ...]  # step stable keys, or ("activity:<name>",) or ("process",)
    delta: Delta
    incidence: float | None = None  # share of cases (never added up)
    cases: int | None = None
    control: bool = False  # on a documented control
    intent_ids: tuple[str, ...] = ()
    detail: Mapping[str, str] = field(default_factory=dict)

    @property
    def shown(self) -> bool:
        """§3.17.3: drawn from 5% of cases, or a control exposure at any frequency; a figure
        stated by interviews (no case share) is shown."""
        return self.control or self.incidence is None or self.incidence >= SHOW_SHARE


def _pct(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def _share_text(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)}% of cases" if whole else ""


def _interviews_text(n: int, total: int) -> str:
    return f"described in {n} of {total} interviews"


def is_control(step: StepFacts, objectives: set[str]) -> bool:
    """A documented control: an approval of the As documented view, or a step with a risk flag or
    covered by a confirmed control objective (an added approval is not one, §3.17.4)."""
    return (
        (step.in_documented and step.kind == "approval")
        or bool(step.risk_flag)
        or step.key in objectives
    )


def _objectives(facts: Facts) -> set[str]:
    return {k for i in facts.intents if i.kind == "control_objective" for k in i.step_keys}


def _next_documented(step: StepFacts, facts: Facts, by_key: Mapping[str, StepFacts]) -> str | None:
    for line in facts.documented_lines:
        if line.source == step.key and line.kind not in REWORK_LINES and line.target in by_key:
            return line.target
    return None


# --- the fourteen types -------------------------------------------------------------------------


def _d1(step: StepFacts, facts: Facts, control: bool) -> Found | None:
    """Skipped step: a documented step the log shows absent, or confirmed unrecorded with no lived
    account, or stated as not done. Never from interview silence alone."""
    if not step.in_documented:
        return None
    if step.recorded and step.reach_next >= MINIMUM_CASES:
        share = _pct(step.skipped, step.reach_next)
        if share >= SKIP_SHARE:
            return Found("D1", (step.key,), Delta(round(100 * share, 1), "pct", MEASURED,
                         _share_text(step.skipped, step.reach_next) + " skip it"),
                         share, step.skipped, control)  # fmt: skip
    if step.recorded is False and step.lived_accounts == 0 and facts.total_cases:
        cases = facts.total_cases
        return Found("D1", (step.key,), Delta(100.0, "pct", MEASURED,
                     f"never recorded; {_share_text(cases, cases)}"), 1.0, cases, control,
                     detail={"basis": "b"})  # fmt: skip
    if step.not_done_quotes:
        n = step.not_done_quotes
        return Found("D1", (step.key,), Delta(float(n), "count", STATED,
                     f"stated in {n} of {facts.interviews} interviews"), None, None, control,
                     detail={"basis": "c"})  # fmt: skip
    return None


def _d2(step: StepFacts, facts: Facts) -> Found | None:
    """Added step: in the As done view only."""
    if step.in_documented or not step.in_done:
        return None
    if step.recorded and step.cases and facts.total_cases:
        share = _pct(step.cases, facts.total_cases)
        return Found("D2", (step.key,), Delta(round(100 * share, 1), "pct", MEASURED,
                     _share_text(step.cases, facts.total_cases)), share, step.cases)  # fmt: skip
    return Found("D2", (step.key,), Delta(float(step.described_in), "count", STATED,
                 _interviews_text(step.described_in, facts.interviews)))  # fmt: skip


def _hidden(work: HiddenWork, facts: Facts) -> Found | None:
    """Added step: a confirmed hidden-work activity the log records."""
    if work.cases < MINIMUM_CASES or not facts.total_cases:
        return None
    share = _pct(work.cases, facts.total_cases)
    return Found("D2", (f"activity:{work.activity}",), Delta(round(100 * share, 1), "pct",
                 MEASURED, _share_text(work.cases, facts.total_cases)), share, work.cases,
                 detail={"activity": work.activity})  # fmt: skip


def _order(lines: Sequence[Line], keys: set[str]) -> list[tuple[str, str]]:
    """Ordered pairs of steps directly in sequence (no loop back, no narration-only line)."""
    return [(ln.source, ln.target) for ln in lines
            if ln.source in keys and ln.target in keys and ln.kind not in REWORK_LINES
            and ln.basis != NARRATION]  # fmt: skip


def _d3(facts: Facts, by_key: Mapping[str, StepFacts]) -> list[Found]:
    """Reordered: two steps in both views in the opposite order, or the log's order differs."""
    both = {s.key for s in facts.steps if s.in_done and s.in_documented}
    documented = set(_order(facts.documented_lines, both))
    out = [Found("D3", (a, b), Delta(None, "", STATED, "described in the other order"))
           for a, b in _order(facts.done_lines, both) if (b, a) in documented]  # fmt: skip
    for key, note in sorted(facts.contradictions.items()):
        if key in by_key:
            out.append(Found("D3", (key,), Delta(None, "", MEASURED, note),
                             detail={"basis": "system"}))  # fmt: skip
    return out


def _d4(step: StepFacts, facts: Facts) -> Found | None:
    """Loop or rework: a rework line back to the step in As done, or measured rework of at least
    10%. With a log, the measured share is the incidence (so an unseen loop isn't drawn)."""
    line = any(ln.target == step.key and ln.kind in REWORK_LINES for ln in facts.done_lines)
    measured = step.recorded and step.cases >= MINIMUM_CASES
    share = _pct(step.rework_cases, step.cases) if measured else None
    if share is not None and share >= REWORK_SHARE:
        return Found("D4", (step.key,), Delta(round(100 * share, 1), "pct", MEASURED,
                     f"rework in {_share_text(step.rework_cases, step.cases)}"),
                     share, step.rework_cases)  # fmt: skip
    if line:
        if share is not None:
            return Found("D4", (step.key,), Delta(round(100 * share, 1), "pct", MEASURED,
                         f"rework in {_share_text(step.rework_cases, step.cases)}"),
                         share, step.rework_cases)  # fmt: skip
        return Found("D4", (step.key,), Delta(None, "", STATED, "a loop back is described"))
    return None


def _d5(step: StepFacts, control: bool) -> Found | None:
    """Control bypassed: a recorded control that cases reach the next step without."""
    if not control or not step.recorded or step.reach_next < MINIMUM_CASES or not step.skipped:
        return None
    share = _pct(step.skipped, step.reach_next)
    return Found("D5", (step.key,), Delta(round(100 * share, 1), "pct", MEASURED,
                 f"{_share_text(step.skipped, step.reach_next)} go round {step.label}"),
                 share, step.skipped, True)  # fmt: skip


def runs(facts: Facts, members: set[str]) -> list[list[str]]:
    """Contiguous runs of the given done-view steps (connected by lines), in process order."""
    adjacent: dict[str, set[str]] = {k: set() for k in members}
    for ln in facts.done_lines:
        if ln.source in members and ln.target in members and ln.kind not in REWORK_LINES:
            adjacent[ln.source].add(ln.target)
            adjacent[ln.target].add(ln.source)
    order = {s.key: s.order for s in facts.steps}
    seen: set[str] = set()
    out = []
    for key in sorted(members, key=lambda k: order.get(k, 0)):
        if key in seen:
            continue
        run, todo = [], [key]
        while todo:
            k = todo.pop()
            if k in seen:
                continue
            seen.add(k)
            run.append(k)
            todo += sorted(adjacent[k] - seen)
        out.append(sorted(run, key=lambda k: order.get(k, 0)))
    return out


def _d6(facts: Facts, by_key: Mapping[str, StepFacts]) -> list[Found]:
    """Off-system: unrecorded done-view steps in line between recorded neighbours, or a step whose
    lived account names an unofficial tool."""
    out: list[Found] = []
    unrecorded = {s.key for s in facts.steps if s.in_done and s.recorded is False}
    covered: set[str] = set()
    for run in runs(facts, unrecorded):
        inside = set(run)
        entered = [ln for ln in facts.done_lines if ln.target in inside and ln.source not in inside]
        left = [ln for ln in facts.done_lines if ln.source in inside and ln.target not in inside
                and ln.kind not in REWORK_LINES]  # fmt: skip
        in_line = any(ln.kind in SEQUENCE_LINES and by_key.get(ln.source) is not None
                      and by_key[ln.source].recorded for ln in entered)  # fmt: skip
        leaves = any(by_key.get(ln.target) is not None and by_key[ln.target].recorded
                     for ln in left)  # fmt: skip
        if in_line and leaves:
            tools = sorted({t for k in run for t in by_key[k].tools})
            out.append(_off_system(tuple(run), tools, by_key, facts))
            covered |= inside
    named = {s.key for s in facts.steps if s.in_done and s.tools and s.key not in covered}
    for run in runs(facts, named):
        out.append(_off_system(tuple(run), sorted({t for k in run for t in by_key[k].tools}),
                               by_key, facts))  # fmt: skip
    return out


def _off_system(keys: tuple[str, ...], tools: list[str], by_key: Mapping[str, StepFacts],
                facts: Facts) -> Found:  # fmt: skip
    described = max(by_key[k].described_in for k in keys)
    words = [_interviews_text(described, facts.interviews)] if described else []
    if any(by_key[k].recorded is False for k in keys):
        words.append("no system record")
    if tools:
        words.append(f"tool “{', '.join(tools)}”")
    return Found("D6", keys, Delta(float(described), "count", STATED, "; ".join(words)),
                 detail={"tool": ", ".join(tools)})  # fmt: skip


def _d7(step: StepFacts) -> Found | None:
    """Takes longer: the done time (measured median, else the lived stated time) more than 50%
    over the documented time. A step whose accounts state a wait compares that wait instead (D8,
    D14), so its documented time isn't set against the work."""
    if step.documented_min is None or step.documented_min <= 0 or step.stated_wait is not None:
        return None
    measured = step.time if step.time and step.time.cases >= MINIMUM_CASES else None
    done, label = (measured.median, MEASURED) if measured else (step.done_min, STATED)
    if done is None:
        return None
    over = (done - step.documented_min) / step.documented_min
    if over <= LONGER:
        return None
    return Found("D7", (step.key,), Delta(round(done - step.documented_min, 1), "min", label,
                 f"+{done - step.documented_min:.0f} min a case "
                 f"({TIMES}{done / step.documented_min:.1f})"))  # fmt: skip


def measured_wait(step: StepFacts) -> Measure | None:
    """The step's measured wait: its activity's duration when its accounts state a wait, else the
    time before it (see the module notes)."""
    if step.stated_wait is not None and step.time is not None:
        return step.time
    return step.wait_before


def _d8(step: StepFacts) -> Found | None:
    """Waiting: a measured median wait of at least 5 minutes, or a lived stated wait."""
    wait = measured_wait(step)
    if wait is not None and wait.cases >= MINIMUM_CASES:
        if wait.median < WAIT_MIN:
            return None
        p90 = f", 90th percentile {wait.p90:.0f}" if wait.p90 is not None else ""
        return Found("D8", (step.key,), Delta(round(wait.median, 1), "min", MEASURED,
                     f"wait {wait.median:.0f} min median{p90}"), cases=wait.cases)  # fmt: skip
    if step.stated_wait is not None and step.stated_wait >= WAIT_MIN and step.recorded is None:
        return Found("D8", (step.key,), Delta(step.stated_wait, "min", STATED,
                     f"wait of {step.stated_wait:.0f} min stated"))  # fmt: skip
    return None


def _d9(facts: Facts) -> Found | None:
    """Parallel routes (process level): at least two system variants of at least 5% each."""
    total = sum(facts.variants)
    big = [n for n in facts.variants if total and n / total >= VARIANT_SHARE]
    if total < MINIMUM_CASES or len(big) < 2:
        return None
    shares = [round(100 * n / total) for n in big]
    other = 100 - sum(shares)
    text = ", ".join(f"{s}%" for s in shares) + (f", Other {other}%" if other > 0 else "")
    return Found("D9", ("process",), Delta(float(len(big)), "count", MEASURED,
                 f"{len(big)} routes: {text}"), cases=total)  # fmt: skip


@dataclass(frozen=True, slots=True)
class Belief:
    believed: float  # the median of the official accounts' stated times
    measured: float  # the measured median
    cases: int
    factor: float  # the larger over the smaller (at least 1)


def belief(step: StepFacts) -> Belief | None:
    """A step's believed and measured time, when both are known (at least 5 measured cases);
    D10 and the Belief vs evidence view (RV6) read the same pair."""
    measured = measured_wait(step) if step.stated_wait is not None else step.time
    if not step.official_min or measured is None or measured.cases < MINIMUM_CASES:
        return None
    believed = sorted(step.official_min)[len(step.official_min) // 2]
    if believed <= 0 or measured.median <= 0:
        return None
    factor = max(believed, measured.median) / min(believed, measured.median)
    return Belief(believed, measured.median, measured.cases, factor)


def _d10(step: StepFacts) -> Found | None:
    """Belief gap (process level): an official account's value against the measured value."""
    b = belief(step)
    if b is None or b.factor < BELIEF_FACTOR:
        return None
    return Found("D10", (step.key,), Delta(round(b.factor, 1), "x", MEASURED,
                 f"believed {b.believed:.0f} min, measured {b.measured:.0f} min "
                 f"({TIMES}{b.factor:.1f})"), cases=b.cases)  # fmt: skip


def _d11(step: StepFacts, facts: Facts, control: bool) -> Found | None:
    """No record: a documented control with a confirmed "no system record" and no executed
    artefact behind it."""
    if not control or step.recorded is not False or step.artefact_support or not facts.total_cases:
        return None
    cases = facts.total_cases
    return Found("D11", (step.key,), Delta(100.0, "pct", MEASURED,
                 f"{step.label}: {_share_text(cases, cases)} without a record"),
                 1.0, cases, True)  # fmt: skip


def _d12(step: StepFacts, control: bool) -> Found | None:
    """Different role: the documented and the done owner differ."""
    if not step.documented_owner or not step.done_owner:
        return None
    if step.documented_owner.casefold() == step.done_owner.casefold():
        return None
    return Found("D12", (step.key,), Delta(None, "", STATED,
                 f"{step.documented_owner} (documented) vs {step.done_owner} (done)"),
                 control=control, detail={"documented": step.documented_owner,
                                          "done": step.done_owner})  # fmt: skip


def _d13(facts: Facts) -> list[Found]:
    """Design gap: a confirmed statement the documented process misses (numeric), or a confirmed
    IX_compare pair. Unconfirmed proposals are never inputs."""
    out = []
    for i in facts.intents:
        if i.metric is None or i.documented is None or i.documented_meets is not False:
            continue
        unit = "T-" if i.metric == "lead_time_min" else ""
        out.append(Found("D13", i.step_keys or ("process",), Delta(
            i.documented - (i.target or 0), "min", TARGET,
            f"target {unit}{i.target:g} vs documented {unit}{i.documented:g}"),
            intent_ids=(i.intent_id,), detail={"basis": "numeric"}))  # fmt: skip
    for c in facts.conflicts:
        out.append(Found("D13", c.step_keys or ("process",), Delta(None, "", DOCUMENTED, c.text),
                         intent_ids=(c.intent_id,),
                         detail={"basis": "rule", "conflict_id": c.conflict_id}))  # fmt: skip
    return out


def _d14(facts: Facts) -> list[Found]:
    """Promise missed: a confirmed statement with a metric that is not met on the done view."""
    out = []
    for i in facts.intents:
        if i.metric is None or i.result != "not_met" or i.actual is None:
            continue
        share = f"; met in {round(100 * i.met_share)}% of cases" if i.met_share is not None else ""
        out.append(Found("D14", i.step_keys or ("process",), Delta(
            round(i.actual - (i.target or 0), 1), "min" if i.metric.endswith("_min") else "pct",
            i.label or STATED, f"target {i.target:g} vs actual {i.actual:.0f}{share}"),
            incidence=(1 - i.met_share) if i.met_share is not None else None, cases=i.cases,
            intent_ids=(i.intent_id,)))  # fmt: skip
    return out


def detect(facts: Facts) -> list[Found]:
    """Every discrepancy the facts show, in process order (process-level ones last)."""
    by_key = {s.key: s for s in facts.steps}
    objectives = _objectives(facts)
    out: list[Found] = []
    for step in sorted(facts.steps, key=lambda s: s.order):
        control = is_control(step, objectives)
        for found in (_d1(step, facts, control), _d2(step, facts), _d4(step, facts),
                      _d5(step, control), _d7(step), _d8(step), _d11(step, facts, control),
                      _d12(step, control)):  # fmt: skip
            if found is not None:
                out.append(found)
    out += [f for w in facts.hidden if (f := _hidden(w, facts)) is not None]
    out += _d3(facts, by_key)
    out += _d6(facts, by_key)
    out += _d13(facts)
    out += _d14(facts)
    out += [f for s in facts.steps if (f := _d10(s)) is not None]
    if (routes := _d9(facts)) is not None:
        out.append(routes)
    return out
