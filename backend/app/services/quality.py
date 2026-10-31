"""The publish quality card (PRD §7.2): checks over the map, its lint report and its rendered
exports. Pure: `build_quality_card(QualityInput) -> QualityCard`. Q1-Q9 are hard (all must pass to
publish); Q10 and Q11 are warnings, and Q12 (a warning) is on the card only when the engagement
uses system records. Rejected steps are not on the map and count for nothing. Details say
what to fix in plain words and never repeat a hidden name.
"""

from __future__ import annotations

import re

from app.domain.enums import Provenance, ReviewStatus
from app.domain.graph import GraphElement
from app.domain.quality import CheckStatus, QualityCard, QualityCheck, QualityInput
from app.services import exports as md
from app.services import sensemaking, signal
from app.services.grounding import scan_redaction_terms
from app.services.lint import MAX_LANES, MAX_STEPS

SIGNAL_WARNING = signal.QUALITY_WARNING

EVIDENCED = {Provenance.OBSERVED.value, Provenance.INFERRED.value}
PROVENANCES = {p.value for p in Provenance}
STEP_KINDS = md.STEP_KINDS
DECIDING_ONE = "decision, approval or judgment step"
DECIDING_MANY = "decisions, approvals or judgment steps"

# Recommendation-type content: it may appear only in section 3 of an export (Q7).
RECOMMENDATION_MARKERS = [
    "- Component: ",
    "### Knowledge-risk register",
    "### External-practice register",
    "### Open validation questions",
    "<dt>Component</dt>",
    "<h3>Knowledge-risk register</h3>",
    "<h3>External-practice register</h3>",
    "<h3>Open validation questions</h3>",
    "### Preserve / Improve",
    "### Reality gaps by gap class",
    "### Disposition and value",
    "<h3>Preserve / Improve</h3>",
    "<h3>Reality gaps by gap class</h3>",
    "<h3>Disposition and value</h3>",
]
HTML_SECTIONS = [
    'aria-labelledby="facts"',
    'aria-labelledby="interpretation"',
    'aria-labelledby="recommendation"',
]
IMAGE_PATTERN = re.compile(
    r"<img\b|<svg\b|<picture\b|data:image/|!\[[^\]]*\]\(|\.(png|jpe?g|webp|gif|bmp|heic)\b",
    re.IGNORECASE,
)


def _names(elements: list[GraphElement], limit: int = 3) -> str:
    shown = ", ".join(f"“{e.label}”" for e in elements[:limit])
    more = len(elements) - limit
    return shown + (f" and {more} more" if more > 0 else "")


def _check(cid: str, name: str, failed: bool, ok: str, bad: str, hard: bool = True) -> QualityCheck:
    status: CheckStatus = ("fail" if hard else "warning") if failed else "pass"
    return QualityCheck(id=cid, name=name, status=status, hard=hard, detail=bad if failed else ok)


def _lint_failures(inp: QualityInput, rules: set[str]) -> list[str]:
    return [f.message for f in inp.lint.failures if f.rule in rules]


def _sections_in_order(text: str, markers: list[str]) -> bool:
    places = [text.find(m) for m in markers]
    return all(text.count(m) == 1 for m in markers) and places == sorted(places) and places[0] >= 0


def _separated(text: str, markers: list[str], section_three: str) -> bool:
    """Exactly the three sections in order, and recommendation content only in the third."""
    if not _sections_in_order(text, markers):
        return False
    before = text.split(section_three)[0]
    return not any(m in before for m in RECOMMENDATION_MARKERS)


