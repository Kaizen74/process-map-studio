"""The shared grade (DECISIONS 96): how sure a finding is, in the three words every app in the
set uses. Deterministic and versioned (constraint 27); Eric may choose another grade, and his
choice wins. The grade never replaces O / I / R or any grounding check.

- Confirmed: a system record and at least one other source support it.
- Indicated: at least one verified source supports it.
- Hypothesis: inferred, recommended from outside practice, or not verified.
"""

from __future__ import annotations

GRADE_RULES_VERSION = "1"

CONFIRMED = "confirmed"
INDICATED = "indicated"
HYPOTHESIS = "hypothesis"
GRADES = (CONFIRMED, INDICATED, HYPOTHESIS)
WORDS = {CONFIRMED: "Confirmed", INDICATED: "Indicated", HYPOTHESIS: "Hypothesis"}


def for_discrepancy(*, documents: int, interviews: int, system_cases: int | None) -> str:
    """From the counts shown with the discrepancy: sources that describe it and measured cases."""
    others = documents + interviews
    if system_cases and others:
        return CONFIRMED
    if system_cases or others:
        return INDICATED
    return HYPOTHESIS


def for_gap_finding(
    *, provenance: str, verification_status: str, needs_check: bool, system: bool, others: int
) -> str:
    """From the finding's own provenance and checks, whether a system record speaks to it and
    how many other sources do (sources that are silent are not counted)."""
    if provenance != "O" or verification_status != "verified" or needs_check:
        return HYPOTHESIS
    if system and others:
        return CONFIRMED
    return INDICATED if system or others else HYPOTHESIS
