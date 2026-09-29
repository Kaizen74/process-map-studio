"""Gap analysis mechanics (PRD §3.11; Appendix A.7): the brief, the confidentiality scan (TE5),
source tiers, the external grounding gate GX1-GX6 (TE1-TE4, TE7) and the severity rules."""

from __future__ import annotations

import pytest

from app.domain.gap import BriefInput, CitedSource
from app.services import gap, grounding

FACTS = BriefInput(
    process_name="Acme Ground Services load control",
    industry="Aviation ground handling",
    adjacent_industries=["Air cargo", "Airport operations"],
    step_labels=[
        "Draft load plan",
        "Approve load plan",
        "Issue load sheet by T-15",
        "Load and return LIR within 10 min",
        "Check LC-07 special loads",
    ],
    confidential_terms=["Acme Ground Services", "LC-07", "RP-02"],
    hidden_names=["Priya Nair"],
)
TRANSCRIPT = (
    "Ramp loads the aircraft and brings the paper loading report back to me, which can take "
    "up to fifteen minutes when containers are short."
)


def test_the_draft_brief_is_generic() -> None:
    brief = gap.build_brief(FACTS)
    assert brief.process_name == "load control"
    assert brief.steps == [
        "Draft load plan",
        "Approve load plan",
        "Issue load sheet by",
        "Load and return LIR within",
        "Check special loads",
    ]
    assert (brief.industry, brief.adjacent_industries) == (
        "Aviation ground handling",
        ["Air cargo", "Airport operations"],
    )
    assert brief.questions == list(gap.DEFAULT_QUESTIONS)
    assert (
        brief.max_searches,
        brief.recency_years,
        brief.allowed_domains,
        brief.blocked_domains,
    ) == (
        10,
        5,
        [],
        [],
    )
    text = gap.brief_text(brief)
    assert "Acme" not in text and "LC-07" not in text and "10" not in text and "T-15" not in text
    scan = gap.scan_brief(
        text,
        hidden_names=FACTS.hidden_names,
        confidential_terms=FACTS.confidential_terms,
        map_numbers={"10", "15", "20", "5"},
        passages=[TRANSCRIPT],
    )
    assert scan == []  # the drafted brief passes its own scan


def test_te5_a_brief_with_a_company_a_name_and_a_passage_is_blocked_three_times() -> None:
    brief = gap.build_brief(FACTS)
    brief.steps.append("Acme Ground Services asks Priya Nair to check it")
    brief.questions.append(
        "Why does ramp bring the paper loading report back to me, which can take so long?"
    )
    hits = gap.scan_brief(
        gap.brief_text(brief),
        hidden_names=FACTS.hidden_names,
        confidential_terms=FACTS.confidential_terms,
        map_numbers={"10", "15"},
        passages=[TRANSCRIPT],
    )
    assert [(h.reason, h.text) for h in hits] == [
        ("A name from your list of names to hide", "Priya Nair"),
        ("A confidential term from Setup", "Acme Ground Services"),
        (
            "Words copied from your sources",
            "the paper loading report back to me which can take",
        ),
    ]  # the ten copied words are one hit, not three overlapping ones


def test_numbers_from_the_map_are_hits() -> None:
    hits = gap.scan_brief(
        "Is 10 minutes typical?",
        hidden_names=[],
        confidential_terms=[],
        map_numbers={"10"},
        passages=[],
    )
    assert [(h.text, h.reason) for h in hits] == [("10", "A number or time copied from the map")]


@pytest.mark.parametrize(
    ("url", "tier"),
    [
        ("https://www.iso.org/standard/1.html", "standards_body"),
        ("https://www.easa.europa.eu/guidance", "regulator"),
        ("https://www.faa.gov/ac", "regulator"),
        ("https://transport.gov.sg/x", "regulator"),
        ("https://www.iata.org/en/publications/ahm", "industry_association"),
        ("https://doi.org/10.1/abc", "academic"),
        ("https://www.mit.edu/paper", "academic"),
        ("https://www.mckinsey.com/insights", "consultancy"),
        ("https://www.reuters.com/a", "news"),
        ("https://www.swissport.com/en", "peer_operator"),
        ("https://www.sita.aero/blog", "vendor"),
        ("https://loadplanning-software.example.com/blog", "other"),
    ],
)
def test_source_tiers(url: str, tier: str) -> None:
    assert gap.source_tier(url) == tier


CITES = {
    "c1": CitedSource(
        id="c1",
        url="https://www.iata.org/ahm",
        title="IATA AHM",
        cited_text="The load sheet shall be checked by a second qualified person "
        "before it is signed.",
        page_age="March 2024",
    ),
    "c2": CitedSource(
        id="c2",
        url="https://loadplanning-software.example.com/blog",
        title="Vendor blog",
        cited_text="Automated tools check the load sheet.",
        page_age="",
    ),
    "c3": CitedSource(
        id="c3",
        url="https://www.iso.org/old",
        title="Old standard",
        cited_text="A second person checks the load sheet.",
        page_age="2009",
    ),
}
SEARCHED = {c.url for c in CITES.values()}


