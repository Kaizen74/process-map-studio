"""The Reality pack (PRD §3.18.6, §7.4; criterion 117; P13d): one self-contained HTML file built
from a version's frozen Reality snapshot, for printing on A3 landscape or 16:9 pages. Pure: every
word, figure and position comes from the snapshot (G17, constraint 26); this only draws it, with
the same class names as the Reality screen and the app's own Reality stylesheet, so a code looks
the same on paper as on screen (RQ4).

Sections follow constraint 9: Facts (Glance, Reality stack, Redline, Where the time goes, Belief
vs evidence, Typical case), Interpretation (impact classes by column, the hotspot, potential
control exposures), Recommendation (Fix or keep and Decide first) and an Appendix. Verdicts
appear only in Recommendation and the Appendix.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape
from pathlib import Path

from app.domain.reality import (
    CaseView,
    CodeView,
    Figure,
    FixView,
    GlanceView,
    RealitySnapshot,
    Shape,
    ShapeGeometry,
    StackView,
    Tile,
    ViewBase,
)
from app.services import reality_copy as copy
from app.services.export_html import CSP, fonts_css, tokens_css

LAYOUTS = ("a3", "slide")
CALLOUTS = {"a3": 3, "slide": 2}
FACTS = ("rv1", "rv2", "rv4", "rv5", "rv6", "rv7")
VERDICT_WORDS = {"codify": "Codify", "correct": "Correct", "rewrite": "Rewrite", "ask": "Ask",
                 "as_designed": "As designed"}  # fmt: skip
STYLE = Path(__file__).with_name("export_reality.css").read_text(encoding="utf-8")
PAGE = {
    "a3": "@page { size: 420mm 297mm; margin: 10mm; }",
    "slide": "@page { size: 1920px 1080px; margin: 0; }",
}
GLYPHS = {
    "triangle": '<path d="M7 1.5 13 12.5H1Z"/>',
    "clock": '<circle cx="7" cy="7" r="5.5"/><path d="M7 3.8V7l2.4 1.6"/>',
    "bars": '<path d="M2 4h10M2 7h10M2 10h10"/>',
    "dotted_square": '<rect x="2" y="2" width="10" height="10" stroke-dasharray="1.6 1.6"/>',
}
LINE = 16
FIRST_LINE = 12
PAD = 4
# The room a view's drawing has on a page, in px (the page less its title, headline, callouts and
# legend, with a margin for a note and two-line callouts), and the smallest scale that keeps the
# drawings' 12.5 px text at 11 px or more. A drawing that would print smaller is printed as its
# table instead (RQ7; the print check in the browser measures every page).
ROOM = {"a3": (1448.0, 750.0), "slide": (1792.0, 760.0)}
MIN_SCALE = 11 / 12.5
AS_TABLE = ("This picture is too large to print legibly on one page, so its figures are printed "
            "as a table. The Reality screen shows the picture.")  # fmt: skip


def e(text: object) -> str:
    return escape(str(text), quote=True)


def n(value: float) -> str:
    """A coordinate as the screen draws it (no needless decimals)."""
    return f"{value:g}"


# --- small parts --------------------------------------------------------------------------------


def _figure(f: Figure, cls: str = "") -> str:
    """A figure as printed: its text, tagged with its ID (RQ9: one value everywhere)."""
    extra = f' class="{cls}"' if cls else ""
    return f'<span data-figure="{e(f.id)}"{extra}>{e(f.text)}</span>'


def _glyph(glyph: str, impact: str) -> str:
    return (f'<svg class="impact-glyph impact-glyph--{e(impact)}" viewBox="0 0 14 14" width="14" '
            f'height="14" aria-hidden="true">{GLYPHS.get(glyph, "")}</svg>')  # fmt: skip


def _impact_word(c: CodeView) -> str:
    return (f'<span class="impact-word impact-word--{e(c.impact_class)}">'
            f"{_glyph(c.glyph, c.impact_class)}{e(c.impact_word)}</span>")  # fmt: skip


def _badge(c: CodeView) -> str:
    return f'<span class="x-tag x-tag--{e(c.impact_class)}">{e(c.code)}</span>'


def _tiles(tiles: Sequence[Tile]) -> str:
    if not tiles:
        return ""
    items = "".join(
        f'<li class="metric-tile">{_figure(t.figure, "metric-tile__number")}'
        f'<span class="metric-tile__caption">{e(t.caption)}</span>'
        f'<span class="metric-tile__label">{e(t.figure.label)}</span></li>'
        for t in tiles
    )
    return f'<ul class="metric-tiles">{items}</ul>'


def _callouts(view: ViewBase, layout: str, snapshot: RealitySnapshot) -> str:
    shown = view.callouts[: CALLOUTS[layout]]
    if not shown:
        return ""
    # A callout's impact colour comes with the legend's symbol and word (constraint 17).
    impacts = {i.impact_class: i for i in snapshot.legend.impacts}

    def tag(impact: str | None) -> str:
        if impact is None or impact not in impacts:
            return ""
        i = impacts[impact]
        return (f'<p class="callout__impact"><span class="impact-word impact-word--{e(impact)}">'
                f"{_glyph(i.glyph, impact)}{e(i.word)}</span></p>")  # fmt: skip

    items = "".join(
        f'<li class="callout{f" callout--{e(c.impact_class)}" if c.impact_class else ""}">'
        + tag(c.impact_class) + "".join(f"<p>{e(line)}</p>" for line in c.lines) + "</li>"
        for c in shown
    )  # fmt: skip
    return f'<ul class="callouts">{items}</ul>'


def _legend(snapshot: RealitySnapshot, scale_note: str, evidence_key: bool = False) -> str:
    impacts = "".join(
        f'<li><span class="impact-word impact-word--{e(i.impact_class)}">'
        f"{_glyph(i.glyph, i.impact_class)}{e(i.word)}</span></li>"
        for i in snapshot.legend.impacts
    )
    lines = "".join(
        f'<li><svg width="28" height="8" aria-hidden="true"><line x1="0" y1="4" x2="28" y2="4" '
        f'class="legend-line legend-line--{e(ln.style)}"/></svg>{e(ln.meaning)}</li>'
        for ln in snapshot.legend.lines
    )
    note = f'<p class="reality-legend__note">{e(scale_note)}</p>' if scale_note else ""
    if evidence_key and snapshot.legend.evidence_key:  # on pages that show the D I S boxes
        note += f'<p class="reality-legend__note">{e(snapshot.legend.evidence_key)}</p>'
    return (f'<footer class="reality-legend"><ul class="reality-legend__row">{impacts}</ul>'
            f'<ul class="reality-legend__row">{lines}</ul>{note}'
            f'<p class="reality-legend__note pack-data-label">{e(snapshot.data_label)} · '
            f"{e(snapshot.evidence.text)}</p></footer>")  # fmt: skip


def _svg(width: float, height: float, label: str, body: str) -> str:
    return (f'<svg class="reality-canvas" viewBox="0 0 {n(width)} {n(height)}" '
            f'preserveAspectRatio="xMinYMin meet" role="img" aria-label="{e(label)}">'
            f"{body}</svg>")  # fmt: skip


def legible(width: float, height: float, layout: str) -> bool:
    """Whether a drawing of this size prints with its text at 11 px or more on the layout's page."""
    room_w, room_h = ROOM[layout]
    return min(room_w / width, room_h / height) >= MIN_SCALE


