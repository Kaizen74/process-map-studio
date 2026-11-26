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
from typing import Any

from app.domain.leadership import ProcessSummary
from app.services import grade as grade_rules
from app.services import process_summary as summary_rules
from app.services.accountability import Rights

RETURN_FORMAT = "compass-return"
RETURN_VERSION = "1.0"
SOURCE_APP = "process-map-studio"
RETURN_RULES_VERSION = "1"

KINDS = ("step", "discrepancy", "intent", "knowledge_risk", "hypothesis_verdict", "variation",
         "sop", "process_summary")  # fmt: skip
KIND_WORDS = {"step": "Steps", "discrepancy": "Discrepancies", "intent": "Intent statements",
              "knowledge_risk": "Knowledge risks",
              "hypothesis_verdict": "What we are testing",
              "variation": "Differences from another country",
              "sop": "SOPs and manuals", "process_summary": "The process at a glance"}  # fmt: skip
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
    rights: Rights | None = None  # §3.20: decisions and approvals only
    role_ref: str = ""  # DECISIONS 113: the lane's Capability Compass role (RL-014), if linked


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
    rights: Rights | None = None  # §3.20: from the first decision or approval step it is at
    also_at: list[str] = field(default_factory=list)  # other such steps with other values


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
    rights: Rights | None = None  # §3.20: this country's step, on a decision_right difference


@dataclass(frozen=True, slots=True)
class Sop:
    """One SOP or manual of the source register (§3.20): who owns and updates it, its dates, and
    the published map's steps that cite it and, of those, the ones done differently."""

    code: str  # SOP-01
    title: str
    owner_role: str
    updated_by: str
    version_date: str
    last_reviewed: str
    review_due: str
    controlled: bool | None
    governed: int
    departing: int
    by_discrepancies: (
        bool  # True: departing counts Reality discrepancies; False: disagreeing sources
    )
    older_also: bool


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
    sops: list[Sop] = field(default_factory=list)
    process_cell: str = ""  # the cluster's ".Process" cell when the hand-off has it (§3.20)
    summary: ProcessSummary | None = None  # §3.20: the process at a glance, names hidden


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


def decision_fields(r: Rights | None) -> dict[str, Any]:
    """§3.20: `on_paper`, `decided_by`, `accountable` (each only when known) and
    `accountable_contested: true` (only when so), for a `decision_right` finding."""
    if r is None:
        return {}
    out: dict[str, Any] = {
        k: v
        for k, v in (("on_paper", r.on_paper), ("decided_by", r.decided_by),
                     ("accountable", r.accountable))
        if v
    }  # fmt: skip
    if r.contested:
        out["accountable_contested"] = True
    return out


def findings(data: Inputs) -> list[dict[str, object]]:
    """Every finding in the order: steps, discrepancies, intent, knowledge risks, verdicts."""
    relates = list(dict.fromkeys([data.pilot_ref, data.cluster_ref, *data.cells]))
    relates = [r for r in relates if r]
    grades: dict[str, str] = {}
    out: list[dict[str, object]] = []

    def add(ref: str, kind: str, title: str, detail: str, grade: str, figure: str,
            note: str, **extra: Any) -> None:  # fmt: skip
        out.append({"ref": ref, "kind": kind, "title": title, "detail": detail,
                    "grade": grade, "figure": figure, "relates_to": list(relates),
                    "source_note": note, **extra})  # fmt: skip

    for s in data.steps:
        detail, grade, note = _step(s)
        grades[s.code] = grade
        topic = DECISION_RIGHT if s.kind in DECIDING else WAY_OF_WORKING
        add(s.code, "step", s.label, detail, grade, "", note, topic=topic,
            **decision_fields(s.rights if topic == DECISION_RIGHT else None))  # fmt: skip
        if s.role_ref and s.role_ref not in relates:  # DECISIONS 113: the lane's Compass role
            out[-1]["relates_to"] = [*relates, s.role_ref]
    for d in data.discrepancies:
        grades[d.code] = d.grade
        verdict = DISCREPANCY_VERDICTS.get(d.verdict or "", "")
        detail = " ".join(p for p in (
            f"Types: {', '.join(TYPE_WORDS.get(t, t) for t in d.types)}." if d.types else "",
            f"Impact: {d.impact}." if d.impact else "",
            f"Verdict: {verdict}." if verdict else "",
            f"Also at {', '.join(d.also_at)}." if d.also_at and d.topic == DECISION_RIGHT else "",
        ) if p)  # fmt: skip
        figure = f"{d.figure} ({d.figure_label})" if d.figure and d.figure_label else d.figure
        chosen = "Grade chosen by the owner. " if d.grade_by_owner else ""
        note = f"{chosen}Rests on {_sources(d.documents, d.interviews, d.system_cases)}."
        add(d.code, "discrepancy", d.title, detail, d.grade, figure, note, topic=d.topic,
            **decision_fields(d.rights if d.topic == DECISION_RIGHT else None))  # fmt: skip
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
        extra.update(decision_fields(v.rights if v.topic == DECISION_RIGHT else None))
        add(v.code, "variation", v.title, detail, v.grade, v.figure, v.source_note, **extra)
    for sop in data.sops:
        sop_relates = [r for r in dict.fromkeys([data.pilot_ref, data.cluster_ref,
                                                 data.process_cell]) if r]  # fmt: skip
        out.append({"ref": sop.code, "kind": "sop", "title": sop.title,
                    "detail": _sop_detail(sop), "grade": grade_rules.INDICATED,
                    "figure": (f"{sop.departing} of {_count(sop.governed, 'step', 'steps')} "
                               "done differently"
                               if sop.governed else "Cited by no step on the published map"),
                    "relates_to": sop_relates, "source_note": _sop_note(sop, data.pilot_ref),
                    "topic": WAY_OF_WORKING, **_sop_fields(sop)})  # fmt: skip
    if data.summary is not None:
        out.append(_summary_finding(data, data.summary))
    return out


