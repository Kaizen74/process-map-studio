"""The interactive map as one offline HTML file (PRD §7.3, §3.10; constraints 9-11, 20).

Drawn from the backend layout of the published map (rejected steps left out), styled with the
shared design tokens (`shared/design_tokens.json`, passed in) and the self-hosted IBM Plex fonts
embedded as data (passed in as bytes). A Content-Security-Policy forbids every outside request;
there is no script: each step on the map links to its details further down the page.
Sections as the Master Process Map: 1 Facts, 2 Interpretation, 3 Recommendation. Both views are
drawn (As done, then As documented; §3.12.11), with "not described" connectors dashed. Role names
only; no verbatim quotes; no images.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from itertools import pairwise
from pathlib import Path

from app.domain.enums import EdgeKind, ElementKind, Provenance
from app.domain.exports import ExportInput
from app.domain.graph import Graph, GraphElement
from app.domain.layout import Layout, TextPos
from app.domain.quality import QualityCard
from app.services import exports as md
from app.services.layout import compute_layout

TIMED = {ElementKind.ACTIVITY.value, ElementKind.APPROVAL.value}
KINDS = md.KINDS
STANCES = {"supports": "supports", "contradicts": "contradicts", "silent": "silent"}
PROVENANCE = {"O": "Observed (O)", "I": "Inferred (I)", "R": "Recommended (R)"}
# A draft's map (2026-10-28): each step says how far its review has got.
REVIEW_WORDS = {"draft": "Not reviewed yet", "confirmed": "Confirmed", "edited": "Edited",
                "added": "Added"}  # fmt: skip
STEP_KINDS = {"activity", "decision", "approval"}
# Only a draft's map carries this rule, so a published map's file is unchanged.
DRAFT_STYLE = (
    ".draft-stamp { margin: var(--space-8) 0 0; padding: var(--space-8) var(--space-12); "
    "border: var(--line-hairline) dashed var(--danger-text); color: var(--danger-text); "
    "background: var(--danger-bg); font-weight: var(--weight-medium); }"
)
DRAFT_STAMP = (
    "Draft: not reviewed, not published. {reviewed} of {total} steps reviewed. Nothing in it is "
    "validated yet."
)
LETTERS = {"R": "Responsible", "A": "Accountable", "C": "Consulted", "I": "Informed"}
BACK = "Back to the map"  # each step card links back up (2026-10-30)

# The self-hosted font files (frontend/public/fonts) and the characters each one covers.
LATIN = (
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, "
    "U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD"
)
LATIN_EXT = (
    "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, "
    "U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, "
    "U+2C60-2C7F, U+A720-A7FF"
)
FONT_FILES = [
    (f"ibm-plex-{face}-{subset}-{weight}-normal.woff2", family, weight, ranges)
    for face, family in (("sans", "IBM Plex Sans"), ("mono", "IBM Plex Mono"))
    for weight in ("400", "500")
    for subset, ranges in (("latin-ext", LATIN_EXT), ("latin", LATIN))
]
CSP = "default-src 'none'; style-src 'unsafe-inline'; font-src data:"

STYLE = (Path(__file__).with_name("export_html.css")).read_text(encoding="utf-8")


def e(text: object) -> str:
    return escape(str(text), quote=True)


# PRD §5.2: the impact and Reality tokens belong to the Reality views, the Reality pack and their
# legend only; the map export never uses them.
REALITY_TOKENS = ("impact-", "designed-work", "baseline-")


def tokens_css(tokens: dict[str, object], *, reality: bool = False) -> str:
    """The tokens as CSS custom properties, named as the app's generated tokens.css (the Reality
    colours only for the Reality pack)."""
    lines = [":root {"]
    for group, values in tokens.items():
        if group.startswith("$") or not isinstance(values, dict):
            continue
        for name, value in values.items():
            if group == "color" and name.startswith(REALITY_TOKENS) and not reality:
                continue
            prop = f"--{name}" if group == "color" else f"--{group}-{name}"
            lines.append(f"  {prop}: {value};")
    lines.append("}")
    return "\n".join(lines)


@lru_cache(maxsize=16)
def _base64(data: bytes) -> str:
    """A font file as base64 text, worked out once per file (the quality card renders the HTML
    export on every look)."""
    return base64.b64encode(data).decode("ascii")


def fonts_css(fonts: dict[str, bytes]) -> str:
    """@font-face rules with each font file embedded as data (no outside request)."""
    rules = []
    for file, family, weight, ranges in FONT_FILES:
        data = fonts.get(file)
        if data is None:
            continue
        encoded = _base64(data)
        rules.append(
            f"@font-face {{ font-family: '{family}'; font-style: normal; font-weight: {weight}; "
            f"font-display: swap; src: url(data:font/woff2;base64,{encoded}) format('woff2'); "
            f"unicode-range: {ranges}; }}"
        )
    return "\n".join(rules)


def at(pos: TextPos, *, chip: bool = False) -> str:
    shift = {"left": "0", "center": "-50%", "right": "-100%"}[pos.align]
    move = f"translateX({shift})" + (" translateY(-50%)" if chip else "")
    return f"left:{pos.x}px;top:{pos.y}px;transform:{move}"


def lens_text(element: GraphElement) -> tuple[str, bool]:
    """The plain lens line under a step: its time, or "No time stated" (danger) when timed."""
    work, wait = element.time.work_min, element.time.wait_min
    if work is None and wait is None:
        return ("No time stated", True) if element.kind in TIMED else ("", False)
    if not wait:
        return f"~{work or 0:g} min", False
    if not work:
        return f"{wait:g} min wait", False
    return f"~{work:g} min + {wait:g} wait", False


def _map(graph: Graph, layout: Layout) -> str:
    elements = {el.id: el for el in graph.elements}
    roles = {r.id: r.name for r in graph.roles}
    band = layout.lanes[0].y if layout.lanes else 0
    out = [
        f'<div class="scroll"><div class="map" role="group" aria-label="Swimlane map" '
        f'style="width:{layout.canvas.w}px;height:{layout.canvas.h}px">',
        f'<div class="band" style="height:{band}px">'
        f'<span style="left:0;width:var(--layout-map-label-column)"><small>Phase</small></span>',
    ]
    out += [
        f'<span style="left:{p.x}px;width:{p.w}px"><b>{e(p.label)}</b>'
        f'<small class="mono">{e(p.time_window)}</small></span>'
        for p in layout.phases
    ]
    out.append("</div>")
    for index, lane in enumerate(layout.lanes):
        steps = md.plural(lane.step_count, "step")
        out.append(
            f'<div class="lane{" even" if index % 2 else ""}" role="group" '
            f'aria-label="{e(lane.label)} lane, {steps}" style="top:{lane.y}px;height:{lane.h}px">'
            f"<span><b>{e(lane.label)}</b><small>{steps}</small></span></div>"
        )
    out += [
        f'<div class="divider" style="left:{p.x}px;height:{layout.canvas.h}px"></div>'
        for p in layout.phases[1:]
    ]
    for edge in layout.edges:
        kind = "gap" if edge.kind == EdgeKind.GAP.value else "back" if edge.is_back_edge else "edge"
        parts = [f'<div class="{kind}" aria-hidden="true">']
        points = edge.points
        for (x1, y1), (x2, y2) in pairwise(points):
            if y1 == y2 and x1 != x2:
                style = f"left:{min(x1, x2)}px;top:{y1}px;width:{abs(x2 - x1)}px"
                parts.append(f'<i class="seg h" style="{style}"></i>')
            elif x1 == x2 and y1 != y2:
                style = f"left:{x1}px;top:{min(y1, y2)}px;height:{abs(y2 - y1)}px"
                parts.append(f'<i class="seg v" style="{style}"></i>')
        if len(points) >= 2:
            (x1, y1), (x2, y2) = points[-2], points[-1]
            way = ("right" if x2 > x1 else "left") if y1 == y2 else ("down" if y2 > y1 else "up")
            parts.append(f'<i class="arrow {way}" style="left:{x2}px;top:{y2}px"></i>')
        if edge.label and edge.label_pos:
            parts.append(
                f'<span class="chip" style="{at(edge.label_pos, chip=True)}">{e(edge.label)}</span>'
            )
        parts.append("</div>")
        out.append("".join(parts))
    for node in layout.nodes:
        el = elements.get(node.id)
        if el is None:
            continue
        state = md.STATES.get(el.source_state, "") if el.kind in md.STEP_KINDS else ""
        words = (KINDS.get(el.kind, el.kind), el.label, roles.get(el.lane_role_id or "", ""), state)
        name = ", ".join(x for x in words if x)
        box = f"left:{node.x}px;top:{node.y}px;width:{node.w}px;height:{node.h}px"
        lines = "".join(f"<span>{e(line)}</span>" for line in node.label_lines)
        size = f"width:{node.w}px;height:{node.h}px"
        inner = {
            "diamond": '<span class="dia"></span>',
            "circle": f'<span class="dot" style="{size}"></span>',
            "double_circle": f'<span class="dot" style="{size}"></span>',
        }.get(node.shape, f'<span class="label" aria-hidden="true">{lines}</span>')
        key = '<span class="key"></span>' if any(c.is_key for c in el.constraints) else ""
        out.append(
            f'<a class="node {node.shape}" href="#step-{e(el.id)}" aria-label="{e(name)}" '
            f'title="{e(el.label)}" style="{box}">{inner}{key}</a>'
        )
        if node.shape == "diamond":
            align = " left" if node.label_pos.align == "left" else ""
            where = at(node.label_pos)
            out.append(
                f'<div class="under{align}" aria-hidden="true" style="{where}">{lines}</div>'
            )
        text, danger = lens_text(el)
        if text:
            out.append(
                f'<div class="lens{" danger" if danger else ""}" aria-hidden="true" '
                f'style="{at(node.lens_pos)}">{e(text)}</div>'
            )
    out.append("</div></div>")
    out.append(
        '<p class="legend">Rounded box: activity · Diamond: decision · Pill: approval · '
        "Dot: start · Double ring: end · Orange dot: key constraint · Dashed line: a loop back "
        "(rework or re-plan), or a step the interview doesn't describe · Under each step: its "
        "time</p>"
    )
    return "\n".join(out)


def _card(card: QualityCard | None) -> str:
    if card is None:
        return '<p class="note">Quality card: not worked out yet.</p>'
    rows = "".join(
        f'<tr><td class="mono">{e(c.id)}</td><td>{e(c.name)}</td>'
        f'<td class="{c.status}">{md.STATUS_WORDS[c.status]}</td><td>{e(c.detail)}</td></tr>'
        for c in card.checks
    )
    warnings = "".join(f"<li>{e(w)}</li>" for w in card.warnings)
    return (
        '<table><caption class="note">Quality card</caption><thead><tr><th>Check</th>'
        "<th>Name</th><th>Status</th><th>Detail</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        f"<p>All hard checks green: {'yes' if card.all_green else 'no'}.</p>"
        + (f"<p>Warnings:</p><ul>{warnings}</ul>" if warnings else "")
    )


def _table(head: list[str], rows: list[list[str]]) -> str:
    """A table from already-escaped cells."""
    th = "".join(f'<th scope="col">{h}</th>' for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    table = f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"
    return f'<div class="scroll">{table}</div>'


def _facts(data: ExportInput, graph: Graph) -> str:
    names = {s.id: s.name for s in data.sources}
    parts = ['<section aria-labelledby="facts">', f'<h2 id="facts">{e(md.FACTS[3:])}</h2>']
    parts.append("<h3>Source registry</h3>")
    registry = [
        [
            e(s.name),
            md.SOURCE_KINDS.get(s.kind, "Document"),
            e(s.version_date or "—"),
            e(s.owner or "—"),
            "Yes" if s.controlled_copy else "No",
        ]
        for s in data.sources
    ]
    head = ["Source", "Kind", "Version date", "Owner", "Controlled copy"]
    parts.append(_table(head, registry) if registry else "<p>No sources recorded.</p>")
    if other := md.other_flows_line(data):
        parts.append(f"<p>{e(other)}</p>")
    parts.append("<h3>Pain points as stated in the sources</h3>")
    pains = []
    for el in md.steps(graph):
        where = md.cited_passages(el, names)
        pains += [
            f"<li>[O] {e(c.text)} (step: {e(el.label)} · {e(where)})</li>"
            for c in el.constraints
            if c.provenance == Provenance.OBSERVED.value
        ]
    parts.append(f"<ul>{''.join(pains)}</ul>" if pains else "<p>None stated in the sources.</p>")
    parts.append("<h3>How well the sources agree</h3>")
    parts.append(
        _table(
            ["Source state", "Steps"],
            [
                [w, str(sum(1 for s in md.steps(graph) if s.source_state == k))]
                for k, w in md.STATES.items()
            ],
        )
    )
    parts.append("<h3>Stories</h3>")
    stories = [f"<li>{e(md.story_line(x))}</li>" for x in data.stories]
    parts.append(f"<ul>{''.join(stories)}</ul>" if stories else "<p>No stories recorded.</p>")
    parts.append("<h3>Strengths as stated (preserve)</h3>")
    strengths = [f"<li>{e(md.capability_line(c))}</li>" for c in data.capabilities
                 if c.kind == "strength"]  # fmt: skip
    parts.append(f"<ul>{''.join(strengths)}</ul>" if strengths else "<p>No strengths stated.</p>")
    parts.append("</section>")
    return "\n".join(parts)


def _details(data: ExportInput, graph: Graph, el: GraphElement) -> str:
    roles = {r.id: r.name for r in graph.roles}
    phases = {p.id: p.name for p in graph.phases}
    names = {s.id: s.name for s in data.sources}
    labels = {x.id: x.label for x in graph.elements}
    rows: list[tuple[str, str]] = [
        ("Kind", KINDS.get(el.kind, el.kind)),
        ("Lane", roles.get(el.lane_role_id or "", "—")),
        ("Phase", phases.get(el.phase_id or "", "—")),
        ("Provenance", PROVENANCE.get(el.provenance, el.provenance)),
        ("Source state", md.STATES.get(el.source_state, el.source_state)),
        ("Time", f"work {md.minutes(el.time.work_min)}, wait {md.minutes(el.time.wait_min)}"
                 + (f" ({el.time.text})" if el.time.text else "")),
    ]  # fmt: skip
    if el.view_membership:
        rows.append(("View", md.view_word(el)))
    if el.work_type:
        rows.append(("Work type", md.work_type_text(el)))
    if el.complexity:
        rows.append(("Complexity", el.complexity))
    if el.kpi:
        rows.append(("KPI", el.kpi))
    if el.kind in md.DECIDING:
        d = el.decision
        rows.append(("Mechanism", md.MECHANISMS.get(d.mechanism, d.mechanism)))
        rows.append(
            ("Decider", roles.get(d.decider_role_id or el.lane_role_id or "", "not stated"))
        )
        if d.rule_or_threshold:
            rows.append(("Rule or threshold", d.rule_or_threshold))
        if d.escalation:
            rows.append(("Escalation", d.escalation))
        exits = [
            f"{x.label or md.EXIT_WORDS.get(x.kind, x.kind)} → {labels.get(x.to, '')}"
            for x in graph.edges
            if x.from_ == el.id
        ]
        rows.append(("Exits", "; ".join(exits) or "none"))
    if el.handoff.in_ or el.handoff.out:
        rows.append(("Data in → out", f"{el.handoff.in_ or '—'} → {el.handoff.out or '—'}"))
    letters: dict[str, list[str]] = {}  # each role once, its letters in order (2026-10-30)
    for r in el.raci:
        word = LETTERS.get(r.letter, r.letter) + (" (contested)" if r.contested else "")
        letters.setdefault(r.role_id, []).append(word)
    raci = [f"{roles.get(role_id, '')}: {_and(words)}" for role_id, words in letters.items()]
    if raci:
        rows.append(("Roles", "; ".join(raci)))
    for c in el.constraints:
        rows.append(("Constraint", f"[{c.provenance}] {c.text}" + (" (key)" if c.is_key else "")))
    evidence = [
        f"{names.get(ev.source_id, md.SOURCE_KINDS.get(ev.source_kind, 'Document'))}"
        + (f" {ev.anchor}" if ev.anchor else "")
        + f" · {STANCES.get(ev.stance, ev.stance)}"
        for ev in el.evidence
    ]
    if evidence:
        rows.append(("Sources", "; ".join(evidence)))
    if el.provenance == Provenance.RECOMMENDED.value:
        rows.append(("Reference", el.r_reference or "none recorded"))
    if not data.published_at and el.kind in STEP_KINDS:
        rows.append(("Review", REVIEW_WORDS.get(el.review_status, el.review_status)))
    body = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in rows)
    return (
        f'<article class="card step" id="step-{e(el.id)}" aria-labelledby="h-{e(el.id)}">'
        f'<h3 id="h-{e(el.id)}">[{e(el.provenance)}] {e(el.label)}</h3><dl>{body}</dl>'
        f'<p class="step__back"><a href="#interpretation">{BACK}</a></p></article>'
    )


def _and(words: list[str]) -> str:
    """Words joined as in a sentence: a; a and b; a, b and c."""
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"


def _interpretation(data: ExportInput, graph: Graph) -> str:
    roles = {r.id: r.name for r in graph.roles}
    order = md.role_order(graph)
    parts = [
        '<section aria-labelledby="interpretation">',
        f'<h2 id="interpretation">{e(md.INTERPRETATION[3:])}</h2>',
        '<p class="note">Select a step to read its details below.</p>',
        *_maps(data, graph),
        "<h3>Steps</h3>",
    ]
    parts += [_details(data, graph, el) for el in md.steps(graph)]
    parts.append("<h3>RACI</h3>")
    parts.append(
        _table(
            ["Step"] + [e(roles.get(r, "")) for r in order],
            [
                [f"[{e(el.provenance)}] {e(el.label)}"]
                + [e(md.raci_cell(el, r)) or "·" for r in order]
                for el in md.steps(graph)
            ],
        )
    )
    parts.append('<p class="note">A? means the sources disagree about who is accountable.</p>')
    parts.append("<h3>Two views: as done and as documented</h3>")
    parts.append(_list(md.two_views_lines(data)))
    parts.append(f"<h3>{e(md.EXCEPTIONS_HEADING)}</h3>")
    parts.append(_list(md.exception_lines(data)))
    know_how = {k.element_id: k for k in data.know_how}
    parts.append("<h3>Work type and know-how</h3>")
    parts.append(
        _table(
            ["Step", "Work type", "Know-how (knowledge risk · dominant ASHEN)"],
            [
                [
                    f"[{e(el.provenance)}] {e(el.label)}",
                    e(md.work_type_text(el)),
                    e(f"{kh.knowledge_risk} · {md.ASHEN_WORDS.get(kh.dominant, kh.dominant)}")
                    if (kh := know_how.get(el.id))
                    else "—",
                ]
                for el in md.steps(graph)
            ],
        )
    )
    parts.append("<h3>Official vs lived</h3>")
    parts.append(_list(md.official_lived_lines(graph)))
    parts.append("<h3>Glossary of SME terms</h3>")
    terms = [
        f"<li><b>{e(t.term)}</b>: {e(t.plain_meaning or 'meaning not stated')}"
        + (f" (step: {e(', '.join(t.steps))})" if t.steps else "")
        + "</li>"
        for t in data.glossary
    ]
    parts.append(f"<ul>{''.join(terms)}</ul>" if terms else "<p>No SME terms recorded.</p>")
    parts.append("</section>")
    return "\n".join(parts)


def _list(lines: list[str]) -> str:
    """Markdown-style lines ("- …") as a list; a lone sentence as a paragraph."""
    items = [x.removeprefix("- ") for x in lines if x.startswith("- ")]
    if not items:
        return "".join(f"<p>{e(x)}</p>" for x in lines)
    return "<ul>" + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>"


VIEW_TITLES = {
    "done": "Map as done: the work as actually performed",
    "documented": "Map as documented: the documents' version",
}


VIEW_EMPTY = {
    "done": "No interview or system record describes these steps yet, so this view has none.",
    "documented": "No document describes these steps yet, so this view has none.",
}


def _maps(data: ExportInput, graph: Graph) -> list[str]:
    """Both views, each drawn from its own backend layout (§3.12.11); the one map before v1.10.
    As in the app, the view that draws more steps comes first, As done on a tie (2026-10-28)."""
    if not data.view_graphs:  # laid out only here: with both views it would go unused
        return [_map(graph, compute_layout(graph))]
    drawn = {view: md.on_the_map(data.view_graphs[view]) for view in VIEW_TITLES}
    counts = {view: len(md.steps(g)) for view, g in drawn.items()}
    order = ["documented", "done"] if counts["documented"] > counts["done"] else list(VIEW_TITLES)
    parts = []
    for view in order:
        parts.append(f"<h3>{e(VIEW_TITLES[view])}</h3>")
        if not counts[view]:
            parts.append(f'<p class="meta">{e(VIEW_EMPTY[view])}</p>')
        parts.append(_map(drawn[view], compute_layout(drawn[view])))
    return parts


def _recommendation(data: ExportInput, graph: Graph) -> str:
    parts = [
        '<section aria-labelledby="recommendation">',
        f'<h2 id="recommendation">{e(md.RECOMMENDATION[3:])}</h2>',
        "<h3>Preserve / Improve</h3>",
        _list(md.preserve_improve_lines(data)),
        "<h3>Reality gaps by gap class</h3>",
        _list(md.reality_gap_lines(data)),
        "<h3>AI flags</h3>",
    ]
    flagged = [el for el in md.steps(graph) if el.ai_flag is not None]
    for el in flagged:
        flag = el.ai_flag
        assert flag is not None
        fields = [
            ("Component", md.COMPONENTS.get(flag.component, flag.component)),
            ("Input", flag.input),
            ("Output", flag.output),
            ("Handoff", flag.handoff),
            ("Basis", md.BASES.get(flag.basis, flag.basis)),
        ]
        body = "".join(f"<dt>{k}</dt><dd>{e(v)}</dd>" for k, v in fields)
        parts.append(
            f'<div class="card"><p><a href="#step-{e(el.id)}">'
            f"[{e(el.provenance)}] {e(el.label)}</a></p><dl>{body}</dl></div>"
        )
    if not flagged:
        parts.append("<p>No AI flags.</p>")
    parts.append("<h3>Knowledge-risk register</h3>")
    risks = [
        f"<li>[{e(el.provenance)}] {e(el.label)}: {e(el.k_risk)}</li>"
        for el in md.steps(graph)
        if el.k_risk
    ]
    parts.append(f"<ul>{''.join(risks)}</ul>" if risks else "<p>No knowledge risks recorded.</p>")
    parts.append("<h3>External-practice register</h3>")
    external = [
        f"<li>[R] {e(el.label)}: {e(el.r_reference or 'no reference recorded')}</li>"
        for el in md.steps(graph)
        if el.provenance == Provenance.RECOMMENDED.value
    ]
    parts.append(
        f"<ul>{''.join(external)}</ul>" if external else "<p>No steps from external practice.</p>"
    )
    parts.append("<h3>Open validation questions</h3>")
    questions = []
    for q in data.open_questions:
        about = [x for x in (q.element_label and f"step: {q.element_label}", q.phase_name) if x]
        where = f" ({' · '.join(about)})" if about else ""
        questions.append(
            f"<li>{e(q.question)}{e(where)} · {e(md.REASONS.get(q.reason, q.reason))}</li>"
        )
    parts.append(f"<ol>{''.join(questions)}</ol>" if questions else "<p>No open questions.</p>")
    parts.append("<h3>Cause library entries (pending validation)</h3>")
    causes = [f"<li>{e(md.cause_line(c).removeprefix('- '))}</li>" for c in data.causes]
    parts.append(
        f"<ul>{''.join(causes)}</ul>" if causes else "<p>No cause library entries yet.</p>"
    )
    parts.append("<h3>Gap analyses</h3>")
    reports = [f"<li>{e(md.gap_report_line(r).removeprefix('- '))}</li>" for r in data.gap_reports]
    parts.append(f"<ul>{''.join(reports)}</ul>" if reports else "<p>No finalised gap analyses.</p>")
    parts += ["<h3>Disposition and value</h3>", f"<p>{md.NOT_USED}</p>"]
    parts += ["<h3>System records</h3>", f"<p>{md.NOT_USED}</p>"]
    parts.append("</section>")
    return "\n".join(parts)


def render_map_html(data: ExportInput, tokens: dict[str, object], fonts: dict[str, bytes]) -> str:
    graph = md.on_the_map(data.graph)
    published = md.display_date(data.published_at)
    title = f"{graph.process.name} — Master Process Map {graph.version.label}"
    meta = (
        f"Version {graph.version.label} · "
        + (f"published {published}" if published else "not published yet")
        + (
            f" · validated by {data.validated_by or 'not recorded'}"
            if published
            else " · not validated yet"
        )
    )
    signal_line = md.signal_text(data)
    steps = [el for el in graph.elements if el.kind in STEP_KINDS]
    reviewed = sum(1 for el in steps if el.review_status != "draft")
    stamp = (
        f'<p class="draft-stamp" role="note">'
        f"{e(DRAFT_STAMP.format(reviewed=reviewed, total=len(steps)))}</p>"
        if not data.published_at
        else ""
    )
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            f'<meta http-equiv="Content-Security-Policy" content="{CSP}">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{e(title)}</title>",
            "<style>",
            fonts_css(fonts),
            tokens_css(tokens),
            STYLE.strip() + ("\n" + DRAFT_STYLE if stamp else ""),
            "</style>",
            "</head>",
            "<body>",
            "<main>",
            f"<header><h1>{e(graph.process.name)} — Master Process Map</h1>"
            f'<p class="meta">{e(meta)}</p>'
            + (f'<p class="meta signal">{e(signal_line)}</p>' if signal_line else "")
            + stamp
            + "</header>",
            f'<div class="card">{_card(data.quality_card)}</div>',
            _facts(data, graph),
            _interpretation(data, graph),
            _recommendation(data, graph),
            "<footer>Role names only. No images, verbatim quotes or names. "
            "Made with Process Map Studio.</footer>",
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
    )