def _table(view: ViewBase) -> str:
    head = "".join(f"<th>{e(c)}</th>" for c in view.table.columns)
    rows = "".join("<tr>" + "".join(f"<td>{e(cell)}</td>" for cell in row) + "</tr>"
                   for row in view.table.rows)  # fmt: skip
    return (
        f'<table class="reality-table"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'
    )


def _text_lines(x: float, y: float, lines: Sequence[str], cls: str = "",
                strong_first: bool = False, dy: int = LINE) -> str:  # fmt: skip
    spans = "".join(
        f'<tspan x="{n(x)}" dy="{0 if i == 0 else dy}"'
        f"{' class="reality-label--strong"' if strong_first and i == 0 else ''}>{e(t)}</tspan>"
        for i, t in enumerate(lines)
    )
    return f'<text class="{cls}" x="{n(x)}" y="{n(y)}">{spans}</text>'


# --- the drawings (as the Reality screen draws them) --------------------------------------------


def glance(view: GlanceView, codes: Sequence[CodeView]) -> str:
    g = view.geometry
    routes = {r.id: r for r in view.glance.routes}
    impact = {c.code: c.impact_class for c in codes}
    t = g.trunk
    parts = [f'<line class="glance-trunk" x1="{n(t.x1)}" x2="{n(t.x2)}" y1="{n(t.y)}" '
             f'y2="{n(t.y)}" stroke-width="{n(t.width)}"/>',
             f'<text class="reality-label" x="{n(t.x1)}" y="{n(t.y - t.width / 2 - 10)}">'
             "The manual</text>"]  # fmt: skip
    for ribbon in g.ribbons:
        route = routes.get(ribbon.route_id)
        if route is None:
            continue
        tone = "documented" if route.documented else (route.impact_class or "neutral")
        badges = "".join(f'<tspan class="reality-code reality-code--{e(impact.get(c, "neutral"))}">'
                         f" {e(c)}</tspan>" for c in route.codes)  # fmt: skip
        parts.append(
            f'<path class="glance-ribbon glance-ribbon--{e(tone)} line--{e(ribbon.style)}" '
            f'd="{e(ribbon.path)}" stroke-width="{n(ribbon.width)}"/>'
            f'<text class="reality-label" x="{n(ribbon.label_x)}" y="{n(ribbon.label_y + 4)}">'
            f'<tspan class="reality-label--strong">{e(route.share.text)}</tspan> '
            f"{e(route.name)}{badges}</text>"
        )
    return _svg(g.width, g.height, f"{view.title} {view.headline}", "".join(parts))


