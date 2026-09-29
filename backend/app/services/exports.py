"""Exports of a version (PRD §7.3, constraints 9-11): pure renderers, no database.

- `render_master_map_md`: the Master Process Map from the fixed template, in three separate
  sections (1 Facts · 2 Interpretation · 3 Recommendation). Every element line carries its
  provenance tag; role names only; no verbatim quotes and no images.
- `render_graph_json`: the graph JSON of PRD §3.6 with the quality card in `version`.
- `render_raci_csv`: steps by roles, a contested Accountable written `A?`.

Rejected steps are not part of the map: they and their lines are left out of every export. The
text comes from the graph, which already has names on the redaction list replaced by roles.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from app.domain.enums import (
    DivergenceType,
    EdgeKind,
    ElementKind,
    Provenance,
    ReviewStatus,
    SourceState,
    Stance,
)
from app.domain.exports import ExportCause, ExportGapReport, ExportInput
from app.domain.graph import Graph, GraphElement
from app.domain.quality import QualityCard
from app.services import signal

STEP_KINDS = {ElementKind.ACTIVITY.value, ElementKind.DECISION.value, ElementKind.APPROVAL.value}
DECIDING = {ElementKind.DECISION.value, ElementKind.APPROVAL.value}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

SOURCE_KINDS = {
    "interview_transcript": "Interview",
    "sop": "SOP",
    "manual": "Manual",
    "job_description": "Job description",
    "executed_artefact": "Executed artefact",
    "other": "Document",
}
STATES = {
    SourceState.CORROBORATED.value: "Corroborated",
    SourceState.DOCUMENTED_ONLY.value: "Documented only",
    SourceState.PRACTICED_ONLY.value: "Practiced only",
    SourceState.CONTESTED.value: "Contested",
    SourceState.TRACE_CONTRADICTED.value: "Trace contradicted",
    SourceState.NOT_ASSESSED.value: "Not assessed",
}
DIVERGENCES = {
    DivergenceType.SEQUENCE.value: "Sequence",
    DivergenceType.OWNERSHIP.value: "Ownership",
    DivergenceType.THRESHOLD.value: "Threshold",
    DivergenceType.TRIGGER.value: "Trigger",
    DivergenceType.EXCEPTION.value: "Exception",
    DivergenceType.OMISSION.value: "Omission",
}
MECHANISMS = {"rule_based": "rule-based", "judgment": "judgment", "none": "mechanism not stated"}
COMPONENTS = {
    "perception": "Perception",
    "knowledge_base": "Knowledge base",
    "reasoning": "Reasoning",
    "learning": "Learning",
    "communication": "Communication",
    "action": "Action",
}
BASES = {
    "rule_based_automate_candidate": "Rule-based: an automation candidate",
    "judgment_support_only": "Judgment: support the person, never automate",
}
REASONS = {
    "contested": "contested",
    "documented_only": "documented only",
    "inferred": "inferred",
    "partial_support": "partial support",
    "low_confidence": "low confidence",
    "gap": "gap",
    "gap_analysis": "gap analysis",
}
EXIT_WORDS = {kind.value: kind.value.capitalize() for kind in EdgeKind}
STATUS_WORDS = {"pass": "Pass", "fail": "Fail", "warning": "Warning"}
NO_PHASE = "Without a phase"

# Headings of the fixed template, in order (the quality card's Q7 checks them).
FACTS = "## 1. Facts: what the sources tell us"
INTERPRETATION = "## 2. Interpretation: how the process works"
RECOMMENDATION = "## 3. Recommendation: enablement and gaps"


# --- Helpers -----------------------------------------------------------------------------------


def on_the_map(graph: Graph) -> Graph:
    """The graph without rejected steps and the lines that touch them."""
    kept = [e for e in graph.elements if e.review_status != ReviewStatus.REJECTED.value]
    ids = {e.id for e in kept}
    edges = [e for e in graph.edges if e.from_ in ids and e.to in ids]
    return graph.model_copy(update={"elements": kept, "edges": edges})


def display_date(iso: str) -> str:
    """ "28 Sep 2026"; "" when there is no date."""
    if not iso:
        return ""
    try:
        moment = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{moment.day} {MONTHS[moment.month - 1]} {moment.year}"


GAP_MODES = {"internal": "Documents vs practice", "external": "External best practice"}


def cause_line(c: ExportCause) -> str:
    """ "- [O] <step> · <type>: <pattern> [I] Likely cause: …" (or not known yet)."""
    cause = (
        f"[I] Likely cause: {c.inferred_cause}"
        if c.inferred_cause
        else "Likely cause: not known yet: ask your SMEs."
    )
    return f"- [O] {c.element_label} · {c.divergence_type}: {c.pattern} {cause}"


def gap_report_line(r: ExportGapReport) -> str:
    """ "- <mode> · finalised <date> · <n> accepted findings: <title>; <title>"."""
    count = len(r.accepted)
    found = f"{count} accepted finding" if count == 1 else f"{count} accepted findings"
    titles = f": {'; '.join(r.accepted)}" if r.accepted else ""
    mode = GAP_MODES.get(r.mode, r.mode)
    return f"- {mode} · finalised {display_date(r.finalised_at)} · {found}{titles}"


def minutes(value: float | None) -> str:
    """ "20 min", or "not stated"."""
    if value is None:
        return "not stated"
    return f"{value:g} min"


def cell(text: str) -> str:
    """Text safe inside a Markdown table cell."""
    return " ".join(text.split()).replace("|", "\\|") or "—"


def tag(element: GraphElement) -> str:
    return f"[{element.provenance}]"


def plural(count: int, one: str, many: str | None = None) -> str:
    return f"{count} {one if count == 1 else (many or one + 's')}"


def role_order(graph: Graph) -> list[str]:
    """Role IDs used by the steps' RACI, in lane order and then by name."""
    used = {r.role_id for e in graph.elements for r in e.raci}
    roles = sorted(
        (r for r in graph.roles if r.id in used),
        key=lambda r: (r.lane_order is None, r.lane_order or 0, r.name),
    )
    return [r.id for r in roles]


