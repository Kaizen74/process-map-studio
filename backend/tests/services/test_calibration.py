"""Calibration rules (PRD §3.7 source states and JD test, §3.8 G7 confidence, Appendix A.6 note)."""

from __future__ import annotations

import pytest

from app.domain.models import AccountableFact, StanceFact
from app.services import calibration

INTERVIEW, SOP, MANUAL, JD, ARTEFACT, OTHER = (
    "interview_transcript",
    "sop",
    "manual",
    "job_description",
    "executed_artefact",
    "other",
)


def stances(*entries: tuple[str, str]) -> list[StanceFact]:
    """(source kind, stance) pairs; each entry is its own source."""
    return [
        StanceFact(source_id=f"s{i}", source_kind=kind, stance=stance)
        for i, (kind, stance) in enumerate(entries)
    ]


# --- Source states ----------------------------------------------------------------------------

S, C, N = "supports", "contradicts", "silent"
I_, SOP_, MAN, ART = INTERVIEW, SOP, MANUAL, ARTEFACT

STATES = [
    # The five states from PRD §3.7.
    ("corroborated", [(I_, S), (SOP_, S)]),
    ("corroborated: a manual also counts as a document", [(I_, S), (MAN, S)]),
    ("practiced_only", [(I_, S), (SOP_, N)]),
    ("documented_only", [(I_, N), (SOP_, S)]),
    ("contested: interview supports, document contradicts", [(I_, S), (SOP_, C)]),
    ("contested: interview contradicts, document supports", [(I_, C), (SOP_, S)]),
    ("contested: one document agrees, another disagrees", [(I_, S), (SOP_, S), (MAN, C)]),
    ("trace_contradicted", [(I_, S), (SOP_, S), (ART, C)]),
    ("trace_contradicted: beats contested", [(I_, S), (SOP_, C), (ART, C)]),
    ("trace_contradicted: against a document alone", [(SOP_, S), (ART, C)]),
    ("corroborated: a supporting executed artefact counts as a document", [(I_, S), (ART, S)]),
    ("not_assessed: no counted source addresses it", [(I_, N), (SOP_, N)]),
    ("not_assessed: only a job description mentions it", [(JD, S)]),
    ("practiced_only: an 'other' document silent", [(I_, S), (OTHER, N)]),
]


@pytest.mark.parametrize(("expected", "entries"), STATES, ids=[s[0] for s in STATES])
def test_source_states(expected: str, entries: list[tuple[str, str]]) -> None:
    assert calibration.assign_source_state(stances(*entries), "O") == expected.split(":")[0]


def test_recommended_elements_are_not_assessed_whatever_the_sources_say() -> None:
    entries = stances((INTERVIEW, "supports"), (SOP, "supports"))
    assert calibration.assign_source_state(entries, "R") == "not_assessed"


@pytest.mark.parametrize(
    "base",
    [
        [(INTERVIEW, "supports"), (SOP, "supports")],
        [(INTERVIEW, "supports")],
        [(SOP, "supports")],
        [(INTERVIEW, "supports"), (SOP, "contradicts")],
    ],
)
@pytest.mark.parametrize(
    "extra", [(SOP, "silent"), (JD, "silent"), (JD, "contradicts"), (JD, "supports")]
)
def test_silence_and_job_descriptions_never_change_the_state(
    base: list[tuple[str, str]], extra: tuple[str, str]
) -> None:
    """Constraint 4: a silent source is silent, never contradicts; JD stances never count."""
    before = calibration.assign_source_state(stances(*base), "O")
    after = calibration.assign_source_state(stances(*base, extra), "O")
    assert after == before


def test_supporting_sources_counts_distinct_sources_without_job_descriptions() -> None:
    facts = [
        StanceFact(source_id="a", source_kind=INTERVIEW, stance="supports"),
        StanceFact(source_id="a", source_kind=INTERVIEW, stance="supports"),
        StanceFact(source_id="b", source_kind=SOP, stance="supports"),
        StanceFact(source_id="c", source_kind=JD, stance="supports"),
        StanceFact(source_id="d", source_kind=MANUAL, stance="silent"),
    ]
    assert calibration.supporting_sources(facts) == 2


# --- JD accountability test -------------------------------------------------------------------