def stack(view: StackView) -> str:
    g = view.geometry
    parts = [f'<rect class="stack-band stack-band--{e(b.id)}" x="{n(b.x)}" y="{n(b.y)}" '
             f'width="{n(b.width)}" height="{n(b.height)}"/>' for b in g.bands]  # fmt: skip
    if g.lens is not None:
        lens = g.lens
        label = view.stack.lens.label if view.stack.lens else ""
        parts.append(f'<g class="stack-lens"><rect x="{n(lens.x)}" y="{n(lens.y)}" '
                     f'width="{n(lens.width)}" height="{n(lens.height)}"/>'
                     f'<text class="reality-label reality-label--strong" x="{n(lens.label_x)}" '
                     f'y="{n(lens.label_y)}">{e(label)}</text></g>')  # fmt: skip
    for lb in g.band_labels:
        parts.append(_text_lines(lb.x, lb.y, lb.lines, "reality-label", strong_first=True))
    for lb in g.column_labels:
        parts.append(f'<text class="reality-label reality-label--strong" x="{n(lb.x)}" '
                     f'y="{n(lb.y)}">{e(lb.lines[0] if lb.lines else "")}</text>')  # fmt: skip
    for m in g.marks:
        cls = f"stack-mark stack-mark--{m.kind}"
        if m.kind == "branch" and m.impact_class:
            cls += f" stack-mark--{m.impact_class}"
        parts.append(f'<g><rect class="{e(cls)} line--{e(m.style)}" x="{n(m.x)}" y="{n(m.y)}" '
                     f'width="{n(m.width)}" height="{n(m.height)}" rx="6"/>'
                     + _text_lines(m.x + 8, m.y + 15, m.lines,
                                   f"stack-text stack-text--{m.kind}") + "</g>")  # fmt: skip
    return _svg(g.width, g.height, f"{view.title} {view.headline}", "".join(parts))


def fix(view: FixView, codes: Sequence[CodeView]) -> str:
    g = view.geometry
    impact = {c.code: c.impact_class for c in codes}
    parts = [f'<rect class="fix-zone fix-zone--{e(z.id)}" x="{n(z.x)}" y="{n(z.y)}" '
             f'width="{n(z.width)}" height="{n(z.height)}"/>' for z in g.zones]  # fmt: skip
    parts += [_text_lines(lb.x, lb.y, lb.lines, "reality-label", strong_first=True)
              for lb in g.labels]  # fmt: skip
    for c in g.circles:
        parts.append(f'<g><circle class="fix-circle fix-circle--{e(impact.get(c.code, "neutral"))}"'
                     f' cx="{n(c.cx)}" cy="{n(c.cy)}" r="{n(c.r)}"/>'
                     f'<text class="fix-code" x="{n(c.cx)}" y="{n(c.cy + c.r + 16)}" '
                     f'text-anchor="middle">{e(c.code)}</text></g>')  # fmt: skip
    return _svg(g.width, g.height, f"{view.title} {view.headline}", "".join(parts))