def raci_cell(element: GraphElement, role_id: str) -> str:
    letters = [
        "A?" if r.letter == "A" and r.contested else r.letter
        for r in element.raci
        if r.role_id == role_id
    ]
    return " ".join(letters)


def cited_passages(element: GraphElement, names: dict[str, str]) -> str:
    """ "file.txt 06:40; sop.docx §3.1": the verified passages that support a step."""
    cited = [
        f"{names.get(ev.source_id, SOURCE_KINDS.get(ev.source_kind, 'Document'))} {ev.anchor}"
        for ev in element.evidence
        if ev.stance == Stance.SUPPORTS.value and ev.segment_id and ev.verified
    ]
    return "; ".join(dict.fromkeys(cited)) or "no passage recorded"


def steps(graph: Graph) -> list[GraphElement]:
    return [e for e in graph.elements if e.kind in STEP_KINDS]


# --- Master Process Map (Markdown) -------------------------------------------------------------


def quality_card_lines(card: QualityCard | None) -> list[str]:
    if card is None:
        return ["Quality card: not worked out yet."]
    lines = ["**Quality card**", "", "| Check | Status | Detail |", "|---|---|---|"]
    lines += [
        f"| {c.id} {cell(c.name)} | {STATUS_WORDS[c.status]} | {cell(c.detail)} |"
        for c in card.checks
    ]
    lines += ["", f"All hard checks green: {'yes' if card.all_green else 'no'}."]
    if card.warnings:
        lines += ["", "Warnings:"] + [f"- {w}" for w in card.warnings]
    return lines


def _facts(data: ExportInput, graph: Graph) -> list[str]:
    names = {s.id: s.name for s in data.sources}
    lines = [FACTS, "", "### Source registry", ""]
    if data.sources:
        lines += [
            "| Source | Kind | Version date | Owner | Controlled copy |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {cell(s.name)} | {SOURCE_KINDS.get(s.kind, 'Document')} | {cell(s.version_date)} "
            f"| {cell(s.owner)} | {'Yes' if s.controlled_copy else 'No'} |"
            for s in data.sources
        ]
    else:
        lines.append("No sources recorded.")

    lines += ["", "### Pain points as stated in the sources", ""]
    pains = []
    for element in steps(graph):
        where = cited_passages(element, names)
        pains += [
            f"- [O] {c.text} (step: {element.label} · {where})"
            for c in element.constraints
            if c.provenance == Provenance.OBSERVED.value
        ]
    lines += pains or ["None stated in the sources."]

    lines += ["", "### How well the sources agree", "", "| Source state | Steps |", "|---|---|"]
    for state, words in STATES.items():
        count = sum(1 for e in steps(graph) if e.source_state == state)
        lines.append(f"| {words} | {count} |")
    return lines


