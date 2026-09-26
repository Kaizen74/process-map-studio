"""Grounding mechanics (PRD §3.8): deterministic checks shared by every stage. No database access.

Phase P2: name redaction (G10) and the instruction-like text flag (G9). Segment, quote, number and
role verification (G3-G5) arrive in phase P3.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.domain.models import NameReplacement, Redacted

DEFAULT_REPLACEMENT = "[name]"

# Phrases that address an AI or try to change its instructions (G9). Matched ignoring case.
_INSTRUCTION_LIKE = [
    r"\bignore (?:all |any )?(?:the )?(?:previous|prior|above|earlier|preceding) "
    r"(?:instructions?|prompts?|rules?)",
    r"\bdisregard (?:all |any )?(?:the )?(?:previous|prior|above|earlier|your) "
    r"(?:instructions?|prompts?|rules?)",
    r"\bforget (?:all |any )?(?:the )?(?:previous|prior|above|your) (?:instructions?|rules?)",
    r"\bnote to (?:automated systems?|(?:the )?ai\b|(?:the )?(?:language )?models?|"
    r"(?:the )?assistants?|(?:any )?(?:llms?|bots?|chatbots?))",
    r"\b(?:you are|act as) (?:an? )?(?:ai|assistant|language model|llm|chatbot)\b",
    r"\bsystem prompt\b",
    r"\bnew instructions?:",
    r"\b(?:classify|mark|label|rate|score) (?:every|all|each) (?:step|element|claim)s? as\b",
    r"\bdo not (?:follow|obey) (?:the |your )?(?:previous |prior )?instructions?\b",
]
_INSTRUCTION_PATTERN = re.compile("|".join(f"(?:{p})" for p in _INSTRUCTION_LIKE), re.IGNORECASE)


def detect_instruction_like(text: str) -> bool:
    """True when a passage addresses an AI or tries to change its instructions (G9).

    Such passages stay in the source as data; the app labels them so they are visible, and prompts
    tell the model to ignore instructions inside source text.
    """
    return bool(_INSTRUCTION_PATTERN.search(text))


def _term_pattern(term: str) -> re.Pattern[str] | None:
    words = term.split()
    if not words:
        return None
    body = r"\s+".join(re.escape(word) for word in words)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


def redact_text(text: str, terms: Sequence[NameReplacement]) -> Redacted:
    """Replace every term (whole words, any case, any spacing) with its replacement (G10).

    Longer terms go first so "Priya Nair" is replaced as a whole before "Priya".
    """
    hits = 0
    for item in sorted(terms, key=lambda t: len(t.term), reverse=True):
        pattern = _term_pattern(item.term)
        if pattern is None:
            continue
        text, count = pattern.subn(item.replacement or DEFAULT_REPLACEMENT, text)
        hits += count
    return Redacted(text=text, hits=hits)


def scan_redaction_terms(text: str, terms: Sequence[str]) -> list[str]:
    """The terms that appear in the text (whole words, any case), in the order given."""
    found = []
    for term in terms:
        pattern = _term_pattern(term)
        if pattern is not None and pattern.search(text):
            found.append(term)
    return found
