"""The gap analysis report as Markdown (PRD §3.11.3; phase P10). Pure: no AI, no database.

A fixed template: 1. Facts, 2. Interpretation, 3. Recommendation, then rejected findings as
counts by guardrail and the run's notes. Every line carries its provenance tag. Documents vs
practice never shows a passage's words, only each side's source, place and stance; external
findings show each source's title, link, tier, date and an excerpt of at most 25 words.
"""

from __future__ import annotations

from collections import Counter

from app.domain.gap import GapFindingView, GapReport
from app.services.exports import display_date

TITLES = {"internal": "documents vs practice", "external": "external best practice"}
ADVISORY = "Advisory evidence summary: not a legal, regulatory or audit opinion."
SEVERITY = {"high": "High", "medium": "Medium", "low": "Low"}
STRENGTH = {"weak": "weak evidence (vendor or unknown sources only)", "dated": "dated sources"}
DECISIONS = {
    "open": "open",
    "added_question": "added as a validation question",
    "added_cause": "added to the cause library",
    "added_step": "added as a step",
    "dismissed": "dismissed",
}
GUARDRAILS = {
    "G3": "passage not given or evidence missing",
    "G4": "quote not found in the source",
    "G5": "number or role not found",
    "G6": "verifier",
    "G10": "name block",
    "GX1": "no source cited",
    "GX2": "source not returned by the search",
    "GX3": "claim not in the cited text",
    "GAV": "gap verifier",
}


def _decision(f: GapFindingView) -> str:
    label = DECISIONS.get(f.disposition, f.disposition)
    return f"Decision: {label}" + (f" ({f.disposition_note})" if f.disposition_note else "")


def _steps(f: GapFindingView) -> str:
    return ", ".join(e.label for e in f.elements if e.label)


def _severity(f: GapFindingView) -> str:
    return f"{SEVERITY.get(f.severity or '', 'No')} severity"


def _sides(f: GapFindingView) -> list[str]:
    lines = []
    for side, label in (("documents", "Documents"), ("practice", "Practice")):
        places = list(
            dict.fromkeys(  # a place cited twice (two quotes from one passage) is listed once
                " ".join(part for part in (e.source_name, e.anchor) if part) + f" ({e.stance})"
                for e in f.evidence
                if e.side == side
            )
        )
        if places:
            lines.append(f"  - {label}: {'; '.join(places)}")
    return lines


GAP_CLASSES = {
    "effective_adaptation": "Effective adaptation",
    "risky_drift": "Risky drift",
    "obsolete_rule": "Obsolete rule",
    "unexplained": "Unexplained",
}


def _gap_class(f: GapFindingView) -> list[str]:
    """A reality gap's class (§3.12.7): proposed from an SME's stated reason, or unexplained;
    confirmed once Eric decides the finding. The reason's words stay in the app."""
    if f.gap_class is None:
        return []
    state = "proposed" if f.disposition == "open" else "confirmed"
    why = (
        "no reason stated; asked as a question"
        if f.gap_class == "unexplained"
        else "from a reason an SME stated"
    )
    cause = f" · cause: {f.cause_type.replace('_', ' ')}" if f.cause_type else ""
    return [f"  - Gap class: {GAP_CLASSES.get(f.gap_class, f.gap_class)} ({state}; {why}){cause}"]


def _internal(report: GapReport) -> list[str]:
    facts = [f for f in report.findings if f.section == "fact"]
    patterns = [f for f in report.findings if f.section == "interpretation"]
    updates = [f for f in report.findings if f.section == "recommendation"]
    lines = ["## 1. Facts", ""]
    for f in facts:
        steps = f" · steps: {_steps(f)}" if _steps(f) else ""
        lines += [f"- [O] {f.title} · {_severity(f)}{steps}", f"  - {f.text}", *_sides(f)]
        lines += _gap_class(f)
    lines += [] if facts else ["No differences between the documents and practice were kept."]
    lines += ["", "## 2. Interpretation", ""]
    for f in patterns:
        lines += [f"- [I] {f.title}: {f.text}", f"  - Basis: {f.basis}", *_gap_class(f)]
    lines += [] if patterns else ["No pattern or likely cause was supported by what the SMEs said."]
    lines += ["", "## 3. Recommendation", ""]
    lines += ["### Documentation updates", ""]
    lines += [f"- [I] {f.title}: {f.text} · {_decision(f)}" for f in updates] or [
        "No documentation updates proposed."
    ]
    lines += ["", "### Questions for the SMEs", ""]
    lines += [f"- {q.question} · {_decision(q)}" for q in report.questions] or ["No questions."]
    lines += ["", "### Decisions on the differences", ""]
    lines += [f"- [{f.provenance}] {f.title} · {_decision(f)}" for f in facts + patterns] or [
        "No differences to decide on."
    ]
    return lines


def _external(report: GapReport) -> list[str]:
    lines = ["## 1. Facts", ""]
    for f in report.findings:
        lines.append(f"- [R] {f.title}: {f.text}")
        for e in f.evidence:
            tier = e.tier.replace("_", " ")
            when = e.page_age or "date not given"
            lines.append(f"  - {e.source_name} ({tier}, {when}) {e.url}: “{e.quote}”")
    lines += [] if report.findings else ["No finding from published practice was kept."]
    lines += ["", "## 2. Interpretation", ""]
    for f in report.findings:
        compared = (
            f"different from the map: {_steps(f)}"
            if f.comparison == "different" and _steps(f)
            else "absent from the current map"
        )
        strength = f" · {STRENGTH[f.evidence_strength]}" if f.evidence_strength in STRENGTH else ""
        notes = "".join(f" {n}" for n in f.notes)
        lines.append(f"- [R] {f.title}: {compared} · {_severity(f)}{strength}.{notes}")
    lines += [] if report.findings else ["Nothing to compare."]
    lines += ["", "## 3. Recommendation", ""]
    lines += [f"- [R] Consider: {f.title} · {_decision(f)}" for f in report.findings] or [
        "No candidate changes."
    ]
    return lines


def render_report_md(report: GapReport, process_name: str) -> str:
    a = report.analysis
    lines = [
        f"# {process_name} — Gap analysis: {TITLES.get(a.mode, a.mode)}",
        f"Version {a.version_label} · run {display_date(a.completed_at or a.created_at)} · "
        f"finalised {display_date(a.finalised_at or '') or 'not yet'}",
        ADVISORY,
        "",
    ]
    lines += _internal(report) if a.mode == "internal" else _external(report)
    lines += ["", "## Rejected findings", ""]
    counts = Counter(f.rejection_guardrail for f in report.rejected)
    lines += [f"- {g} ({GUARDRAILS.get(g, g)}): {n}" for g, n in sorted(counts.items())] or [
        "None."
    ]
    if a.notes:
        lines += ["", "## Notes", "", *(f"- {n}" for n in a.notes)]
    return "\n".join(lines) + "\n"
