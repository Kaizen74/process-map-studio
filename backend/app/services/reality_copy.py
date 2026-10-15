"""The Reality views' words (PRD §3.18.4, §5.12.5; P13b): a fixed, versioned catalogue of titles,
headlines, callouts and availability sentences, chosen and filled only with computed values. No
AI call ever writes or polishes this text (constraint 26). Changing any template is a change of
`COPY_VERSION`: it re-runs the affected baselines and is logged in DECISIONS.md first (G15).

Number formats (§5.12.5): whole percentages ("70%"), minutes ("+18 min"), hours ("426 h a
month"), multipliers ("3.0" and the multiplication sign), prevalence ("5 of 6 interviews").
Role and step names only.
"""

from __future__ import annotations

from collections.abc import Mapping

COPY_VERSION = "3"  # 2: Redline, time, belief and typical case (P13c); 3: outside lane (E1)
OUTSIDE_LANE = "Outside the organisation"  # the Typical case's lane (E1)
OUTSIDE_START = "Starts outside"
OUTSIDE_END = "Ends outside"
TIMES = "\u00d7"  # the multiplication sign
MAX_HEADLINE_WORDS = 20

TITLES = {
    "rv1": "How different is real {process} from the manual?",
    "rv2": "Where does reality break away from the manual, and what does it cost?",
    "rv3": "Which gaps should we fix, and which should we keep?",
    "rv4": "What exactly changed versus the manual?",
    "rv5": "Where does the extra time come from?",
    "rv6": "How far is what we believe from what happens?",
    "rv7": "What does the hidden work feel like for one customer?",
}

# Headline templates by slot, in the order they are considered (the first whose values exist).
TEMPLATES: Mapping[str, str] = {
    "rv1.share": "Only {documented_share} of cases follow the manual.",
    "rv1.share_none": "No case in the log follows the manual as written.",
    "rv1.steps": "{done_only} only in practice and {documented_only} only in the manual.",
    "rv1.no_manual": "No manual to compare with yet: {steps} come from interviews only.",
    "rv1.same": "No difference from the manual found in these sources.",
    "rv1.no_record": "{control_share} of cases leave no record of {control_name}.",
    "rv1.bypass": "{control_share} of cases go round {control_name}.",
    "rv1.multiplier": "Cases take {multiplier} the designed time.",
    "rv2.hotspot": "{phase} is the hotspot: {added_min} extra minutes a case and {hours} hours a "
    "month.",
    "rv2.hotspot_minutes": "{phase} is the hotspot: {added_min} extra minutes a case.",
    "rv2.no_time": "{gaps} found; none has a measured or stated time yet.",
    "rv2.same": "No difference from the manual found to place on the process.",
    "rv3.both": "{correct} {correct_verb} {intent_kind} at risk; {codify} {codify_verb} the "
    "promise and could become the official way.",
    "rv3.correct": "{correct} {correct_verb} {intent_kind} at risk; none is yet clearly a practice "
    "to keep.",
    "rv3.codify": "{codify} {codify_verb} the promise and could become the official way.",
    "rv3.rewrite": "{rewrite} {rewrite_verb} in the manual itself: the rule needs rewriting.",
    "rv3.ask": "{ask} {ask_verb} the process owner's view before {ask_pronoun} can be sorted.",
    "rv3.no_intent": "{ask} {ask_wait} in Ask until intent is confirmed.",
    "rv3.same": "No gap to sort yet.",
    "rv4.changes": "{changes} from the manual, {controls} on a control.",
    "rv4.changes_plain": "{changes} from the manual.",
    "rv4.same": "Practice follows the manual as written in these sources.",
    "rv4.none": "No SOP or manual is in the sources, so there is nothing to mark up yet.",
    "rv5.added": "{phase} adds {added_min} minutes a case; {wait_min} of it is waiting, not work.",
    "rv5.added_work": "{phase} adds {added_min} minutes a case of extra work.",
    "rv5.none": "No added time can be worked out from the times your sources state.",
    "rv6.gap": "{step} is the largest gap: measured {measured} against a believed {believed}.",
    "rv6.none": "No step has both a believed and a measured time to compare.",
    "rv6.close": "Belief and measurement are within {factor} on {steps} compared.",
    "rv7.promise": "A typical case touches {tools} and finishes {late} after the promise.",
    "rv7.designed": "A typical case touches {tools} and finishes {late} after the designed time.",
    "rv7.records": "A typical case touches {tools} and leaves {missing} without a record.",
    "rv7.label": "A typical case: median timings of {cases}, not one real case.",
    "rv6.note": "A visibility gap, not a competence gap.",
    "rv6.method": "How belief is measured: the median of the times official accounts state for a "
    "step, never one person's answer, set against the system's median for the same step.",
    "callout.code": "{code} {title} ({delta}).",
    "callout.figures": "{figures}.",
    "callout.control": "Potential control exposure, for the control owner to confirm.",
    "callout.decide": "Decide first: {code} {title}.",
    "callout.reason": "{reason}",
    "rv3.note": "Verdicts are recommendations; the process owner decides.",
    "label.draft": "Draft: figures may change",
    "label.published": "Version {label}, validated by {owner} on {date}",
    "label.published_unnamed": "Version {label}, validated on {date}",
    "lens": "Largest loss: {column}",
    "columns.hidden": "{n} not shown, none with a control exposure",
}

