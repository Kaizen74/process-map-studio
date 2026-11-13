"""The country comparison pages (PRD §3.19; DECISIONS 98): a summary, "Who decides", "How the work
differs" and "Only in one country", in the Reality pack's style, for A3 or 16:9.

Pure and fixed: every line comes from the comparison the rules worked out and the reasons Eric
gave; nothing here is written by AI. Role names only: no quote, name, source text or file name.
Only differences Eric classed or kept are printed; open ones are counted, dismissed ones left out.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from app.domain.comparisons import ComparisonView, DifferenceView
from app.services.export_html import CSP, fonts_css, tokens_css
from app.services.export_reality import LAYOUTS, PAGE, STYLE

__all__ = ["LAYOUTS", "render"]

REASONS = {
    "required": "Required",
    "chosen": "Chosen",
    "inherited": "Inherited",
    "unknown": "Not known yet",
}
TOPICS = {
    "decision_right": "Who decides",
    "role_presence": "Which roles exist",
    "role_reason": "Why a role is there",
    "way_of_working": "How the work runs",
}
GRADES = {"confirmed": "Confirmed", "indicated": "Indicated", "hypothesis": "Hypothesis"}
ONLY = ("only_reference", "only_other")
PRINTED = ("classed", "kept")


def e(text: object) -> str:
    return escape(str(text), quote=True)


def _reason(d: DifferenceView) -> str:
    if d.status == "kept" or not d.reason_class:
        return "Kept; no reason given yet"
    word = REASONS.get(d.reason_class, d.reason_class)
    return f"{word}: {d.reason_note}" if d.reason_note else word


def _rows(found: Sequence[DifferenceView]) -> str:
    return "".join(
        f'<tr><td class="mono">{e(d.code or "")}</td><td>{e(d.title)}</td>'
        f"<td>{e(d.figure or '—')}</td><td>{e(_reason(d))}</td>"
        f"<td>{e(GRADES.get(d.grade.grade, d.grade.grade))}</td></tr>"
        for d in found
    )


def _table(found: Sequence[DifferenceView], empty: str) -> str:
    if not found:
        return f'<p class="pack-availability">{e(empty)}</p>'
    return (
        '<table class="reality-table"><thead><tr><th scope="col">Code</th>'
        '<th scope="col">Difference</th><th scope="col">Figure</th>'
        '<th scope="col">Reason</th><th scope="col">Grade</th></tr></thead>'
        f"<tbody>{_rows(found)}</tbody></table>"
    )


def _page(section: str, kicker: str, title: str, body: str, footer: str) -> str:
    return (
        f'<section class="page" data-section="{e(section)}">'
        f'<p class="pack-section">{e(kicker)}</p>'
        f'<h2 class="reality-view__title">{e(title)}</h2>{body}'
        f'<p class="pack-small">{e(footer)}</p></section>'
    )


def _count_table(caption: str, head: str, counts: Sequence[tuple[str, int]]) -> str:
    rows = "".join(f'<tr><td>{e(k)}</td><td class="mono">{v}</td></tr>' for k, v in counts)
    return (
        f'<table class="reality-table"><caption>{e(caption)}</caption><thead><tr>'
        f'<th scope="col">{e(head)}</th><th scope="col">Differences</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )


def render(
    view: ComparisonView,
    layout: str,
    *,
    process: str,
    tokens: dict[str, object],
    fonts: dict[str, bytes],
    reality_css: str,
) -> str:
    """The comparison pages as one HTML file. `layout` is `a3` or `slide`."""
    assert layout in LAYOUTS
    ref, other = view.reference.country, view.other.country
    printed = [d for d in view.differences if d.status in PRINTED]
    decides = [d for d in printed if d.topic == "decision_right" and d.kind not in ONLY]
    works = [d for d in printed if d.topic != "decision_right" and d.kind not in ONLY]
    only = [d for d in printed if d.kind in ONLY]
    by_reason = [
        (REASONS[k], sum(1 for d in printed if d.status == "classed" and d.reason_class == k))
        for k in REASONS
    ]
    by_reason.append(("Kept without a reason", sum(1 for d in printed if d.status == "kept")))
    by_topic = [(TOPICS[k], sum(1 for d in printed if d.topic == k)) for k in TOPICS]
    footer = (
        f"{other} {view.other.version_label} compared with {ref} "
        f"{view.reference.version_label} (the reference). Worked out by fixed rules (rules "
        f"version {view.rules_version}); every reason is the process owner's. Role names "
        "only. Nothing here is written by AI."
    )
    summary = (
        f'<p class="pack-strong">{len(printed)} differences classed or kept; '
        f"{view.counts.open} not classed yet (not printed); {view.counts.dismissed} dismissed as "
        "not real differences (not printed).</p>"
        + _count_table("By reason", "Reason", by_reason)
        + _count_table("By topic", "Topic", by_topic)
    )
    title = f"{process}: {other} compared with {ref}"
    pages = "".join(
        [
            _page("summary", "Summary", title, summary, footer),
            _page(
                "decides",
                "Who decides",
                f"Who decides: {other} and {ref}",
                _table(decides, "No difference in who decides is classed or kept."),
                footer,
            ),
            _page(
                "work",
                "How the work differs",
                f"How the work differs: {other} and {ref}",
                _table(works, "No difference in how the work runs is classed or kept."),
                footer,
            ),
            _page(
                "only",
                "Only in one country",
                f"Only in one country: {other} and {ref}",
                _table(only, "Every step is in both countries."),
                footer,
            ),
        ]
    )
    css = "\n".join(
        [fonts_css(fonts), tokens_css(tokens, reality=True), reality_css, STYLE, PAGE[layout]]
    )
    return (
        "<!doctype html>\n"
        f'<html lang="en"><head><meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{e(title)}</title><style>{css}</style></head>"
        f'<body class="pack pack--{layout}"><main>{pages}</main></body></html>\n'
    )
