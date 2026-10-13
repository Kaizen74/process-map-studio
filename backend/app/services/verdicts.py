"""Where each discrepancy sits, how much it matters and where the fix lies (PRD §3.17.3-3.17.6;
P13a). Pure and deterministic, part of the rule set `REALITY_RULES_VERSION` (G15).

- `group`: types found at the same step, or on the same contiguous run of added steps, share one
  location (and later one code); a D13 design gap always has its own, because its fix lies in the
  manual. Process-level types (D9 parallel routes, D10 belief gap) have no location code.
- `impact`: the first rule of §3.17.4 that applies (B.46).
- `hours`: the hours a month the discrepancy accounts for, from measured figures only (a wait,
  the extra minutes, repeated work or measured added work); 0 when nothing is measured. Codes are
  given in order of impact class, then these hours, then process order.
- `verdict`: the suggested verdict and its reason (§3.17.5, B.47). Eric's decision always wins.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.services.discrepancies import Facts, Found, IntentOnStep, StepFacts, runs

CONTROL, TIME, CAPACITY, WORKAROUND = (
    "control_exposure",
    "time_impact",
    "capacity_drain",
    "workaround",
)
IMPACT_ORDER = (CONTROL, TIME, CAPACITY, WORKAROUND)
CODIFY, CORRECT, REWRITE, ASK = "codify", "correct", "rewrite", "ask"
VERDICTS = (CODIFY, CORRECT, REWRITE, ASK)
PROCESS_LEVEL = frozenset({"D9", "D10"})
RISKS = frozenset({"financial", "safety", "regulatory"})
TIME_METRICS = frozenset({"cycle_time_min", "step_time_min", "wait_min", "lead_time_min"})
TYPE_ORDER = tuple(f"D{n}" for n in range(1, 15))
POTENTIAL = "potential control exposure, for the control owner to confirm"

ASK_REASON = "Not enough evidence to say where the fix lies: ask the process owner."
ASK_NO_INTENT = "No confirmed intent covers it: ask the process owner which way is intended."
ASK_NO_CASES = (
    "No case-level figure to compare with the target: ask the process owner, or add system records."
)
ASK_STATED = "The SME's stated reason suggests codify; confirm the gap class."
CORRECT_TARGET = "Practice misses the target ({target}) while the documented way meets it."
CORRECT_CONTROL = "The control objective is not met: restore the control or remove the cause."
REWRITE_REASON = "The manual itself misses the intent: the documented way can't meet it."


@dataclass(frozen=True, slots=True)
class Group:
    location_key: str
    kind: str  # step · run · activity · order · design · process
    keys: tuple[str, ...]  # step stable keys (in process order), or the activity name
    found: tuple[Found, ...]

    @property
    def types(self) -> list[str]:
        return sorted({f.type for f in self.found}, key=TYPE_ORDER.index)

    @property
    def shown(self) -> bool:
        return any(f.shown for f in self.found)

    @property
    def control(self) -> bool:
        return any(f.control for f in self.found)

    @property
    def intent_ids(self) -> list[str]:
        return list(dict.fromkeys(i for f in self.found for i in f.intent_ids))


def _order(facts: Facts) -> dict[str, int]:
    return {s.key: s.order for s in facts.steps}


def group(found: Sequence[Found], facts: Facts) -> list[Group]:
    """Every discrepancy's location, in process order (process-level types last)."""
    order = _order(facts)
    out: list[Group] = []
    singles: dict[str, list[Found]] = {}
    multi: list[tuple[set[str], list[Found]]] = []
    for f in found:
        if f.type in PROCESS_LEVEL:
            out.append(Group(f"process:{f.type}:{'+'.join(f.keys)}", "process", f.keys, (f,)))
        elif f.type == "D13":
            basis = f.detail.get("conflict_id") or "+".join(f.intent_ids)
            out.append(Group(f"design:{'+'.join(f.keys)}:{basis}", "design", f.keys, (f,)))
        elif f.keys and f.keys[0].startswith("activity:"):
            name = f.keys[0].removeprefix("activity:")
            out.append(Group(f"activity:{name}", "activity", (name,), (f,)))
        elif f.type == "D3" and len(f.keys) == 2:
            out.append(Group(f"order:{'+'.join(f.keys)}", "order", f.keys, (f,)))
        elif len(f.keys) > 1:
            multi.append((set(f.keys), [f]))
        else:
            singles.setdefault(f.keys[0], []).append(f)
    # Contiguous runs of added steps share one location (§3.17.6).
    added = {k for k, fs in singles.items() if any(f.type == "D2" for f in fs)}
    for run in runs(facts, added):
        if len(run) > 1:
            multi.append((set(run), []))
    merged: list[tuple[set[str], list[Found]]] = []
    for keys, fs in multi:
        for other in [m for m in merged if m[0] & keys]:
            merged.remove(other)
            keys, fs = keys | other[0], fs + other[1]
        merged.append((keys, fs))
    for keys, fs in merged:
        for k in sorted(keys):
            fs += singles.pop(k, [])
        ordered = tuple(sorted(keys, key=lambda k: order.get(k, 0)))
        out.append(Group(f"run:{'+'.join(ordered)}", "run", ordered, tuple(fs)))
    for key, fs in singles.items():
        out.append(Group(f"step:{key}", "step", (key,), tuple(fs)))
    rank = {"process": 2}
    return sorted(out, key=lambda g: (rank.get(g.kind, 0),
                                      min((order.get(k, 0) for k in g.keys), default=0),
                                      g.kind == "design", g.location_key))  # fmt: skip