def check(**changes: object) -> object:
    base: dict[str, object] = {
        "claim": "A second qualified person checks the load sheet before it is signed.",
        "quote": "checked by a second qualified person before it is signed",
        "citation_ids": ["c1"],
        "citations": CITES,
        "search_urls": SEARCHED,
        "element_ids": ["e1"],
        "known_elements": {"e1"},
        "recency_years": 5,
        "this_year": 2026,
        "tier_of": gap.source_tier,
    }
    return grounding.verify_citations(**{**base, **changes})  # type: ignore[arg-type]


def test_a_well_cited_finding_passes_with_its_tier() -> None:
    result = check()
    assert result.outcome.passed and not result.weak and not result.dated  # type: ignore[attr-defined]
    assert result.tiers_by_domain == {"iata.org": "industry_association"}  # type: ignore[attr-defined]


def test_gx1_to_gx3_reject() -> None:
    assert check(citation_ids=[]).outcome.guardrail == "GX1"  # type: ignore[attr-defined]  # TE2
    # TE1: a URL the search never returned.
    assert check(search_urls={"https://elsewhere.org"}).outcome.guardrail == "GX2"  # type: ignore[attr-defined]
    assert check(citation_ids=["c9"]).outcome.guardrail == "GX2"  # type: ignore[attr-defined]
    # TE3: a number absent from the cited text.
    te3 = check(claim="A second person checks the load sheet within 5 minutes.")
    assert te3.outcome.guardrail == "GX3"  # type: ignore[attr-defined]
    assert te3.outcome.reason == "claim not found in the cited source text"  # type: ignore[attr-defined]
    assert check(quote="words that are nowhere in the source").outcome.guardrail == "GX3"  # type: ignore[attr-defined]


def test_gx4_to_gx6_keep_but_flag() -> None:
    te4 = check(
        claim="Automated tools check the load sheet.",
        quote="Automated tools check the load sheet",
        citation_ids=["c2"],
    )
    assert te4.outcome.passed and te4.weak  # type: ignore[attr-defined]
    old = check(
        claim="A second person checks the load sheet.",
        quote="A second person checks the load sheet",
        citation_ids=["c3"],
    )
    assert old.outcome.passed and old.dated  # type: ignore[attr-defined]
    te7 = check(element_ids=["e1", "ghost"])
    assert te7.outcome.passed  # type: ignore[attr-defined]
    assert (te7.element_ids, te7.dropped_element_ids) == (["e1"], ["ghost"])  # type: ignore[attr-defined]


def test_internal_severity_follows_the_a7_table() -> None:
    assert gap.severity_internal("dead_control_candidate", ["approval"]) == "high"
    assert gap.severity_internal("threshold_gap", ["activity"]) == "medium"
    assert gap.severity_internal("ownership_mismatch", ["decision"]) == "high"
    assert gap.severity_internal("undocumented_work", ["activity"]) == "medium"
    assert gap.severity_internal("sequence_gap", ["activity"]) == "low"
    assert gap.severity_internal("sequence_gap", ["activity"], trace_contradicted=True) == "high"
    # A.7: "Resolve or offload" sits on the exception path (reached by "No"): an exception-path
    # gap is Medium, like practiced-only work on the main path.
    assert gap.severity_internal("undocumented_work", ["activity"]) == "medium"
    # A documented-only step that isn't a control is an omission of a non-control step: Low.
    assert gap.severity_internal("dead_control_candidate", ["activity"]) == "low"
    assert gap.severity_internal("trigger_gap", ["activity"]) == "low"
    assert gap.severity_internal("exception_gap", ["activity"]) == "medium"


def test_external_severity_and_the_compliance_note() -> None:
    assert (
        gap.severity_external("missing_control", {"iso.org": "standards_body"}, dated=False)
        == "high"
    )
    assert (
        gap.severity_external(
            "missing_control",
            {"iata.org": "industry_association", "reuters.com": "news"},
            dated=False,
        )
        == "high"
    )
    assert (
        gap.severity_external("missing_control", {"iata.org": "industry_association"}, dated=False)
        == "medium"
    )
    assert (
        gap.severity_external("kpi_practice", {"iso.org": "standards_body"}, dated=False)
        == "medium"
    )
    assert (
        gap.severity_external("missing_step", {"x.example.com": "other"}, dated=False) == "low"
    )  # TE4
    assert (
        gap.severity_external("missing_control", {"iso.org": "standards_body"}, dated=True) == "low"
    )
    assert gap.needs_compliance_note("Operators are required by law to …", ["other"])
    assert gap.needs_compliance_note("A check", ["regulator"])
    assert not gap.needs_compliance_note("A second person checks it.", ["industry_association"])


def test_excerpts_are_at_most_25_words() -> None:
    long = " ".join(f"w{i}" for i in range(40))
    assert len(gap.excerpt(long).split()) == 25 and gap.excerpt(long).endswith("…")
    assert gap.excerpt("short text") == "short text"