def build_quality_card(inp: QualityInput) -> QualityCard:
    graph = md.on_the_map(inp.graph)
    steps = [e for e in graph.elements if e.kind in STEP_KINDS]
    checks: list[QualityCheck] = []

    # Q1 provenance: every step tagged, every recommendation with its reference.
    untagged = [e for e in steps if e.provenance not in PROVENANCES]
    unreferenced = [
        e
        for e in steps
        if e.provenance == Provenance.RECOMMENDED.value and not e.r_reference.strip()
    ]
    q1 = []
    if untagged:
        q1.append(f"{md.plural(len(untagged), 'step')} without provenance: {_names(untagged)}.")
    if unreferenced:
        q1.append(
            f"{md.plural(len(unreferenced), 'recommended step')} without a reference: "
            f"{_names(unreferenced)}."
        )
    checks.append(
        _check(
            "Q1",
            "Provenance green",
            bool(q1),
            f"All {md.plural(len(steps), 'step')} are tagged O, I or R.",
            " ".join(q1),
        )
    )

    # Q2 evidence: every O/I step has a verified passage (an O step may rest on its system
    # trace, R8); no unverified claim behind a step.
    traced = set(inp.traced)
    unevidenced = [
        e
        for e in steps
        if e.provenance in EVIDENCED
        and not any(ev.verified and ev.segment_id for ev in e.evidence)
        and not (e.provenance == Provenance.OBSERVED.value and e.id in traced)
    ]
    q2 = []
    if unevidenced:
        q2.append(
            f"{md.plural(len(unevidenced), 'step')} without a verified passage: "
            f"{_names(unevidenced)}."
        )
    if inp.unverified_claims:
        q2.append(f"{md.plural(inp.unverified_claims, 'unverified claim')} behind the map's steps.")
    checks.append(
        _check(
            "Q2",
            "Evidence verified",
            bool(q2),
            "Every observed or inferred step has a verified passage.",
            " ".join(q2),
        )
    )

    # Q3-Q5 from the lint rules.
    for cid, name, rules, ok in (
        (
            "Q3",
            "Diamonds closed",
            {"L4", "L5"},
            "Every decision and approval has all its exits, each labelled.",
        ),
        (
            "Q4",
            "Lanes and ownership",
            {"L6", "L7", "L8", "L9", "L11"},
            "Every step sits in the right lane, has one Accountable role and is connected.",
        ),
        (
            "Q5",
            "Flags executable",
            {"L10"},
            "Every AI flag is complete, and none is on a judgment step.",
        ),
    ):
        failures = _lint_failures(inp, rules)
        bad = " ".join(failures[:3]) + (
            f" And {len(failures) - 3} more." if len(failures) > 3 else ""
        )
        checks.append(_check(cid, name, bool(failures), ok, bad))

    # Q6 fully reviewed.
    unreviewed = [e for e in steps if e.review_status == ReviewStatus.DRAFT.value]
    unchecked = [e for e in unreviewed if e.needs_check]
    q6 = []
    if unreviewed:
        q6.append(f"{md.plural(len(unreviewed), 'step')} not reviewed yet.")
    if unchecked:
        q6.append(
            f"{md.plural(len(unchecked), 'step')} the verifier only partly supported still "
            "to confirm or edit."
        )
    if inp.pending_merges:
        q6.append(f"{md.plural(inp.pending_merges, 'merge decision')} waiting for you.")
    if inp.open_image_suggestions:
        q6.append(f"{md.plural(inp.open_image_suggestions, 'suggested image')} to keep or discard.")
    checks.append(
        _check(
            "Q6",
            "Fully reviewed",
            bool(q6),
            "Every step, merge and suggested image has been reviewed.",
            " ".join(q6),
        )
    )

    # Q7 facts, interpretation and recommendation separated in the exports.
    markers = [md.FACTS, md.INTERPRETATION, md.RECOMMENDATION]
    md_ok = _separated(inp.exports.get("md", ""), markers, md.RECOMMENDATION)
    html_ok = _separated(inp.exports.get("html", ""), HTML_SECTIONS, HTML_SECTIONS[2])
    wrong = [name for name, ok in (("Master Process Map", md_ok), ("HTML map", html_ok)) if not ok]
    checks.append(
        _check(
            "Q7",
            "Facts, interpretation and recommendation separated",
            bool(wrong),
            "The exports keep facts, interpretation and recommendation in their own sections.",
            f"The {' and the '.join(wrong)} mix the three sections.",
        )
    )

    # Q8 anonymised: no hidden name in any rendered export (the names themselves are never shown).
    leaks = [
        fmt for fmt, text in inp.exports.items() if scan_redaction_terms(text, inp.hidden_terms)
    ]
    checks.append(
        _check(
            "Q8",
            "Anonymised",
            bool(leaks),
            "No name from the list of names to hide appears in any export.",
            f"A name from the list of names to hide appears in the {', '.join(leaks)} "
            "export. Replace it with the role in the step's text.",
        )
    )

    # Q9 images contained.
    pictured = [fmt for fmt, text in inp.exports.items() if IMAGE_PATTERN.search(text)]
    checks.append(
        _check(
            "Q9",
            "Images contained",
            bool(pictured),
            "No image or image reference in any export.",
            f"An image or image reference is in the {', '.join(pictured)} export.",
        )
    )

    # Q10 one map, one hour (warning only).
    lanes = {e.lane_role_id for e in steps if e.lane_role_id}
    large = len(steps) > MAX_STEPS or len(lanes) > MAX_LANES
    size = f"{md.plural(len(steps), 'step')} and {md.plural(len(lanes), 'lane')}"
    checks.append(
        _check(
            "Q10",
            "60-minute validatable",
            large,
            f"{size}: fits a one-hour session.",
            f"{size}: consider splitting by phase.",
            hard=False,
        )
    )

    # Q11 work types confirmed (warning, PRD v1.10 §7.2).
    awaiting = sensemaking.awaiting_work_type(steps)
    checks.append(
        _check(
            "Q11",
            "Work types confirmed",
            bool(awaiting),
            "Every decision, approval and judgment step has a confirmed work type.",
            f"{md.plural(len(awaiting), DECIDING_ONE, DECIDING_MANY)} without a confirmed work "
            f"type: {_names(awaiting)}.",
            hard=False,
        )
    )

    # Q12 system alignment complete (warning, PRD v1.11; only when system records are used).
    if inp.unaligned_activities is not None:
        checks.append(
            _check(
                "Q12",
                "System alignment complete",
                inp.unaligned_activities > 0,
                "Every imported system activity is aligned to a step or marked hidden work.",
                f"{md.plural(inp.unaligned_activities, 'system activity', 'system activities')} "
                "not yet aligned to a step or marked hidden work.",
                hard=False,
            )
        )

    warnings = [w.message for w in inp.lint.warnings]
    strength = signal.signal_strength(inp.source_kinds)
    if strength is not None and (warning := signal.quality_warning(strength)) is not None:
        warnings.append(warning)  # a warning, never a blocker (P12)
    all_green = all(c.status == "pass" for c in checks if c.hard)
    return QualityCard(checks=checks, warnings=warnings, all_green=all_green)


def hard_failures(card: QualityCard) -> int:
    return sum(1 for c in card.checks if c.hard and c.status == "fail")