def _intents(g: Group, facts: Facts) -> list[IntentOnStep]:
    named = set(g.intent_ids)
    return [i for i in facts.intents if i.intent_id in named or set(i.step_keys) & set(g.keys)]


def _steps(g: Group, facts: Facts) -> list[StepFacts]:
    by_key = {s.key: s for s in facts.steps}
    return [by_key[k] for k in g.keys if k in by_key]


def hours(g: Group, facts: Facts) -> float:
    """Hours a month the discrepancy accounts for, from measured figures only."""
    total = 0.0
    steps = {s.key: s for s in _steps(g, facts)}
    for f in g.found:
        s = steps.get(f.keys[0]) if f.keys else None
        month = s.per_month if s and s.per_month else 0.0
        if f.type in ("D7", "D8") and f.delta.label == "measured" and f.delta.value:
            total += f.delta.value * month / 60  # the wait, or the extra minutes, a case
        elif f.type == "D4" and s and s.time and s.cases:
            total += s.rework_cases / s.cases * s.time.median * month / 60
        elif f.type == "D2" and s and s.time and f.delta.label == "measured":
            total += s.time.median * month / 60
        elif f.type == "D2" and g.kind == "activity":
            work = next((w for w in facts.hidden if w.activity == g.keys[0]), None)
            if work and work.minutes and work.per_month:
                total += work.minutes * work.per_month / 60
    return round(total, 1)


def impact(g: Group, facts: Facts) -> str | None:
    """B.46 impact class: the first rule of §3.17.4 that applies (none for process-level types)."""
    if g.kind == "process":
        return None
    types = set(g.types)
    steps = _steps(g, facts)
    intents = _intents(g, facts)
    named = [i for i in intents if i.intent_id in g.intent_ids]
    if (
        types & {"D5", "D11"}
        or (types & {"D1", "D3", "D12"} and g.control)
        or any(s.risk_flag in RISKS for s in steps)
        or (types & {"D13", "D14"} and any(i.kind == "control_objective" for i in named))
    ):
        return CONTROL  # fmt: skip
    usual = any(s.usual_route for s in steps)
    if (types & {"D7", "D8"} and usual) or (
        types & {"D13", "D14"} and any(i.metric in TIME_METRICS for i in named)
    ):
        return TIME  # fmt: skip
    if types & {"D4", "D7", "D2"} and hours(g, facts) > 0 and g.kind != "activity":
        return CAPACITY
    if types & {"D13", "D14"}:
        return CAPACITY
    return WORKAROUND


def verdict(g: Group, facts: Facts) -> tuple[str | None, str]:
    """The suggested verdict and why (§3.17.5); D10 belief gaps carry none."""
    if g.kind == "process":
        return None, ""
    types = set(g.types)
    intents = _intents(g, facts)
    if "D13" in types:
        return REWRITE, REWRITE_REASON
    for i in intents:
        if "D14" in types and i.intent_id in g.intent_ids and i.documented_meets:
            target = f"{i.target:g}" if i.target is not None else "the target"
            return CORRECT, CORRECT_TARGET.format(target=target)
    if types & {"D1", "D5", "D11"} and any(i.kind == "control_objective" for i in intents):
        return CORRECT, CORRECT_CONTROL
    if any(s.stated_reason for s in _steps(g, facts)):
        return ASK, ASK_STATED
    if any(i.metric for i in intents):
        return ASK, ASK_NO_CASES
    if not intents:
        return ASK, ASK_NO_INTENT
    return ASK, ASK_REASON


def code_order(groups: Sequence[Group], facts: Facts,
               impacts: Mapping[str, str | None]) -> list[Group]:  # fmt: skip
    """New codes go in order of impact class, then hours a month, then process order."""
    order = _order(facts)
    return sorted(
        groups,
        key=lambda g: (IMPACT_ORDER.index(impacts[g.location_key] or WORKAROUND),
                       -hours(g, facts), min((order.get(k, 0) for k in g.keys), default=0),
                       g.location_key),
    )  # fmt: skip
