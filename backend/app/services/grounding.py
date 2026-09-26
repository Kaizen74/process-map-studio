"""Grounding mechanics (PRD §3.8): deterministic checks shared by every stage. No database access.

Phase P2: name redaction (G10) and the instruction-like text flag (G9). Phase P3: segment, quote,
number and role verification (G3-G5), all deterministic so they can be tested offline.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Sequence
from difflib import SequenceMatcher

from app.domain.models import CheckOutcome, NameReplacement, Redacted

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


# --- G3-G5: is every claim grounded in the passages it cites? (PRD §3.8) ------------------------

QUOTE_THRESHOLD = 0.90  # PRD §3.8 G4: minimum similarity of the quote to the cited text
QUOTE_MAX_WORDS = 40  # PRD §3.8 G2
PASSED = CheckOutcome(passed=True)

_QUOTE_MARKS = str.maketrans(
    {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-"}
)
_NOT_WORD = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")


def normalise_text(text: str) -> str:
    """Lower case, curly quotes and dashes made plain, punctuation removed, spaces collapsed."""
    plain = text.translate(_QUOTE_MARKS).lower()
    plain = _NOT_WORD.sub(" ", plain.replace("'", ""))
    return _SPACES.sub(" ", plain).strip()


def verify_segments(cited: Sequence[str], provided: Collection[str]) -> CheckOutcome:
    """G3: the claim cites at least one passage, and only passages sent in the same call."""
    if not cited:
        return CheckOutcome(passed=False, guardrail="G3", reason="cites no passage")
    missing = [segment for segment in cited if segment not in provided]
    if missing:
        return CheckOutcome(
            passed=False, guardrail="G3", reason="cites a passage that wasn't provided"
        )
    return PASSED


def verify_quote(quote: str, cited_text: str, threshold: float = QUOTE_THRESHOLD) -> CheckOutcome:
    """G4: the quote appears in the cited text, allowing only minor differences.

    Both are normalised (case, spacing, punctuation, quote marks); the quote must then match a
    stretch of the cited text of the same length with similarity at least `threshold`.
    """
    fail = CheckOutcome(passed=False, guardrail="G4", reason="quote not found in source")
    words = normalise_text(quote).split()
    if not words:
        return fail
    if len(quote.split()) > QUOTE_MAX_WORDS:
        return CheckOutcome(
            passed=False, guardrail="G4", reason=f"quote longer than {QUOTE_MAX_WORDS} words"
        )
    needle = " ".join(words)
    haystack = normalise_text(cited_text)
    if needle in haystack:
        return PASSED
    text_words = haystack.split()
    width = len(words)
    best = 0.0
    for size in {max(1, width - 1), width, width + 1}:
        for start in range(max(1, len(text_words) - size + 1)):
            window = " ".join(text_words[start : start + size])
            best = max(best, SequenceMatcher(None, needle, window, autojunk=False).ratio())
            if best >= threshold:
                return PASSED
    return fail


_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}  # fmt: skip
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}  # fmt: skip
_NUMBER_WORD = re.compile(
    r"\b(?P<tens>"
    + "|".join(_TENS)
    + r")(?:[\s-](?P<unit>"
    + "|".join(k for k in _UNITS if k != "zero")
    + r"))?\b"
    r"|\b(?P<single>" + "|".join(_UNITS) + r")\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"(?<![\w.])(?P<t>[Tt]\s?[-\u2013]\s?)?(?P<n>\d+(?:[.,]\d+)?)")


def _words_to_digits(text: str) -> str:
    """ "twenty minutes" → "20 minutes"; "fifteen to forty" → "15 to 40"."""

    def replace(match: re.Match[str]) -> str:
        if match.group("single"):
            return str(_UNITS[match.group("single").lower()])
        value = _TENS[match.group("tens").lower()]
        if match.group("unit"):
            value += _UNITS[match.group("unit").lower()]
        return str(value)

    return _NUMBER_WORD.sub(replace, text)


def numbers_in(text: str) -> set[str]:
    """Every number, time offset or threshold in the text, in a comparable form.

    "20 min" → "20"; "fifteen" → "15"; "10%" → "10"; "T-90" → "T-90" (an offset is not the
    same as the plain number 90); "1,5" and "1.5" → "1.5"; "06:40" → "6" and "40".
    """
    found: set[str] = set()
    for match in _NUMBER.finditer(_words_to_digits(text)):
        raw = match.group("n").replace(",", ".")
        value = str(float(raw)).removesuffix(".0") if "." in raw else str(int(raw))
        found.add(f"T-{value}" if match.group("t") else value)
    return found


def verify_numbers(claim_text: str, cited_text: str, basis: str = "") -> CheckOutcome:
    """G5 (numbers): every number in the claim appears in the cited text (number words count).

    An inferred claim may state a number that isn't in the text only if its `basis` shows the
    derivation: the number appears in the basis together with at least one number from the text.
    """
    cited = numbers_in(cited_text)
    missing = sorted(numbers_in(claim_text) - cited)
    if missing and basis:
        in_basis = numbers_in(basis)
        if in_basis & cited:
            missing = [n for n in missing if n not in in_basis]
    if missing:
        return CheckOutcome(
            passed=False,
            guardrail="G5",
            reason="number not found in cited text: " + ", ".join(missing),
        )
    return PASSED


def _mentions(text: str, name: str) -> bool:
    words = normalise_text(name)
    if not words:
        return False
    return re.search(rf"(?<!\w){re.escape(words)}s?(?!\w)", text) is not None


def verify_roles(
    roles: Iterable[str], cited_text: str, known: Sequence[Sequence[str]] = ()
) -> CheckOutcome:
    """G5 (roles): every role the claim names appears in the cited text, directly or through a
    role Eric confirmed: each entry of `known` is one role's name followed by its aliases, and
    naming any of them counts for all of them ("Load controller" / "LC")."""
    text = normalise_text(cited_text)
    for role in roles:
        if not role.strip():
            continue
        group = next(
            (g for g in known if any(normalise_text(n) == normalise_text(role) for n in g)),
            [role],
        )
        if not any(_mentions(text, name) for name in group):
            return CheckOutcome(
                passed=False, guardrail="G5", reason=f"role not found in cited text: {role}"
            )
    return PASSED
