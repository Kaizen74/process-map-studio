"""The alignment matrix (PRD §4 Views, §5.4 Matrix, §3.7 Stage 3): one row per step, each kind of
source classified as supports · contradicts · silent · not_applicable, never reconciled; silence is
never contradiction (constraint 4)."""

from __future__ import annotations

import pytest

from app.domain.enums import SourceKind
from app.domain.graph import AccountSummary, GraphEvidence
from app.services import alignment
from tests.services.test_lint import clean, element, replace


def said(kind: str, stance: str, source: str = "s") -> GraphEvidence:
    segment = None if stance == "silent" else f"seg-{source}"
    return GraphEvidence(segment_id=segment, source_id=f"{source}-{kind}", source_kind=kind,
                         stance=stance, anchor="", verified=stance != "silent")  # fmt: skip


def test_every_source_kind_sits_in_exactly_one_column() -> None:
    columns = list(alignment.COLUMNS.values())
    assert set().union(*columns) == {k.value for k in SourceKind}
    assert sum(len(c) for c in columns) == len(SourceKind)


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        ([], "not_applicable"),  # no source of that kind at all
        ([said("sop", "silent")], "silent"),  # the SOP doesn't mention the step
        ([said("sop", "supports")], "supports"),
        ([said("sop", "silent"), said("manual", "supports", "m")], "supports"),
        ([said("sop", "supports"), said("manual", "contradicts", "m")], "contradicts"),
        ([said("other", "contradicts")], "contradicts"),  # "other" documents count as documents
    ],
)
def test_a_column_is_its_strongest_stance(evidence: list[GraphEvidence], expected: str) -> None:
    assert alignment.cell(evidence, alignment.DOCUMENTS) == expected


def test_one_row_per_step_in_process_order_with_state_and_divergence() -> None:
    graph = replace(
        clean(),
        "plan",
        source_state="contested",
        divergence_types=["threshold"],
        evidence=[
            said("sop", "supports"),
            said("interview_transcript", "contradicts", "i"),
            said("job_description", "silent", "j"),
        ],
    )
    rows = alignment.alignment_matrix(graph)
    steps = [e.id for e in graph.elements if e.kind in {"activity", "decision", "approval"}]
    assert [r.element_id for r in rows] == steps  # start and end are left out
    plan = rows[0]
    assert (plan.label, plan.kind, plan.state, plan.divergence_types) == (
        "Plan",
        "activity",
        "contested",
        ["threshold"],
    )
    assert (plan.sop, plan.interview, plan.jd, plan.artefact) == (
        "supports",
        "contradicts",
        "silent",
        "not_applicable",
    )


def test_silence_is_never_shown_as_contradiction() -> None:
    graph = replace(
        clean(),
        "plan",
        source_state="practiced_only",
        evidence=[said("interview_transcript", "supports", "i"), said("sop", "silent")],
    )
    row = alignment.alignment_matrix(graph)[0]
    assert (row.interview, row.sop, row.state) == ("supports", "silent", "practiced_only")


def test_rejected_steps_are_left_out_and_recommended_steps_are_not_assessed() -> None:
    graph = replace(clean(), "plan", review_status="rejected")
    graph.elements.append(
        element(
            "benchmark",
            "activity",
            provenance="R",
            r_reference="IATA AHM 560",
            source_state="not_assessed",
            evidence=[said("sop", "silent")],
        )
    )
    rows = {r.element_id: r for r in alignment.alignment_matrix(graph)}
    assert "plan" not in rows
    benchmark = rows["benchmark"]
    assert (benchmark.sop, benchmark.interview, benchmark.jd, benchmark.artefact) == (
        "not_applicable",
    ) * 4
    assert benchmark.state == "not_assessed"


def test_a_trace_contradiction_shows_in_the_artefact_column() -> None:
    graph = replace(
        clean(),
        "plan",
        source_state="trace_contradicted",
        evidence=[said("sop", "supports"), said("executed_artefact", "contradicts", "a")],
    )
    row = alignment.alignment_matrix(graph)[0]
    assert (row.sop, row.artefact, row.state) == ("supports", "contradicts", "trace_contradicted")


@pytest.mark.parametrize(
    ("interview", "official", "lived", "unclear", "expected"),
    [
        ("supports", 1, 2, 0, ("supports", "supports")),  # both accounts given
        ("supports", 0, 1, 1, ("silent", "supports")),  # only the lived account: official silent
        ("contradicts", 1, 0, 0, ("contradicts", "silent")),  # the stance goes to its account
        ("supports", 0, 0, 2, ("account_unclear", "account_unclear")),  # never guessed
        ("silent", 0, 0, 0, ("silent", "silent")),  # the interview doesn't mention the step
        ("not_applicable", 0, 0, 0, ("not_applicable", "not_applicable")),  # no interview at all
    ],
)
def test_the_sme_official_and_lived_layers_split_the_interview_by_account(
    interview: str, official: int, lived: int, unclear: int, expected: tuple[str, str]
) -> None:
    """P9u-2 (PRD §6.3 P9 four layers, §3.12.3): which account the interview gives of a step."""
    accounts = AccountSummary(official=official, lived=lived, unclear=unclear)
    found = (alignment.layer(interview, accounts, "official"),
             alignment.layer(interview, accounts, "lived"))  # fmt: skip
    assert found == expected


def test_each_row_carries_both_layers() -> None:
    graph = replace(clean(), "plan", evidence=[said("interview_transcript", "supports", "i")],
                    account_summary=AccountSummary(official=1, lived=0, unclear=0))  # fmt: skip
    plan = alignment.alignment_matrix(graph)[0]
    assert (plan.interview, plan.sme_official, plan.sme_lived) == ("supports", "supports", "silent")