AVAILABILITY: Mapping[str, str] = {
    "rv1.no_documents": "Without documents there is no manual to compare with: upload an SOP or "
    "manual.",
    "rv1.no_log": "Without system records the routes are step counts from interviews and "
    "documents, not shares of cases.",
    "rv2.no_documents": "No documents uploaded.",
    "rv2.no_intent": "Add intent statements to compare with what you promise.",
    "rv2.no_log": "No system records: minutes are stated times, and hours a month need a system "
    "log.",
    "rv2.no_belief": "No official account states a time for a step.",
    "rv3.no_intent": "Without intent every deviation sits in Ask. Add intent statements (a target, "
    "a promise or a control objective) to sort the gaps into fix or keep.",
    "rv4.no_documents": "The Redline marks changes on an SOP or manual: upload one to see it.",
    "rv5.no_times": 'Steps without a time show "No time stated"; the totals are incomplete.',
    "rv6.no_log": "Measured values come from system records: import a system log to compare "
    "them with what experts believe.",
    "rv6.no_belief": "No official account states a time for a step the system measures.",
    "rv7.no_log": "A typical case needs a system log with at least 5 cases on one route; it is "
    "never one real case.",
    "no_version": "Create a draft map first.",
}

BANDS = {
    "promise": "What we promise",
    "belief": "What experts believe",
    "documented": "What the manual says",
    "done": "What actually happens",
    "consequence": "What it costs",
}

QUADRANTS = {
    "as_designed": ("Working as designed", "Follows the manual and delivers the promise."),
    "codify": ("Codify the practice", "Departs from the manual and delivers the promise."),
    "rewrite": ("Rewrite the rule", "Follows the manual and falls short of the promise."),
    "correct": ("Correct the practice", "Departs from the manual and falls short of the promise."),
    "ask": ("Ask", "Not enough evidence to say where the fix lies."),
}

IMPACT_WORDS = {
    "control_exposure": ("Control exposure", "triangle"),
    "time_impact": ("Time impact", "clock"),
    "capacity_drain": ("Capacity drain", "bars"),
    "workaround": ("Workaround", "dotted_square"),
}

LINES = (
    ("solid", "In the system of record, or as documented"),
    ("dashed", "A deviation the system records"),
    ("dotted", "Off-system work"),
    ("double", "An approved local variation"),
)

INTENT_KINDS = {
    "control_objective": "a control",
    "target": "a target",
    "promise": "the promise",
    "policy_rule": "a policy rule",
}


# --- formats ------------------------------------------------------------------------------------


def pct(share: float) -> str:
    """A share (0-1) as a whole percentage, rounded as the discrepancy engine rounds."""
    return f"{round(100 * share)}%"


def minutes(value: float, signed: bool = True) -> str:
    sign = "+" if signed and value >= 0 else ""
    return f"{sign}{value:.0f} min"


def hours(value: float) -> str:
    return f"{value:.0f} h a month"


def times(value: float) -> str:
    return f"{value:.1f}{TIMES}"


def count(n: int, noun: str, plural: str | None = None) -> str:
    return f"{n} {noun if n == 1 else (plural or noun + 's')}"


def of(n: int, total: int, noun: str) -> str:
    return f"{n} of {total} {noun if total == 1 else noun + 's'}"


def words(text: str) -> int:
    return len(text.split())


# --- filling ------------------------------------------------------------------------------------


def fill(slot: str, **values: object) -> str:
    """A template filled with computed values (KeyError when a value is missing: never guessed)."""
    return TEMPLATES[slot].format(**values)


def title(view: str, process: str) -> str:
    return TITLES[view].format(process=process or "the process")


def headline(*sentences: str) -> str:
    """Sentences in order of precedence, kept while the headline stays within 20 words."""
    out: list[str] = []
    for s in sentences:
        if not s:
            continue
        if out and words(" ".join([*out, s])) > MAX_HEADLINE_WORDS:
            break
        out.append(s)
    return " ".join(out)


def verb(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def data_label(draft: bool, label: str, owner: str, date: str) -> str:
    if draft:
        return fill("label.draft")
    if owner:
        return fill("label.published", label=label, owner=owner, date=date)
    return fill("label.published_unnamed", label=label, date=date)


def evidence_text(documents: int, interviews: int, cases: int | None) -> str:
    parts = [count(documents, "document"), count(interviews, "interview")]
    if cases is not None:
        parts.append(count(cases, "case"))
    return " · ".join(parts)


def evidence_sentence(documents: int, interviews: int, system_cases: int | None) -> str:
    def part(n: int | None, noun: str, plural: str) -> str:
        return f"no {noun}" if not n else count(n, noun, plural)

    return (
        f"Evidence: {part(documents, 'document', 'documents')}, "
        f"{part(interviews, 'interview', 'interviews')}, "
        f"{part(system_cases, 'system case', 'system cases')}."
    )


def every_template() -> list[str]:
    """Every fixed text (for the banned-words and names scans)."""
    return [
        *TITLES.values(),
        *TEMPLATES.values(),
        *AVAILABILITY.values(),
        *BANDS.values(),
        *(t for pair in QUADRANTS.values() for t in pair),
        *(w for w, _ in IMPACT_WORDS.values()),
        *(m for _, m in LINES),
        OUTSIDE_LANE,
        OUTSIDE_START,
        OUTSIDE_END,
    ]