def _shape(s: Shape) -> str:
    cls = f"rs rs--{s.role} line--{s.style}" + (f" rs-impact--{s.impact_class}"
                                                 if s.impact_class else "")  # fmt: skip
    if s.kind == "rect":
        rx = s.height / 2 if s.role == "markup-wait" else 3
        style = ' style="fill:url(#rs-hatch)"' if s.role == "wait" else ""
        out = (f'<rect class="{e(cls)}" x="{n(s.x)}" y="{n(s.y)}" width="{n(s.width)}" '
               f'height="{n(s.height)}" rx="{n(rx)}"{style}/>')  # fmt: skip
        if s.role in ("markup-added", "legend-added"):
            out += (f'<text class="rs-glyph" x="{n(s.x + s.width / 2)}" '
                    f'y="{n(s.y + s.height - 4)}" text-anchor="middle">+</text>')  # fmt: skip
        return out
    if s.kind == "circle":
        return f'<circle class="{e(cls)}" cx="{n(s.x)}" cy="{n(s.y)}" r="{n(s.r)}"/>'
    if s.kind == "line":
        return (f'<line class="{e(cls)}" x1="{n(s.x)}" y1="{n(s.y)}" x2="{n(s.x2)}" '
                f'y2="{n(s.y2)}"/>')  # fmt: skip
    if s.kind == "path":
        return f'<path class="{e(cls)}" d="{e(s.path)}"/>'
    return _text_lines(s.x + PAD, s.y + FIRST_LINE, s.lines, cls)


def shapes(geometry: ShapeGeometry, label: str) -> str:
    hatch = (
        '<defs><pattern id="rs-hatch" width="6" height="6" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)"><rect class="rs-hatch-ground" width="6" height="6"/>'
        '<line class="rs-hatch-line" x1="0" y1="0" x2="0" y2="6"/></pattern></defs>'
    )
    body = hatch + "".join(f'<g data-role="{e(s.role)}">{_shape(s)}</g>' for s in geometry.shapes)
    return _svg(geometry.width, geometry.height, label, body)


# --- pages --------------------------------------------------------------------------------------


def _drawing(snapshot: RealitySnapshot, vid: str) -> tuple[str, str, float, float]:
    """A view's drawing, its scale note and its size."""
    v = snapshot.views
    if vid == "rv1":
        g1 = v.rv1.geometry
        return glance(v.rv1, snapshot.codes), g1.scale_note, g1.width, g1.height
    if vid == "rv2":
        g2 = v.rv2.geometry
        return stack(v.rv2), "", g2.width, g2.height
    if vid == "rv3":
        g3 = v.rv3.geometry
        return fix(v.rv3, snapshot.codes), g3.scale_note, g3.width, g3.height
    view = getattr(v, vid)
    geometry: ShapeGeometry = view.geometry
    drawn = shapes(geometry, f"{view.title} {view.headline}")
    return drawn, geometry.scale_note, geometry.width, geometry.height


def _view_page(snapshot: RealitySnapshot, vid: str, layout: str, section: str) -> str:
    view: ViewBase = getattr(snapshot.views, vid)
    a = view.availability
    missing = a.state == "missing"
    note = f'<p class="pack-availability">{e(a.message)}</p>' if a.message else ""
    drawing, scale, width, height = _drawing(snapshot, vid)
    if legible(width, height, layout):
        drawing = f'<div class="pack-drawing">{drawing}</div>'
    else:
        drawing = (f'<p class="pack-availability pack-as-table">{e(AS_TABLE)}</p><div '
                   f'class="pack-drawing pack-drawing--table">{_table(view)}</div>')  # fmt: skip
        scale = ""  # the note explains the picture's scale; the table has none
    extra = ""
    if vid == "rv1":
        extra = _tiles(snapshot.tiles)
    elif vid == "rv7" and isinstance(view, CaseView) and view.case.events:
        extra = f'<p class="pack-strong">{e(view.case.label)}</p>' + _tiles(view.case.tiles)
    body = "" if missing else extra + drawing
    return (f'<section class="page pack-view" data-view="{vid}" data-section="{section}">'
            f'<p class="pack-section">{e(section.capitalize())}</p>'
            f'<h2 class="reality-view__title">{e(view.title)}</h2>'
            f'<p class="reality-view__headline">{e(view.headline)}</p>{note}{body}'
            f"{_callouts(view, layout, snapshot)}{_legend(snapshot, scale)}</section>")  # fmt: skip