def _phase_groups(graph: Graph) -> list[tuple[str, str, list[GraphElement]]]:
    """(name, time window, steps) per phase in order; steps without a phase last."""
    groups = [
        (p.name, p.time_window, [e for e in steps(graph) if e.phase_id == p.id])
        for p in sorted(graph.phases, key=lambda p: p.order)
    ]
    known = {p.id for p in graph.phases}
    loose = [e for e in steps(graph) if e.phase_id not in known]
    if loose:
        groups.append((NO_PHASE, "", loose))
    return [g for g in groups if g[2]]


def _interpretation(graph: Graph) -> list[str]:
    roles = {r.id: r.name for r in graph.roles}
    labels = {e.id: e.label for e in graph.elements}
    lines = [INTERPRETATION]
    for index, (name, window, members) in enumerate(_phase_groups(graph), start=1):
        activities = [e for e in members if e.kind == ElementKind.ACTIVITY.value]
        deciding = [e for e in members if e.kind in DECIDING]
        lanes = list(dict.fromkeys(roles.get(e.lane_role_id or "", "") for e in members))
        lines += ["", f"### Phase {index}: {name}", ""]
        lines.append(f"Time window: {window or 'not stated'}.")
        lines.append(
            f"Purpose: covers {plural(len(members), 'step')}, "
            f"from “{members[0].label}” to “{members[-1].label}”."
        )
        if activities:
            lines += [
                "",
                "| Step | Lane | Prov | Source state | Time (work/wait) | Complexity "
                "| Data in → out | Flags |",
                "|---|---|---|---|---|---|---|---|",
            ]
            for e in activities:
                time = f"{minutes(e.time.work_min)} / {minutes(e.time.wait_min)}"
                data = (
                    f"{e.handoff.in_ or '—'} → {e.handoff.out or '—'}"
                    if e.handoff.in_ or e.handoff.out
                    else "—"
                )
                flags = [
                    word
                    for word, present in (
                        ("key constraint", any(c.is_key for c in e.constraints)),
                        ("AI flag", e.ai_flag is not None),
                        ("knowledge risk", bool(e.k_risk)),
                    )
                    if present
                ]
                lines.append(
                    f"| {cell(e.label)} | {cell(roles.get(e.lane_role_id or '', ''))} | {tag(e)} "
                    f"| {STATES.get(e.source_state, e.source_state)} | {time} "
                    f"| {e.complexity or '—'} | {cell(data)} | {', '.join(flags) or '—'} |"
                )
        if deciding:
            lines += ["", "Decisions and approvals:", ""]
            for e in deciding:
                exits = [
                    f"{edge.label or EXIT_WORDS.get(edge.kind, edge.kind)} → "
                    f"{labels.get(edge.to, '')}"
                    for edge in graph.edges
                    if edge.from_ == e.id
                ]
                who = roles.get(e.decision.decider_role_id or e.lane_role_id or "", "not stated")
                decider = "approver" if e.kind == ElementKind.APPROVAL.value else "decider"
                lines.append(
                    f"- {tag(e)} {e.label} ({e.kind}, "
                    f"{MECHANISMS.get(e.decision.mechanism, e.decision.mechanism)}, "
                    f"{decider}: {who}). Exits: {'; '.join(exits) or 'none'}."
                )
        lines += [
            "",
            f"This phase has {plural(len(activities), 'activity', 'activities')} and "
            f"{plural(len(deciding), 'decision or approval', 'decisions or approvals')}, "
            f"involving {', '.join(r for r in lanes if r) or 'no named role'}.",
        ]

    order = role_order(graph)
    lines += ["", "### RACI", ""]
    if order:
        lines.append("| Step | " + " | ".join(cell(roles.get(r, "")) for r in order) + " |")
        lines.append("|---|" + "---|" * len(order))
        for e in steps(graph):
            row = [raci_cell(e, r) or "·" for r in order]
            lines.append(f"| {tag(e)} {cell(e.label)} | " + " | ".join(row) + " |")
        lines += ["", "A? means the sources disagree about who is accountable."]
    else:
        lines.append("No roles recorded.")

    lines += ["", "### Divergences between sources", ""]
    divergences = [
        (words, [e.label for e in steps(graph) if kind in e.divergence_types])
        for kind, words in DIVERGENCES.items()
    ]
    found = [(words, members) for words, members in divergences if members]
    if found:
        lines += ["| Divergence | Steps |", "|---|---|"]
        lines += [f"| {words} | {cell(', '.join(members))} |" for words, members in found]
    else:
        lines.append("No divergences between the sources.")
    return lines