def _summary_finding(data: Inputs, s: ProcessSummary) -> dict[str, Any]:
    """§3.20: one `process_summary` per published map, under the pilot's own ref."""
    detail = (
        f"Counted on the published map: {_count(s.steps, 'step', 'steps')}, "
        f"{_count(s.decisions, 'decision', 'decisions')}, "
        f"{_count(s.approvals, 'approval', 'approvals')}, "
        f"{_count(s.handoffs, 'handoff', 'handoffs')} between {_count(s.roles, 'role', 'roles')}, "
        f"{_count(s.rework_loops, 'rework loop', 'rework loops')}."
    )
    if s.timed_steps < s.steps:
        detail += f" Times recorded on {s.timed_steps} of {s.steps} steps."
    finding: dict[str, Any] = {
        "ref": data.pilot_ref, "kind": "process_summary", "title": data.process_name,
        "detail": detail, "grade": grade_rules.INDICATED,
        "figure": f"{_count(s.steps, 'step', 'steps')}, "
                  f"{_count(s.handoffs, 'handoff', 'handoffs')}",
        "relates_to": [r for r in dict.fromkeys([data.pilot_ref, data.cluster_ref]) if r],
        "source_note": f"Counted from the published map of {data.pilot_ref}.",
        "topic": WAY_OF_WORKING,
    }  # fmt: skip
    if s.process_owner:
        finding["process_owner"] = s.process_owner[:80]
    finding["metrics"] = summary_rules.metrics(s)
    return finding


def _sop_fields(sop: Sop) -> dict[str, Any]:
    """The register's fields, each only when known; the two step counts always."""
    out: dict[str, Any] = {
        k: v
        for k, v in (("owner_role", sop.owner_role), ("updated_by", sop.updated_by),
                     ("version_date", sop.version_date), ("last_reviewed", sop.last_reviewed),
                     ("review_due", sop.review_due))
        if v
    }  # fmt: skip
    if sop.controlled is not None:
        out["controlled_copy"] = sop.controlled
    out["steps_governed"], out["steps_departing"] = sop.governed, sop.departing
    return out


def _sop_detail(sop: Sop) -> str:
    dates = ", ".join(p for p in (
        f"version {sop.version_date}" if sop.version_date else "",
        f"last reviewed {sop.last_reviewed}" if sop.last_reviewed else "not reviewed on record",
        f"review due {sop.review_due}" if sop.review_due else "no review due recorded",
    ) if p)  # fmt: skip
    copy = {
        True: " The copy in use is the controlled one.",
        False: " The copy in use is not the controlled one.",
        None: "",
    }[sop.controlled]
    return (
        f"Owner: {sop.owner_role or 'not recorded'}. "
        f"Updated by: {sop.updated_by or 'nobody named'}. "
        f"{dates[:1].upper()}{dates[1:]}.{copy}"
        + (" Older version also in the sources." if sop.older_also else "")
    )


def _sop_note(sop: Sop, pilot_ref: str) -> str:
    how = (
        ""
        if sop.by_discrepancies
        else " Done differently: cited steps whose sources disagree (the Reality views are off)."
    )
    return f"From the source register; step counts from the published map of {pilot_ref}.{how}"


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
            if f["kind"] == "process_summary":
                lines.append(f"  Process owner: {f.get('process_owner') or 'not named'}")
                counts: dict[str, int] = dict(f.get("metrics") or {})  # type: ignore[call-overload]
                lines.append("  Counts: " + " · ".join(
                    f"{k.replace('_', ' ')} {v}" for k, v in counts.items()))  # fmt: skip
            roles = [
                f"{word}: {f[key]}"
                for key, word in (("on_paper", "On paper"), ("decided_by", "Decides"),
                                  ("accountable", "Accountable"))
                if f.get(key)
            ]  # fmt: skip
            if roles:
                contested = " (contested)" if f.get("accountable_contested") is True else ""
                lines.append(f"  {' · '.join(roles)}{contested}")
            lines.append(f"  Rests on: {f['source_note']}")
    if not found:
        lines += ["", "No finding to return yet."]
    return "\n".join(lines) + "\n"


def leaks(text: str, hidden_terms: list[str], secret_markers: tuple[str, ...]) -> list[str]:
    """What must never be in the file but is: a hidden name or something shaped like a key."""
    lowered = text.lower()
    found = [t for t in hidden_terms if t and t.lower() in lowered]
    return found + [m for m in secret_markers if m.lower() in lowered]
