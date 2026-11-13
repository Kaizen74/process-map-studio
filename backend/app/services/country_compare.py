"""Comparing two countries' published maps of the same process (PRD §3.19; DECISIONS 98).

Pure and deterministic (rule set `COUNTRY_RULES_VERSION`, constraint 27): the caller hands in each
side's steps with names already hidden. Proposes step pairs with their reasons, and works out the
differences of the pairs Eric confirmed, each as one line with both values in words. It never
classes a difference: the reason is Eric's.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from app.services import grade as grade_rules

COUNTRY_RULES_VERSION = "1"
TIME_RATIO = 1.5  # one side at least 1.5 times the other (Eric's brief §4.4)

DECIDING = frozenset({"decision", "approval"})
KIND_WORDS = {"activity": "an activity", "decision": "a decision", "approval": "an approval"}
MECHANISM_WORDS = {"rule_based": "a fixed rule", "judgment": "judgment"}
WORK_TYPE_WORDS = {
    "clear": "clear",
    "complicated": "complicated",
    "complex": "complex",
    "chaotic": "chaotic",
}
DISCREPANCY_TYPE_WORDS = {
    "D1": "skipped step",
    "D2": "added step",
    "D3": "reordered",
    "D4": "rework loop",
    "D5": "control bypassed",
    "D6": "off-system",
    "D7": "takes longer",
    "D8": "waiting",
    "D9": "parallel routes",
    "D10": "belief gap",
    "D11": "no record",
    "D12": "different role",
    "D13": "design gap",
    "D14": "promise missed",
}
STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "into", "is", "it", "of", "on", "or", "the", "to", "with",
})  # fmt: skip

DECISION_RIGHT = "decision_right"
ROLE_PRESENCE = "role_presence"
WAY_OF_WORKING = "way_of_working"


@dataclass(frozen=True, slots=True)
class Step:
    """One step of a published map as compared (names already hidden)."""

    key: str
    code: str
    label: str
    kind: str
    lane: str
    phase: str
    order: int
    decider: str = ""
    mechanism: str = "none"
    work_type: str | None = None  # only when confirmed
    work_min: float | None = None
    wait_min: float | None = None
    provenance: str = "O"
    documents: int = 0
    interviews: int = 0
    discrepancies: tuple[tuple[str, tuple[str, ...]], ...] = ()  # (Xn, (D12, …))


@dataclass(frozen=True, slots=True)
class Proposal:
    reference_key: str
    other_key: str
    why: str


@dataclass(frozen=True, slots=True)
class Difference:
    key: str
    kind: str  # B.53
    topic: str  # B.52
    title: str
    reference_value: str
    other_value: str
    figure: str
    reference_key: str | None
    other_key: str | None
    suggested_grade: str
    grade_reason: str


@dataclass(frozen=True, slots=True)
class Countries:
    reference: str  # "Arden"
    other: str  # "Belmar"
    reference_lanes: frozenset[str] = field(default_factory=frozenset)  # casefolded lane names
    other_lanes: frozenset[str] = field(default_factory=frozenset)


def words(label: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", label.casefold()) if w not in STOPWORDS}


def _same(a: str, b: str) -> bool:
    return a.strip().casefold() == b.strip().casefold()


def propose(
    reference: Sequence[Step], other: Sequence[Step], taken: Iterable[str] = ()
) -> list[Proposal]:
    """Pairs for the steps nobody has decided yet, best first: shared words in the label, then the
    same lane role name, the same kind and the same phase name, then nearest in order. A pair
    needs a shared word, or the same lane, kind and phase together."""
    busy = set(taken)
    left = [s for s in reference if s.key not in busy]
    right = [s for s in other if s.key not in busy]
    scored = []
    for r in left:
        for o in right:
            shared = sorted(words(r.label) & words(o.label))
            lane, kind, phase = _same(r.lane, o.lane), r.kind == o.kind, _same(r.phase, o.phase)
            if not shared and not (lane and kind and phase):
                continue
            score = 3 * len(shared) + 2 * lane + kind + phase
            reasons = [f"same words: {', '.join(shared)}"] if shared else []
            reasons += [f"same lane: {r.lane}"] if lane and r.lane else []
            reasons += ["same kind of step"] if kind else []
            reasons += [f"same phase: {r.phase}"] if phase and r.phase else []
            scored.append(
                (-score, abs(r.order - o.order), r.order, r.key, o.key, " · ".join(reasons))
            )
    out, used_r, used_o = [], set(), set()
    for _, _, _, rk, ok, why in sorted(scored):
        if rk in used_r or ok in used_o:
            continue
        used_r.add(rk)
        used_o.add(ok)
        out.append(Proposal(rk, ok, why[0].upper() + why[1:]))
    return out


def _grade(*steps: Step) -> tuple[str, str]:
    if len(steps) == 1:
        return grade_rules.HYPOTHESIS, (
            "Hypothesis: only one map has this step, and the other map's sources may simply not "
            "mention it."
        )
    if all(s.provenance == "O" and s.documents + s.interviews > 0 for s in steps):
        return grade_rules.INDICATED, (
            "Indicated: both steps are observed, each in at least one checked source."
        )
    return grade_rules.HYPOTHESIS, (
        "Hypothesis: at least one of the two steps is inferred or rests on no checked source."
    )


def _minutes(value: float) -> str:
    return f"{value:g} min"


def _discrepancy_topic(step: Step, types: Sequence[str]) -> str:
    return DECISION_RIGHT if "D12" in types and step.kind in DECIDING else WAY_OF_WORKING


def discrepancy_topic(kind: str, types: Sequence[str]) -> str:
    """The topic of a discrepancy finding (PRD §3.19): D12 on a decision or approval decides."""
    return DECISION_RIGHT if "D12" in types and kind in DECIDING else WAY_OF_WORKING


def step_topic(kind: str) -> str:
    return DECISION_RIGHT if kind in DECIDING else WAY_OF_WORKING


def pair_differences(r: Step, o: Step, c: Countries) -> list[Difference]:
    """Every difference of one confirmed pair, one line each."""
    out: list[Difference] = []
    grade, reason = _grade(r, o)
    name = o.label

    def add(
        kind: str, topic: str, phrase: str, ref_value: str, other_value: str, figure: str = ""
    ) -> None:
        out.append(
            Difference(
                key=f"{kind}|{r.key}|{o.key}",
                kind=kind,
                topic=topic,
                title=f"{name}: {phrase}",
                reference_value=ref_value,
                other_value=other_value,
                figure=figure,
                reference_key=r.key,
                other_key=o.key,
                suggested_grade=grade,
                grade_reason=reason,
            )
        )

    if not _same(r.lane, o.lane):
        add(
            "who_does",
            WAY_OF_WORKING,
            f"done by {o.lane or 'no named role'} in {c.other}, "
            f"by {r.lane or 'no named role'} in {c.reference}",
            r.lane,
            o.lane,
        )
    if (r.decider or o.decider) and not _same(r.decider, o.decider):
        verb = "approved" if "approval" in (r.kind, o.kind) else "decided"
        add(
            "who_decides",
            DECISION_RIGHT,
            f"{verb} by {o.decider or 'no named role'} in {c.other}, "
            f"by {r.decider or 'no named role'} in {c.reference}",
            r.decider,
            o.decider,
        )
    if (
        r.mechanism in MECHANISM_WORDS
        and o.mechanism in MECHANISM_WORDS
        and r.mechanism != o.mechanism
    ):
        add(
            "how_decided",
            DECISION_RIGHT,
            f"decided by {MECHANISM_WORDS[o.mechanism]} in {c.other}, "
            f"by {MECHANISM_WORDS[r.mechanism]} in {c.reference}",
            MECHANISM_WORDS[r.mechanism],
            MECHANISM_WORDS[o.mechanism],
        )
    if r.kind != o.kind:
        topic = DECISION_RIGHT if {r.kind, o.kind} & DECIDING else WAY_OF_WORKING
        add(
            "step_kind",
            topic,
            f"{KIND_WORDS.get(o.kind, o.kind)} in {c.other}, "
            f"{KIND_WORDS.get(r.kind, r.kind)} in {c.reference}",
            KIND_WORDS.get(r.kind, r.kind),
            KIND_WORDS.get(o.kind, o.kind),
        )
    if r.work_type and o.work_type and r.work_type != o.work_type:
        add(
            "work_type",
            WAY_OF_WORKING,
            f"{WORK_TYPE_WORDS.get(o.work_type, o.work_type)} work in {c.other}, "
            f"{WORK_TYPE_WORDS.get(r.work_type, r.work_type)} in {c.reference}",
            r.work_type,
            o.work_type,
        )
    for kind, what, rv, ov in (
        ("work_time", "work", r.work_min, o.work_min),
        ("wait_time", "wait", r.wait_min, o.wait_min),
    ):
        if rv and ov and max(rv, ov) >= TIME_RATIO * min(rv, ov):
            add(
                kind,
                WAY_OF_WORKING,
                f"{_minutes(ov)} of {what} in {c.other}, {_minutes(rv)} in {c.reference}",
                _minutes(rv),
                _minutes(ov),
                f"{_minutes(ov)} in {c.other} vs {_minutes(rv)} in {c.reference} (stated)",
            )
    ref_x, other_x = bool(r.discrepancies), bool(o.discrepancies)
    if ref_x != other_x:
        step = o if other_x else r
        types = [t for _, ts in step.discrepancies for t in ts]
        words_ = ", ".join(dict.fromkeys(DISCREPANCY_TYPE_WORDS.get(t, t) for t in types))
        where, calm = (c.other, c.reference) if other_x else (c.reference, c.other)
        # Only this (the other) country's X code means anything outside its engagement.
        codes = f"{', '.join(x for x, _ in o.discrepancies)}: " if other_x else ""
        add(
            "documented_vs_done",
            _discrepancy_topic(step, types),
            f"the documented and the done way differ in {where} ({codes}{words_}), not in {calm}",
            "differ" if ref_x else "agree",
            "differ" if other_x else "agree",
        )
    return out


def only_difference(step: Step, side: str, c: Countries) -> Difference:
    """A step one country has and the other doesn't (Eric marked it "Only in …")."""
    here, there = (c.reference, c.other) if side == "reference" else (c.other, c.reference)
    lanes_here, lanes_there = (
        (c.reference_lanes, c.other_lanes)
        if side == "reference"
        else (c.other_lanes, c.reference_lanes)
    )
    lane = step.lane.casefold()
    topic = (
        ROLE_PRESENCE if lane and lane in lanes_here and lane not in lanes_there else WAY_OF_WORKING
    )
    grade, reason = _grade(step)
    kind = "only_reference" if side == "reference" else "only_other"
    ref_key, other_key = (step.key, None) if side == "reference" else (None, step.key)
    return Difference(
        key=f"{kind}|{ref_key or ''}|{other_key or ''}",
        kind=kind,
        topic=topic,
        title=f"{step.label}: only in {here} ({step.lane or 'no named role'}), not in {there}",
        reference_value="present" if side == "reference" else "absent",
        other_value="present" if side == "other" else "absent",
        figure="",
        reference_key=ref_key,
        other_key=other_key,
        suggested_grade=grade,
        grade_reason=reason,
    )


def differences(
    reference: Sequence[Step],
    other: Sequence[Step],
    pairs: Sequence[tuple[str | None, str | None, str]],
    c: Countries,
) -> list[Difference]:
    """The differences of Eric's decisions, in the reference map's order: each confirmed pair's,
    and one per step marked as only in one country."""
    by_r: Mapping[str, Step] = {s.key: s for s in reference}
    by_o: Mapping[str, Step] = {s.key: s for s in other}
    found: list[tuple[int, int, Difference]] = []
    for ref_key, other_key, status in pairs:
        if (
            status == "confirmed"
            and ref_key
            and other_key
            and ref_key in by_r
            and other_key in by_o
        ):
            r, o = by_r[ref_key], by_o[other_key]
            found += [(r.order, o.order, d) for d in pair_differences(r, o, c)]
        elif status == "only_reference" and ref_key and ref_key in by_r:
            found.append((by_r[ref_key].order, 0, only_difference(by_r[ref_key], "reference", c)))
        elif status == "only_other" and other_key and other_key in by_o:
            o = by_o[other_key]
            found.append((o.order, o.order, only_difference(o, "other", c)))
    return [d for _, _, d in sorted(found, key=lambda x: (x[0], x[1]))]