def _verdict(c: CodeView) -> str:
    v = c.verdict
    if v is None or not v.shown:
        return ""
    word = VERDICT_WORDS.get(v.shown, v.shown)
    return f'<span class="pack-verdict">{e(word)} ({e(v.status)})</span>'


def _chips(c: CodeView) -> str:
    chips = "".join(
        f'<span class="evidence-chip{" evidence-chip--on" if on else ""}" aria-hidden="true">'
        f"{letter}</span>"
        for letter, on in (("D", c.evidence.chips.documents), ("I", c.evidence.chips.interviews),
                           ("S", c.evidence.chips.system))
    )  # fmt: skip
    return (f'<span class="evidence-chips">{chips}</span> '
            f'<span class="pack-small">{e(c.evidence.sentence)}</span>')  # fmt: skip


def _decide_first(snapshot: RealitySnapshot) -> str:
    """Decide first as a table for print: code, gap, impact, verdict and reason, hours, evidence."""
    by_code = {c.code: c for c in snapshot.codes}
    rows = []
    for code in snapshot.views.rv3.fix.decide_first:
        c = by_code.get(code)
        if c is None:
            continue
        hours = _figure(c.hours) if c.hours is not None else "Needs system records"
        reason = c.verdict.reason if c.verdict else ""
        hedge = f'<br><span class="pack-small">{e(c.impact_note)}</span>' if c.impact_note else ""
        rows.append(f"<tr><td>{_badge(c)}</td><td>{e(c.title)}</td><td>{_impact_word(c)}</td>"
                    f"<td>{_verdict(c)}<br><span class=\"pack-small\">{e(reason)}</span>{hedge}"
                    f"</td><td>{hours}</td><td>{_chips(c)}</td></tr>")  # fmt: skip
    note = snapshot.views.rv3.fix.note
    return (f'<section class="page pack-decide" data-section="recommendation">'
            f'<p class="pack-section">Recommendation</p>'
            f'<h2 class="reality-view__title">Decide first</h2><table class="reality-table">'
            f"<thead><tr><th>Code</th><th>Gap</th><th>Impact</th><th>Verdict</th>"
            f"<th>Hours a month</th><th>Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody>"
            f'</table><p class="inline-note">{e(note)}</p>'
            f'{_legend(snapshot, "", evidence_key=True)}</section>')  # fmt: skip


def _interpretation(snapshot: RealitySnapshot) -> str:
    impacts = [(i.impact_class, i.word, i.glyph) for i in snapshot.legend.impacts]
    head = "".join(f'<th><span class="impact-word impact-word--{e(k)}">{_glyph(g, k)}{e(w)}'
                   "</span></th>" for k, w, g in impacts)  # fmt: skip
    names = {c.id: c.name for c in snapshot.columns}
    rows = []
    for col in snapshot.columns:
        here = [c for c in snapshot.codes if c.column_id == col.id]
        cells = "".join(
            "<td>" + " ".join(_badge(c) for c in here if c.impact_class == k) + "</td>"
            for k, _, _ in impacts
        )
        rows.append(f"<tr><th>{e(names[col.id])}</th>{cells}</tr>")
    elsewhere = [c for c in snapshot.codes if c.column_id is None]
    if elsewhere:
        cells = "".join("<td>" + " ".join(_badge(c) for c in elsewhere if c.impact_class == k)
                        + "</td>" for k, _, _ in impacts)  # fmt: skip
        rows.append(f"<tr><th>Not shown on the views</th>{cells}</tr>")
    lens = snapshot.views.rv2.stack.lens
    hotspot = f'<p class="pack-strong">{e(lens.label)}</p>' if lens else (
        '<p>No column stands out: no gap has a time or hours figure yet.</p>')  # fmt: skip
    controls = [c for c in snapshot.codes if c.control]
    hedge = copy.fill("callout.control")
    exposures = "".join(
        f"<li>{_badge(c)} "
        f"{e(copy.fill('callout.code', code=c.code, title=c.title, delta=c.delta.text))} "
        f"{e(hedge)}</li>"
        for c in controls
    ) or "<li>No potential control exposure is found.</li>"  # fmt: skip
    return (f'<section class="page" data-section="interpretation">'
            f'<p class="pack-section">Interpretation</p>'
            f'<h2 class="reality-view__title">Where the gaps concentrate</h2>'
            f'<h3>The hotspot</h3>{hotspot}'
            f'<h3>Impact classes by column</h3><table class="reality-table"><thead><tr>'
            f'<th>Column</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'
            f'<h3>Potential control exposures</h3><ul class="pack-list">{exposures}</ul>'
            f"{_legend(snapshot, '')}</section>")  # fmt: skip