def accountable(*entries: tuple[str, str]) -> list[AccountableFact]:
    return [
        AccountableFact(source_id=f"s{i}", source_kind=kind, role=role)
        for i, (kind, role) in enumerate(entries)
    ]


def test_sop_and_interview_disagree_on_the_accountable_role() -> None:
    """A.5 'Deviation in limits?': Load control lead (SOP) vs Captain (interview); JD silent."""
    result = calibration.jd_accountability_test(
        accountable((SOP, "Load control lead"), (INTERVIEW, "Captain"))
    )
    assert result.contested is True
    assert result.roles == ["Load control lead", "Captain"]
    assert result.sources_by_role == {"Load control lead": ["s0"], "Captain": ["s1"]}


def test_job_description_disagreeing_makes_it_contested() -> None:
    result = calibration.jd_accountability_test(
        accountable((SOP, "Load control lead"), (JD, "Duty manager"))
    )
    assert result.contested and result.roles == ["Load control lead", "Duty manager"]


def test_agreement_ignoring_case_and_spaces_is_not_contested() -> None:
    result = calibration.jd_accountability_test(
        accountable((SOP, "Load Control Lead"), (JD, "load  control lead"), (INTERVIEW, ""))
    )
    assert result.contested is False
    assert result.roles == ["Load Control Lead"]
    assert result.sources_by_role == {"Load Control Lead": ["s0", "s1"]}


def test_no_accountable_role_anywhere_is_not_contested() -> None:
    result = calibration.jd_accountability_test(accountable((INTERVIEW, " "), (SOP, "")))
    assert result.contested is False and result.roles == []


# --- Confidence (G7) --------------------------------------------------------------------------

CONFIDENCE = [
    # provenance, supporting sources, verifier, contested → value, labels
    ("O", 1, "not_run", False, 0.60, ["Observed (O)", "Independent verifier: not run"]),
    ("I", 1, "not_run", False, 0.40, ["Inferred (I)", "Independent verifier: not run"]),
    ("O", 2, "supported", False, 0.85,
     ["Observed (O)", "1 more independent source supports", "Independent verifier: supported"]),
    ("O", 3, "supported", False, 1.00,
     ["Observed (O)", "2 more independent sources support", "Independent verifier: supported"]),
    ("O", 5, "supported", False, 1.00,
     ["Observed (O)", "2 more independent sources support", "Independent verifier: supported"]),
    ("O", 2, "partial", False, 0.55,
     ["Observed (O)", "1 more independent source supports", "Independent verifier: partial"]),
    ("I", 1, "partial", False, 0.20, ["Inferred (I)", "Independent verifier: partial"]),
    ("O", 2, "supported", True, 0.60,
     ["Observed (O)", "1 more independent source supports", "Independent verifier: supported",
      "Capped at 0.60 while contested"]),
    ("I", 1, "supported", True, 0.50, ["Inferred (I)", "Independent verifier: supported"]),
    ("O", 0, "supported", False, 0.70, ["Observed (O)", "Independent verifier: supported"]),
]  # fmt: skip


@pytest.mark.parametrize(
    ("provenance", "supporting", "verifier", "contested", "value", "labels"), CONFIDENCE
)
def test_confidence_follows_g7_and_the_breakdown_sums_to_the_value(
    provenance: str,
    supporting: int,
    verifier: str,
    contested: bool,
    value: float,
    labels: list[str],
) -> None:
    result = calibration.derive_confidence(provenance, supporting, verifier, contested)
    assert result.value == value
    assert [t.label for t in result.breakdown] == labels
    assert round(sum(t.delta for t in result.breakdown), 2) == result.value


def test_capped_breakdown_shows_the_cap_as_its_own_term() -> None:
    result = calibration.derive_confidence("O", 2, "supported", contested=True)
    assert [t.delta for t in result.breakdown] == [0.6, 0.15, 0.1, -0.25]


def test_confidence_is_only_computed_for_observed_and_inferred() -> None:
    with pytest.raises(ValueError, match="O and I"):
        calibration.derive_confidence("R", 1, "not_run", False)


def test_low_confidence_threshold_is_half() -> None:
    assert calibration.LOW_CONFIDENCE == 0.50
