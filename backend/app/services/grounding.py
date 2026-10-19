"""Grounding mechanics (PRD §3.8): deterministic checks shared by every stage. No database access.

Phase P2: name redaction (G10) and the instruction-like text flag (G9). Phase P3: segment, quote,
number and role verification (G3-G5), all deterministic so they can be tested offline. Phase
P10: the external grounding gate GX1-GX6 (`verify_citations`) for gap analysis B.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from difflib import SequenceMatcher
from urllib.parse import urlsplit

from app.domain.gap import CitationCheck, CitedSource
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
    # A window a few words wider than the quote lets spoken fillers the quote left out fit in.
    for size in sorted({max(1, width - 1), width, width + 1, width + 2, width + 3}):
        for start in range(max(1, len(text_words) - size + 1)):
            window = text_words[start : start + size]
            similar = SequenceMatcher(None, needle, " ".join(window), autojunk=False).ratio()
            if similar >= threshold and same_meaning(words, window):
                return PASSED
    return fail


# Words a quote may leave out of (or, for articles, add to) the source: spoken hesitations and
# articles, which carry no meaning a map relies on.
FILLERS = frozenset({
    "um", "umm", "uh", "uhm", "er", "erm", "ah", "eh", "hmm", "mm", "like", "you", "know",
    "i", "mean", "sort", "kind", "of", "so", "well", "just", "actually", "basically", "really",
    "okay", "ok", "right", "yeah", "a", "an", "the",
})  # fmt: skip
ARTICLES = frozenset({"a", "an", "the"})
# Negations: a quote that gains or loses one says the opposite of its source.
NEGATIONS = frozenset({
    "not", "no", "never", "none", "nobody", "nothing", "neither", "nor", "without", "cannot",
    "cant", "dont", "doesnt", "didnt", "isnt", "arent", "wasnt", "werent", "wont", "wouldnt",
    "shouldnt", "couldnt", "hasnt", "havent", "hadnt", "mustnt", "neednt", "shant",
})  # fmt: skip
SPELLING = 0.8  # a changed stretch must read almost the same: a typo, "its" for "it is"


def same_meaning(quote: Sequence[str], source: Sequence[str]) -> bool:
    """G4 (deep review, 2026-10-19): the quote differs from its source only in spelling and
    fillers. Character similarity alone cannot tell "approves" from "does not approve" in a long
    quote, so each stretch that differs is checked word by word: a changed stretch must be spelled
    almost the same, no negation may be gained or lost, the quote may leave out only fillers and
    add only articles."""
    for tag, q1, q2, s1, s2 in SequenceMatcher(None, quote, source, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        said, written = quote[q1:q2], source[s1:s2]
        if NEGATIONS.intersection(said) or NEGATIONS.intersection(written):
            return False
        if tag == "delete" and not ARTICLES.issuperset(said):
            return False  # the quote adds a word its source doesn't have
        if tag == "insert" and not FILLERS.issuperset(written):
            return False  # the quote leaves out a word that carries meaning
        if tag == "replace" and (
            SequenceMatcher(None, "".join(said), "".join(written)).ratio() < SPELLING
        ):
            return False  # a different word, not a different spelling
    return True


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


def words_to_digits(text: str) -> str:
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
    for match in _NUMBER.finditer(words_to_digits(text)):
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


# --- External grounding gate GX1-GX6 (PRD §3.11.2 step 4; phase P10) --------------------------

_YEAR = re.compile(r"\b(19|20)\d{2}\b")


def _year(page_age: str) -> int | None:
    found = _YEAR.search(page_age or "")
    return int(found.group(0)) if found else None


def verify_citations(
    *,
    claim: str,
    quote: str,
    citation_ids: Sequence[str],
    citations: Mapping[str, CitedSource],
    search_urls: Collection[str],
    element_ids: Sequence[str],
    known_elements: Collection[str],
    recency_years: int,
    this_year: int,
    tier_of: Callable[[str], str],
) -> CitationCheck:
    """GX1 at least one citation ID; GX2 every cited URL was returned by the search in the same
    request; GX3 the claim is supported by the cited text (the quote found with the G4 similarity,
    every number found as in G5); GX4 weak when only vendor or unknown sources back it; GX5 dated
    when every cited source is older than the recency limit; GX6 unknown step references dropped."""
    kept = [e for e in element_ids if e in known_elements]
    dropped = [e for e in element_ids if e not in known_elements]

    def refused(guardrail: str, reason: str) -> CitationCheck:
        return CitationCheck(
            outcome=CheckOutcome(passed=False, guardrail=guardrail, reason=reason),
            element_ids=kept,
            dropped_element_ids=dropped,
        )

    if not citation_ids:
        return refused("GX1", "no source cited")
    cited = [citations[c] for c in citation_ids if c in citations]
    if len(cited) != len(citation_ids) or any(c.url not in search_urls for c in cited):
        return refused("GX2", "source not returned by the search")
    text = " ".join(c.cited_text for c in cited)
    supported = verify_quote(quote, text).passed and verify_numbers(claim, text).passed
    if not supported:
        return refused("GX3", "claim not found in the cited source text")
    tiers = {domain: tier_of(c.url) for c in cited for domain in [_domain(c.url)]}
    years = [_year(c.page_age) for c in cited]
    dated = all(y is not None and y < this_year - recency_years for y in years)
    return CitationCheck(
        outcome=PASSED,
        weak=all(t in {"vendor", "other"} for t in tiers.values()),
        dated=dated,
        tiers_by_domain=tiers,
        element_ids=kept,
        dropped_element_ids=dropped,
    )


def _domain(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")