def _recommendation(data: ExportInput, graph: Graph) -> list[str]:
    lines = [RECOMMENDATION, "", "### AI flags", ""]
    flagged = [e for e in steps(graph) if e.ai_flag is not None]
    for e in flagged:
        flag = e.ai_flag
        assert flag is not None
        lines += [
            f"**{tag(e)} {e.label}**",
            "",
            f"- Component: {COMPONENTS.get(flag.component, flag.component)}",
            f"- Input: {flag.input}",
            f"- Output: {flag.output}",
            f"- Handoff: {flag.handoff}",
            f"- Basis: {BASES.get(flag.basis, flag.basis)}",
            "",
        ]
    if not flagged:
        lines += ["No AI flags.", ""]

    lines += ["### Knowledge-risk register", ""]
    risks = [f"- {tag(e)} {e.label}: {e.k_risk}" for e in steps(graph) if e.k_risk]
    lines += (risks or ["No knowledge risks recorded."]) + [""]

    lines += ["### External-practice register", ""]
    external = [
        f"- {tag(e)} {e.label}: {e.r_reference or 'no reference recorded'}"
        for e in steps(graph)
        if e.provenance == Provenance.RECOMMENDED.value
    ]
    lines += (external or ["No steps from external practice."]) + [""]

    lines += ["### Open validation questions", ""]
    questions = []
    for number, q in enumerate(data.open_questions, start=1):
        about = [
            part for part in (q.element_label and f"step: {q.element_label}", q.phase_name) if part
        ]
        where = f" ({' · '.join(about)})" if about else ""
        questions.append(f"{number}. {q.question}{where} · {REASONS.get(q.reason, q.reason)}")
    lines += (questions or ["No open questions."]) + [""]

    lines += ["### Cause library entries (pending validation)", ""]
    lines += [cause_line(c) for c in data.causes] or ["No cause library entries yet."]
    lines += ["", "### Gap analyses", ""]
    lines += [gap_report_line(r) for r in data.gap_reports] or ["No finalised gap analyses."]
    return lines


def signal_text(data: ExportInput) -> str:
    """ "Signal strength: Strong (3 of 3). Built from …" or "" without an interview (P12)."""
    strength = signal.signal_strength(s.kind for s in data.sources)
    if strength is None:
        return ""
    return f"Signal strength: {strength.label} ({strength.score} of 3). {strength.detail}"


def signal_lines(data: ExportInput) -> list[str]:
    text = signal_text(data)
    return [text, ""] if text else []


def render_master_map_md(data: ExportInput) -> str:
    graph = on_the_map(data.graph)
    published = display_date(data.published_at)
    header = [
        f"# {graph.process.name} — Master Process Map",
        "",
        f"Version {graph.version.label} · "
        + (f"published {published}" if published else "not published yet")
        + f" · validated by {data.validated_by or 'not recorded'}",
        "",
        *signal_lines(data),
    ]
    body = (
        header
        + quality_card_lines(data.quality_card)
        + [""]
        + _facts(data, graph)
        + [""]
        + _interpretation(graph)
        + [""]
        + _recommendation(data, graph)
    )
    return "\n".join(body) + "\n"


# --- Graph JSON and RACI CSV -------------------------------------------------------------------


def render_graph_json(data: ExportInput) -> str:
    graph = on_the_map(data.graph)
    card = data.quality_card.model_dump(mode="json") if data.quality_card else None
    graph = graph.model_copy(
        update={"version": graph.version.model_copy(update={"quality_card": card})}
    )
    return json.dumps(graph.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"


def render_raci_csv(data: ExportInput) -> str:
    """Steps by roles; a byte-order mark first so spreadsheet programs read the accents right."""
    graph = on_the_map(data.graph)
    roles = {r.id: r.name for r in graph.roles}
    order = role_order(graph)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(["Step", "Kind", "Lane", "Provenance", *(roles[r] for r in order)])
    for e in steps(graph):
        writer.writerow(
            [e.label, e.kind, roles.get(e.lane_role_id or "", ""), e.provenance]
            + [raci_cell(e, r) for r in order]
        )
    return "﻿" + buffer.getvalue()