def _appendix(snapshot: RealitySnapshot) -> str:
    rows = "".join(
        f"<tr><td>{_badge(c)}</td><td>{e(c.title)}</td><td>{e(' '.join(c.types))}</td>"
        f"<td>{_figure(c.delta)} ({e(c.delta.label)})</td><td>{_impact_word(c)}</td>"
        f"<td>{_verdict(c)}</td><td>{_chips(c)}</td></tr>"
        for c in sorted(snapshot.codes, key=lambda c: (len(c.code), c.code))
    ) or '<tr><td colspan="7">No discrepancy is found.</td></tr>'  # fmt: skip
    results = {"met": "Met", "not_met": "Not met", "unknown": "Not known yet"}
    intents = "".join(
        f"<tr><td>{e(i.kind.replace('_', ' ').capitalize())}</td><td>{e(i.text)}</td>"
        f"<td>{e(i.target)}</td><td>{e(results.get(i.result, i.result))}</td></tr>"
        for i in snapshot.intents
    ) or '<tr><td colspan="4">No confirmed intent statement yet.</td></tr>'  # fmt: skip
    versions = (f"Rules version {e(snapshot.rules_version)} · copy version "
                f"{e(snapshot.copy_version)} · layout version {e(snapshot.layout_version)} · "
                f"app version {e(snapshot.app_version)}")  # fmt: skip
    return (f'<section class="page" data-section="appendix"><p class="pack-section">Appendix</p>'
            f'<h2 class="reality-view__title">Discrepancies</h2><table class="reality-table">'
            f"<thead><tr><th>Code</th><th>Location</th><th>Types</th><th>Delta</th><th>Impact</th>"
            f"<th>Verdict</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody></table>"
            f'<h2 class="reality-view__title">Intent statements</h2><table class="reality-table">'
            f"<thead><tr><th>Kind</th><th>Statement</th><th>Target</th><th>Result</th></tr>"
            f"</thead><tbody>{intents}</tbody></table>"
            f'<p class="pack-small">{versions}</p>'
            f'{_legend(snapshot, "", evidence_key=True)}</section>')  # fmt: skip


def _cover(snapshot: RealitySnapshot, signal: str) -> str:
    return (f'<section class="page pack-cover" data-section="cover">'
            f'<h1>{e(snapshot.process_name)}: Reality views</h1>'
            f"<p>{e(snapshot.data_label)}</p>"
            + (f"<p>Signal strength: {e(signal)}</p>" if signal else "")
            + f"<p>{e(snapshot.evidence.text)}</p>"
            '<p class="pack-small">Every figure, headline and verdict is worked out by fixed rules '
            "from the sources and confirmed intent; nothing here is written by AI. Verdicts are "
            "recommendations; the process owner decides.</p></section>")  # fmt: skip


def render_pack(snapshot: RealitySnapshot, layout: str, *, signal: str,
                tokens: dict[str, object], fonts: dict[str, bytes],
                reality_css: str) -> str:  # fmt: skip
    """The pack as one HTML file. `layout` is `a3` or `slide`."""
    assert layout in LAYOUTS
    facts = "".join(_view_page(snapshot, vid, layout, "facts") for vid in FACTS)
    body = (f'<div data-section="facts">{facts}</div>'
            f'<div data-section="interpretation">{_interpretation(snapshot)}</div>'
            f'<div data-section="recommendation">'
            f'{_view_page(snapshot, "rv3", layout, "recommendation")}'
            f"{_decide_first(snapshot)}</div>"
            f"{_appendix(snapshot)}")  # fmt: skip
    css = "\n".join([fonts_css(fonts), tokens_css(tokens, reality=True), reality_css, STYLE,
                     PAGE[layout]])  # fmt: skip
    title = f"{snapshot.process_name}: Reality views"
    return ("<!doctype html>\n"
            f'<html lang="en"><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{e(title)}</title><style>{css}</style></head>"
            f'<body class="pack pack--{layout}">'
            f"{_cover(snapshot, signal)}{body}</body></html>\n")  # fmt: skip
