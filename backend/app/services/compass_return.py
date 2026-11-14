"""The `compass-return` file (Eric's brief §2.4, §3 D; DECISIONS 97): what a published map found,
in the one shape the other apps read, as JSON and as the same content in readable text.

Pure: the action hands in what to say, already with names hidden. A finding carries this app's
own code (S-01, X1, I1) or, for a verdict on something being tested, the ID exactly as Capability
Compass or Eric gave it; no ID is made here. No quote, no person's name, no source text and no
key is ever part of it; `leaks` is the last check before a file leaves.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.services import grade as grade_rules

RETURN_FORMAT = "compass-return"
RETURN_VERSION = "1.0"
SOURCE_APP = "process-map-studio"
RETURN_RULES_VERSION = "1"

KINDS = ("step", "discrepancy", "intent", "knowledge_risk", "hypothesis_verdict", "variation")
KIND_WORDS = {"step": "Steps", "discrepancy": "Discrepancies", "intent": "Intent statements",
              "knowledge_risk": "Knowledge risks",
              "hypothesis_verdict": "What we are testing",
              "variation": "Differences from another country"}  # fmt: skip
REASON_WORDS = {"required": "Required", "chosen": "Chosen", "inherited": "Inherited",
                "unknown": "Not known yet"}  # fmt: skip
SECRET_MARKERS = ("sk-" + "ant-", "api_key", "x-api-key")
# Topics (PRD §3.19, B.52): which Compass readout page a finding belongs on.
DECISION_RIGHT, WAY_OF_WORKING = "decision_right", "way_of_working"
DECIDING = frozenset({"decision", "approval"})
# Discrepancy types in words (B.48), as the Compass's own sample writes them.
TYPE_WORDS = {
    "D1": "Skipped step", "D2": "Added step", "D3": "Reordered", "D4": "Rework loop",
    "D5": "Control bypassed", "D6": "Off-system", "D7": "Takes longer", "D8": "Waiting",
    "D9": "Parallel routes", "D10": "Belief gap", "D11": "No record", "D12": "Different role",
    "D13": "Design gap", "D14": "Promise missed",
}  # fmt: skip
# Country differences in words (B.53); "Only in …" names the country.
DIFFERENCE_WORDS = {
    "who_does": "Different role doing it", "who_decides": "Different role",
    "how_decided": "Different way of deciding", "step_kind": "Different kind of step",
    "work_type": "Different work type", "work_time": "Different work time",
    "wait_time": "Different waiting time", "documented_vs_done": "Documented and done differ",
}  # fmt: skip


def discrepancy_topic(step_kinds: list[str], types: list[str]) -> str:
    """D12 "Different role" on a decision or approval is about who decides; the rest is how the
    work runs."""
    return DECISION_RIGHT if "D12" in types and DECIDING & set(step_kinds) else WAY_OF_WORKING


STEP_KINDS = {"activity": "Activity", "decision": "Decision", "approval": "Approval"}
WORK_TYPES = {"clear": "clear", "complicated": "complicated", "complex": "complex",
              "chaotic": "chaotic"}  # fmt: skip
MECHANISMS = {"rule_based": "rule-based", "judgment": "judgment"}
RESULTS = {"met": "Met", "not_met": "Not met", "unknown": "Not yet known"}
VERDICTS = {"supported": "Supported", "refuted": "Refuted", "open": "Open"}
# The words the Reality views use for each verdict (reality_copy.QUADRANTS).
DISCREPANCY_VERDICTS = {"codify": "codify the practice", "correct": "correct the practice",
                        "rewrite": "rewrite the rule", "ask": "ask",
                        "as_designed": "working as designed"}  # fmt: skip


@dataclass(frozen=True, slots=True)
class Step:
    code: str
    label: str
    kind: str
    lane: str
    work_type: str | None
    mechanism: str
    provenance: str
    documents: int
    interviews: int
    knowledge_risk: str = ""


@dataclass(frozen=True, slots=True)
class Discrepancy:
    code: str
    title: str
    types: list[str]
    figure: str
    figure_label: str
    grade: str
    grade_by_owner: bool
    impact: str
    verdict: str | None
    documents: int
    interviews: int
    system_cases: int | None
    topic: str = WAY_OF_WORKING


@dataclass(frozen=True, slots=True)
class Variation:
    """One classed or kept difference between this country's map and the reference country's
    (PRD §3.19): reported by this country only."""

    code: str  # V1
    kind: str  # B.53
    title: str
    topic: str
    step_code: str  # this country's S-nn; "" for a step only the reference country has
    step_label: str
    reason_class: str | None  # None unless Eric classed it
    reason_note: str
    grade: str
    figure: str
    country: str
    compared_with: str
    source_note: str


@dataclass(frozen=True, slots=True)
class Intent:
    code: str
    text: str
    kind: str
    result: str
    target: str
    quoted: bool


@dataclass(frozen=True, slots=True)
class Tested:
    ref: str
    text: str
    verdict: str
    evidence_refs: list[str]
    note: str


@dataclass(frozen=True, slots=True)
class Inputs:
    engagement_key: str
    pilot_ref: str
    cluster_ref: str
    cells: list[str]
    generated_at: str
    process_name: str
    version_label: str
    steps: list[Step] = field(default_factory=list)
    discrepancies: list[Discrepancy] = field(default_factory=list)
    intents: list[Intent] = field(default_factory=list)
    tested: list[Tested] = field(default_factory=list)
    country: str = ""
    variations: list[Variation] = field(default_factory=list)


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _sources(documents: int, interviews: int, system_cases: int | None = None) -> str:
    system = f"system records of {_count(system_cases, 'case', 'cases')}" if system_cases else ""
    parts = [
        _count(documents, "document", "documents") if documents else "",
        _count(interviews, "interview", "interviews") if interviews else "",
        system,
    ]
    return ", ".join(p for p in parts if p) or "no source that speaks to it"


def _step(s: Step) -> tuple[str, str, str]:
    """(detail, grade, source note)."""
    work = WORK_TYPES.get(s.work_type or "", "")
    kind = STEP_KINDS.get(s.kind, s.kind)
    decided = f"Decided by {MECHANISMS[s.mechanism]}." if s.mechanism in MECHANISMS else ""
    parts = [f"{kind} in the {s.lane} lane." if s.lane else f"{kind}.",
             f"Work type: {work}." if work else "Work type: not classified.", decided]  # fmt: skip
    observed = s.provenance == "O" and (s.documents or s.interviews)
    grade = grade_rules.INDICATED if observed else grade_rules.HYPOTHESIS
    words = {"O": "Observed in", "I": "Inferred from", "R": "Recommended; not from"}
    note = f"{words.get(s.provenance, 'From')} {_sources(s.documents, s.interviews)}."
    return " ".join(p for p in parts if p), grade, note


def _tested_grade(t: Tested, grades: dict[str, str]) -> str:
    """Open is a hypothesis; a verdict is as sure as the weakest finding it rests on."""
    if t.verdict == "open":
        return grade_rules.HYPOTHESIS
    behind = [grades[r] for r in t.evidence_refs if r in grades]
    if behind and all(g == grade_rules.CONFIRMED for g in behind):
        return grade_rules.CONFIRMED
    if behind and all(g == grade_rules.HYPOTHESIS for g in behind):
        return grade_rules.HYPOTHESIS
    return grade_rules.INDICATED


def findings(data: Inputs) -> list[dict[str, object]]:
    """Every finding in the order: steps, discrepancies, intent, knowledge risks, verdicts."""
    relates = list(dict.fromkeys([data.pilot_ref, data.cluster_ref, *data.cells]))
    relates = [r for r in relates if r]
    grades: dict[str, str] = {}
    out: list[dict[str, object]] = []

    def add(ref: str, kind: str, title: str, detail: str, grade: str, figure: str,
            note: str, **extra: str) -> None:  # fmt: skip
        out.append({"ref": ref, "kind": kind, "title": title, "detail": detail,
                    "grade": grade, "figure": figure, "relates_to": list(relates),
                    "source_note": note, **extra})  # fmt: skip

    for s in data.steps:
        detail, grade, note = _step(s)
        grades[s.code] = grade
        topic = DECISION_RIGHT if s.kind in DECIDING else WAY_OF_WORKING
        add(s.code, "step", s.label, detail, grade, "", note, topic=topic)
    for d in data.discrepancies:
        grades[d.code] = d.grade
        verdict = DISCREPANCY_VERDICTS.get(d.verdict or "", "")
        detail = " ".join(p for p in (
            f"Types: {', '.join(TYPE_WORDS.get(t, t) for t in d.types)}." if d.types else "",
            f"Impact: {d.impact}." if d.impact else "",
            f"Verdict: {verdict}." if verdict else "",
        ) if p)  # fmt: skip
        figure = f"{d.figure} ({d.figure_label})" if d.figure and d.figure_label else d.figure
        chosen = "Grade chosen by the owner. " if d.grade_by_owner else ""
        note = f"{chosen}Rests on {_sources(d.documents, d.interviews, d.system_cases)}."
        add(d.code, "discrepancy", d.title, detail, d.grade, figure, note, topic=d.topic)
    for i in data.intents:
        known = i.result in ("met", "not_met")
        grade = grade_rules.INDICATED if known else grade_rules.HYPOTHESIS
        grades[i.code] = grade
        origin = "Quoted from a policy or charter" if i.quoted else "Target stated by the owner"
        add(i.code, "intent", i.text, f"{RESULTS.get(i.result, i.result)}.", grade, i.target,
            f"{origin}; compared with the published map.")  # fmt: skip
    for s in data.steps:
        if s.knowledge_risk:
            add(s.code, "knowledge_risk", f"Knowledge risk at {s.label}", s.knowledge_risk,
                grades[s.code], "", f"Recorded at role level for step {s.code}.")  # fmt: skip
    for t in data.tested:
        behind = ", ".join(t.evidence_refs)
        detail = " ".join(p for p in (
            f"{VERDICTS.get(t.verdict, t.verdict)}.",
            f"Behind it: {behind}." if behind else "",
            t.note,
        ) if p)  # fmt: skip
        note = (f"The owner's verdict, resting on {behind}." if behind
                else "No verdict yet.")  # fmt: skip
        add(t.ref, "hypothesis_verdict", t.text, detail, _tested_grade(t, grades), "", note)
    for v in data.variations:
        word = DIFFERENCE_WORDS.get(v.kind) or (
            f"Only in {v.compared_with}" if v.kind == "only_reference" else f"Only in {v.country}"
        )
        elsewhere = f"Step not on this map ({v.compared_with}'s step: {v.step_label})."
        where = f"Step {v.step_code} ({v.step_label})." if v.step_code else elsewhere
        reason = v.reason_note.strip().rstrip(".")
        detail = f"Types: {word}. {where}" + (f" Reason: {reason}." if reason else "")
        extra = {"topic": v.topic}
        if v.reason_class is not None:
            extra["reason_class"] = v.reason_class
        extra["compared_with"] = v.compared_with
        add(v.code, "variation", v.title, detail, v.grade, v.figure, v.source_note, **extra)
    return out


def build(data: Inputs) -> dict[str, object]:
    head: dict[str, object] = {"format": RETURN_FORMAT, "format_version": RETURN_VERSION,
                               "generated_at": data.generated_at, "source_app": SOURCE_APP,
                               "engagement_key": data.engagement_key}  # fmt: skip
    if data.country:
        head["country"] = data.country
    return {**head, "findings": findings(data)}


def render_json(data: Inputs) -> str:
    return json.dumps(build(data), indent=2, ensure_ascii=False) + "\n"


def render_text(data: Inputs) -> str:
    """The same content for a reader: one section per kind, one block per finding."""
    file = build(data)
    found = findings(data)
    ids = [r for r in dict.fromkeys([data.pilot_ref, data.cluster_ref, *data.cells]) if r]
    relates = ", ".join(ids) or "none"
    lines = [
        f"# {data.process_name}: findings for Capability Compass",
        "",
        f"Engagement key: {data.engagement_key} · "
        + (f"country: {data.country} · " if data.country else "")
        + f"pilot: {data.pilot_ref} · map version: {data.version_label}",
        f"Format: {file['format']} {file['format_version']} · made by {SOURCE_APP} · "
        f"{data.generated_at}",
        f"Relates to: {relates}",
        "",
        "Grades: Confirmed (a system record and another source), Indicated (at least one "
        "checked source), Hypothesis (inferred or not yet checked). Role names only; no "
        "quotes and no source text.",
    ]
    for kind in KINDS:
        of_kind = [f for f in found if f["kind"] == kind]
        if not of_kind:
            continue
        lines += ["", f"## {KIND_WORDS[kind]}", ""]
        for f in of_kind:
            grade = grade_rules.WORDS.get(str(f["grade"]), str(f["grade"]))
            lines.append(f"- **{f['ref']}** {f['title']} · {grade}")
            if f["detail"]:
                lines.append(f"  {f['detail']}")
            if f["figure"]:
                lines.append(f"  Figure: {f['figure']}")
            if f.get("reason_class"):
                lines.append(f"  Reason class: {REASON_WORDS.get(str(f['reason_class']), '')}")
            if f.get("compared_with"):
                lines.append(f"  Compared with: {f['compared_with']}")
            lines.append(f"  Rests on: {f['source_note']}")
    if not found:
        lines += ["", "No finding to return yet."]
    return "\n".join(lines) + "\n"


def leaks(text: str, hidden_terms: list[str], secret_markers: tuple[str, ...]) -> list[str]:
    """What must never be in the file but is: a hidden name or something shaped like a key."""
    lowered = text.lower()
    found = [t for t in hidden_terms if t and t.lower() in lowered]
    return found + [m for m in secret_markers if m.lower() in lowered]
