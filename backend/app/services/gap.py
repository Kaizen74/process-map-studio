"""Gap analysis mechanics (PRD §3.11; phase P10). Deterministic, no AI, no database.

- `build_brief`: the research brief for analysis B from the version's generic facts only.
- `brief_text`: exactly what is sent to web search (and nothing else is).
- `scan_brief`: the confidentiality gate: names to hide, confidential terms, numbers and times
  copied from the map, and any run of 8+ consecutive words found in a source passage.
- `source_tier`: the source tier of a URL (B.24) from a domain table.
- `severity_internal` / `severity_external`: the §3.11 severity rules.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from urllib.parse import urlsplit

from app.domain.gap import Brief, BriefInput, ScanHit
from app.services.grounding import normalise_text, numbers_in, scan_redaction_terms

DEFAULT_QUESTIONS = (
    "What steps, controls and approvals do comparable processes typically include?",
    "How are decision rights and approvals typically allocated?",
    "What cycle-time, KPI or threshold benchmarks are published?",
    "What technology or automation is commonly used?",
)
DEFAULT_MAX_SEARCHES = 10
MAX_SEARCHES_RANGE = (3, 20)
DEFAULT_RECENCY_YEARS = 5
COPIED_RUN_WORDS = 8

# Times, thresholds and figures never go into a generic step label.
_FIGURES = re.compile(
    r"(?i)\b[Tt]\s?[-\u2013]\s?\d+\b|\b\d+(?:[.,]\d+)?\s*(?:%|min(?:ute)?s?|h(?:ou)?rs?|kg|tonnes?|t)?\b"
)
_SPACES = re.compile(r"\s+")


def _generic(label: str, remove: Sequence[str]) -> str:
    """A step label without any confidential or hidden term (first, so a term containing a number
    such as "LC-07" goes whole) and without figures."""
    text = label
    for term in remove:
        if term.strip():
            text = re.sub(rf"(?i)\b{re.escape(term.strip())}\b", " ", text)
    text = _FIGURES.sub(" ", text)
    return _SPACES.sub(" ", text).strip(" -\u2013,;:")


def build_brief(facts: BriefInput) -> Brief:
    """The draft brief Eric edits (PRD §3.11.2 step 1): generic process name, industry, adjacent
    industries, the step labels made generic, the default questions and source policy."""
    remove = [*facts.confidential_terms, *facts.hidden_names]
    steps: list[str] = []
    for label in facts.step_labels:
        generic = _generic(label, remove)
        if generic and generic.lower() not in {s.lower() for s in steps}:
            steps.append(generic)
    return Brief(
        process_name=_generic(facts.process_name, remove) or "Business process",
        industry=facts.industry,
        adjacent_industries=list(facts.adjacent_industries),
        region="",
        steps=steps,
        questions=list(DEFAULT_QUESTIONS),
        max_searches=DEFAULT_MAX_SEARCHES,
        allowed_domains=[],
        blocked_domains=[],
        recency_years=DEFAULT_RECENCY_YEARS,
    )


def brief_text(brief: Brief) -> str:
    """The research request exactly as sent: only the brief's own words (the source policy goes
    to the search tool settings, not into the text)."""
    lines = [f"Process: {brief.process_name}"]
    if brief.industry:
        lines.append(f"Industry: {brief.industry}")
    if brief.adjacent_industries:
        lines.append("Adjacent industries: " + "; ".join(brief.adjacent_industries))
    if brief.region:
        lines.append(f"Region focus: {brief.region}")
    if brief.steps:
        lines.append("Steps of the process as it is done today:")
        lines += [f"- {s}" for s in brief.steps]
    if brief.questions:
        lines.append("Research questions:")
        lines += [f"- {q}" for q in brief.questions]
    return "\n".join(lines)


def _terms_found(text: str, terms: Iterable[str]) -> list[str]:
    return scan_redaction_terms(text, [t for t in terms if t.strip()])


def _copied_runs(text: str, passages: Iterable[str], run: int = COPIED_RUN_WORDS) -> list[str]:
    """Each maximal run of `run`+ consecutive words of `text` that also appears in a passage."""
    words = normalise_text(text).split()
    if len(words) < run:
        return []
    shingles: set[tuple[str, ...]] = set()
    for passage in passages:
        tokens = normalise_text(passage).split()
        shingles.update(tuple(tokens[i : i + run]) for i in range(len(tokens) - run + 1))
    hits: list[str] = []
    i = 0
    while i <= len(words) - run:
        if tuple(words[i : i + run]) in shingles:
            end = i + run
            while end < len(words) and tuple(words[end - run + 1 : end + 1]) in shingles:
                end += 1
            hits.append(" ".join(words[i:end]))
            i = end
        else:
            i += 1
    return hits


def scan_brief(
    text: str,
    *,
    hidden_names: Sequence[str],
    confidential_terms: Sequence[str],
    map_numbers: Iterable[str],
    passages: Iterable[str],
) -> list[ScanHit]:
    """The confidentiality gate (PRD §3.11.2): every hit blocks the run until removed."""
    hits = [
        ScanHit(text=t, reason="A name from your list of names to hide")
        for t in _terms_found(text, hidden_names)
    ]
    hits += [
        ScanHit(text=t, reason="A confidential term from Setup")
        for t in _terms_found(text, confidential_terms)
    ]
    copied_numbers = sorted(numbers_in(text) & set(map_numbers))
    hits += [ScanHit(text=n, reason="A number or time copied from the map") for n in copied_numbers]
    hits += [
        ScanHit(text=run, reason="Words copied from your sources")
        for run in _copied_runs(text, passages)
    ]
    return hits


# --- Source tiers (B.24, GX4) -------------------------------------------------------------------

_TIERS: dict[str, tuple[str, ...]] = {
    "standards_body": ("iso.org", "icao.int", "sae.org", "iec.ch", "nist.gov", "cen.eu"),
    "regulator": (
        "faa.gov",
        "easa.europa.eu",
        "caa.co.uk",
        "caas.gov.sg",
        "casa.gov.au",
        "tc.gc.ca",
        "dgca.gov.in",
        "osha.gov",
        "hse.gov.uk",
    ),
    "industry_association": (
        "iata.org",
        "aci.aero",
        "airlines.org",
        "ahm.iata.org",
        "tiaca.org",
        "fiata.org",
        "flightsafety.org",
    ),
    "academic": (
        "doi.org",
        "sciencedirect.com",
        "springer.com",
        "tandfonline.com",
        "jstor.org",
        "ieee.org",
        "researchgate.net",
        "arxiv.org",
        "wiley.com",
        "mdpi.com",
    ),
    "consultancy": (
        "mckinsey.com",
        "bcg.com",
        "bain.com",
        "deloitte.com",
        "pwc.com",
        "ey.com",
        "kpmg.com",
        "accenture.com",
        "oliverwyman.com",
        "rolandberger.com",
    ),
    "news": (
        "reuters.com",
        "bbc.co.uk",
        "bbc.com",
        "ft.com",
        "bloomberg.com",
        "aviationweek.com",
        "flightglobal.com",
        "aircargonews.net",
        "simpleflying.com",
    ),
    "peer_operator": (
        "swissport.com",
        "dnata.com",
        "menziesaviation.com",
        "wfs.aero",
        "lufthansa.com",
        "britishairways.com",
        "emirates.com",
        "qantas.com",
    ),
    "vendor": ("sita.aero", "amadeus.com", "lhsystems.com", "sabre.com", "ibsplc.com"),
}
WEAK_TIERS = {"vendor", "other"}
STRONG_TIERS = {"standards_body", "regulator"}


def domain_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


def source_tier(url: str) -> str:
    """B.24 tier from the domain table; government and university domains by suffix; else other."""
    host = domain_of(url)
    for tier, domains in _TIERS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return tier
    if host.endswith(".gov") or ".gov." in host or host.endswith(".gouv.fr"):
        return "regulator"
    if host.endswith(".edu") or ".ac." in host or ".edu." in host:
        return "academic"
    return "other"


# --- Severity (PRD §3.11.1 step 5, §3.11.2 step 6) ------------------------------------------------

CONTROL_KINDS = {"decision", "approval"}
COMPLIANCE_NOTE = "Confirm with your compliance team; this is not legal advice."
_REGULATORY = re.compile(r"(?i)\b(regulat\w*|legal\w*|law|laws|mandatory|required by|compliance)\b")


def severity_internal(
    finding_type: str,
    kinds: Sequence[str],
    *,
    trace_contradicted: bool = False,
) -> str:
    """High: ownership or threshold divergence on a decision or approval; a documented-only
    control; any trace-contradicted step. Medium: practiced-only work on the main path or with
    K-RISK, and exception-path gaps (practiced-only work off the main path is on an exception
    route; A.7 "Resolve or offload"); ownership or threshold differences on activities. Low:
    sequence or trigger differences on activities; omissions of non-control steps."""
    control = any(k in CONTROL_KINDS for k in kinds)
    if trace_contradicted:
        return "high"
    if control and finding_type in {
        "ownership_mismatch",
        "threshold_gap",
        "dead_control_candidate",
    }:
        return "high"
    # Practiced-only work is on the main path or on an exception route: Medium either way.
    if finding_type in {
        "undocumented_work",
        "exception_gap",
        "threshold_gap",
        "ownership_mismatch",
    }:
        return "medium"
    return "low"


def independent_strong_sources(tiers_by_domain: dict[str, str]) -> int:
    return sum(1 for tier in tiers_by_domain.values() if tier not in WEAK_TIERS)


def severity_external(finding_type: str, tiers_by_domain: dict[str, str], *, dated: bool) -> str:
    """High: a missing control, approval or decision-rights difference backed by a standards body
    or regulator, or by 2+ independent non-vendor sources. Medium: one non-vendor source. Low:
    weak (vendor or unknown sources only) or dated evidence only."""
    solid = independent_strong_sources(tiers_by_domain)
    if solid == 0 or dated:
        return "low"
    control = finding_type in {"missing_control", "decision_rights_difference"}
    if control and (STRONG_TIERS & set(tiers_by_domain.values()) or solid >= 2):
        return "high"
    return "medium"


def needs_compliance_note(text: str, tiers: Iterable[str]) -> bool:
    return "regulator" in set(tiers) or bool(_REGULATORY.search(text))


def excerpt(text: str, max_words: int = 25) -> str:
    """At most 25 words of a cited source (PRD §3.11.2 step 7)."""
    words = text.split()
    return " ".join(words[:max_words]) + ("…" if len(words) > max_words else "")
