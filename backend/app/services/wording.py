"""Wording checks for interview material and generated text (PRD §3.12.9, Appendix F).

Pure functions on text: the non-blaming vocabulary rule and the anti-anchoring rule (no claim
about what the SOP or documents say before movement M6).
"""

from __future__ import annotations

import re

# §3.12.9 rule 4: never these words; use adaptation, workaround, pressure, rule that no longer
# fits, unexplained instead.
BANNED_PHRASES = ("violation", "non-compliance", "noncompliance", "failure to follow", "error by")

# A statement about what the documents say ("the procedure mentions …", "the SOP says …"). A
# question that only offers "following a procedure" as a way to describe a story is not one.
_SOP_CLAIM = re.compile(
    r"\bSOP\b|\bthe procedure\b|\bprocedures? (?:say|says|mention|mentions|state|states)\b"
    r"|\bdocumented\b|\bofficially\b|\baccording to the\b"
    r"|\bthe (?:manual|policy) (?:says|states)\b",
    re.IGNORECASE,
)


def banned_words(text: str) -> list[str]:
    """The banned phrases found in `text` (whole words, any case)."""
    lowered = text.lower()
    return [p for p in BANNED_PHRASES if re.search(rf"\b{re.escape(p)}\b", lowered)]


def sop_claims(text: str) -> list[str]:
    """The phrases in `text` that state or cite what the SOP or documents say."""
    return [m.group(0) for m in _SOP_CLAIM.finditer(text)]
