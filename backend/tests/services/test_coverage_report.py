"""The coverage report's rules (PRD §3.12.8; API_CONTRACT → GET /versions/{vid}/coverage), on the
sample map's As done view with hand-made interview claims and items: deterministic, no Claude."""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.graph import Graph
from app.domain.models import ClaimRecord
from app.services import interview_templates, sensemaking

SAMPLE = Path(__file__).resolve().parents[3] / "frontend" / "tests" / "fixtures" / "sample_map.json"


def done_view() -> Graph:
    graph = Graph.model_validate(json.loads(SAMPLE.read_text(encoding="utf-8"))["graph"])
    elements = [e for e in graph.elements if e.view_membership != "documented_only"]
    edges = [x for x in graph.edges if x.view_membership != "documented_only"]
    return graph.model_copy(update={"elements": elements, "edges": edges})


def key(graph: Graph, label: str) -> str:
    return next(e.stable_key for e in graph.elements if e.label == label)


def flow(claim_type: str, account: str = "lived", **payload: object) -> ClaimRecord:
    return ClaimRecord(source_id="s", stage="S1", claim_type=claim_type, payload=dict(payload),
                       segment_ids=["p"], quote="q", provenance="O", basis="",
                       verification_status="verified", account_type=account)  # fmt: skip


def item(claim_type: str, **payload: object) -> ClaimRecord:
    return flow(claim_type, **payload).model_copy(update={"account_type": None})


def wording() -> dict[str, str]:
    bank = interview_templates.load_bank()
    return {q.id: q.wording for q in bank.value.questions}  # type: ignore[union-attr]


def test_nothing_said_is_missing_one_mention_thin_two_covered() -> None:
    dims, _ = sensemaking.coverage_dimensions([], done_view())
    assert list(dims) == list(sensemaking.COVERAGE_QUESTIONS)  # every dimension, in order
    # The end point and the official-vs-lived contrast come from the map's interview evidence.
    from_map = {"end_point", "official_vs_lived"}
    assert {n: d.status for n, d in dims.items() if n not in from_map} == {
        n: "missing" for n in dims if n not in from_map
    }
    one, _ = sensemaking.coverage_dimensions([flow("kpi")], done_view())
    two, _ = sensemaking.coverage_dimensions([flow("kpi"), flow("kpi", "official")], done_view())
    assert (one["kpis"].status, two["kpis"].status, two["kpis"].evidence_count) == (
        "thin", "covered", 2)  # fmt: skip
    # Document claims (no account type) never count: coverage is what the interviews said.
    document = flow("kpi").model_copy(update={"account_type": None})
    assert sensemaking.coverage_dimensions([document], done_view())[0]["kpis"].status == "missing"


def test_what_each_dimension_counts() -> None:
    claims = [
        flow("decision", decider_role="Captain"),
        flow("activity", duration_text="forty minutes", variation_condition="On a busy wave"),
        flow("raci"),
        item("know_how", category="artefacts", about_steps=[]),
        item("know_how", category="heuristics", about_steps=[]),
        item("sme_term", term="wave"),
    ]
    dims, _ = sensemaking.coverage_dimensions(claims, done_view())
    counts = {n: d.evidence_count for n, d in dims.items()}
    assert (counts["decisions_and_criteria"], counts["raci"], counts["work_and_wait_time"],
            counts["exceptions"], counts["artefacts"], counts["sme_terms"]) == (
        1, 2, 1, 1, 1, 1)  # fmt: skip
    # The end point counts the interview passages on the steps that lead to an end.
    assert (dims["end_point"].status, dims["end_point"].note) == (
        "thin",
        "Heard for: Issue load sheet",
    )


def test_the_step_spine_stays_thin_while_an_order_is_not_stated() -> None:
    steps = [flow("activity"), flow("decision"), flow("approval")]
    dims, about = sensemaking.coverage_dimensions(steps, done_view())
    assert (dims["step_spine"].status, dims["step_spine"].evidence_count) == ("thin", 3)
    assert about["step_spine"] == [
        "Load and return LIR → Busy wave?; Read report at aircraft → Deviation in limits?"
    ]
    graph = done_view()
    edges = [x.model_copy(update={"sequence_basis": "explicit_order"}) for x in graph.edges]
    stated = graph.model_copy(update={"edges": edges})
    dims, about = sensemaking.coverage_dimensions(steps, stated)
    assert (dims["step_spine"].status, dims["step_spine"].note, about["step_spine"]) == (
        "covered", "", [""])  # fmt: skip


def test_know_how_at_each_decision_and_the_three_stories() -> None:
    graph = done_view()
    deciding = [e.label for e in graph.elements if e.kind in {"decision", "approval"}]
    assert deciding == ["Special loads OK?", "Busy wave?", "Deviation in limits?",
                        "Approve deviation"]  # fmt: skip
    all_known = [item("know_how", category="skills", about_steps=[key(graph, label)])
                 for label in deciding]  # fmt: skip
    told = [item("story", fragment_type=k) for k in ("went_well", "went_badly", "surprise")]
    dims, about = sensemaking.coverage_dimensions(all_known + told, graph)
    assert (dims["know_how"].status, dims["stories"].status) == ("covered", "covered")
    assert (about["know_how"], about["stories"]) == ([], [])
    dims, about = sensemaking.coverage_dimensions(all_known[:1] + told[2:], graph)
    assert (dims["know_how"].status, dims["know_how"].note) == (
        "thin", "No know-how yet: Busy wave?, Deviation in limits?, Approve deviation")  # fmt: skip
    assert (dims["stories"].status, about["stories"]) == ("thin", ["went_well", "went_badly"])


def test_official_and_lived_need_both_accounts_on_one_step() -> None:
    graph = done_view()
    dims, _ = sensemaking.coverage_dimensions([], graph)
    assert dims["official_vs_lived"].model_dump() == {  # the sample's 22:30 contrast
        "status": "covered", "evidence_count": 1,
        "note": "Both accounts on 1 step: Load and return LIR"}  # fmt: skip
    only_lived = graph.model_copy(update={"elements": [
        e.model_copy(update={"account_summary": e.account_summary.model_copy(
            update={"official": 0})}) for e in graph.elements]})  # fmt: skip
    dims, _ = sensemaking.coverage_dimensions([], only_lived)
    assert (dims["official_vs_lived"].status, dims["official_vs_lived"].note) == ("missing", "")


def test_follow_ups_are_bank_questions_word_for_word() -> None:
    graph = done_view()
    told = [item("story", fragment_type="went_badly")]
    dims, about = sensemaking.coverage_dimensions([*told, flow("kpi"), flow("kpi")], graph)
    asked = sensemaking.follow_up_questions(dims, about, wording())
    words = wording()
    assert all(q.question == words[q.question_id] for q in asked)
    assert "kpis" not in {q.dimension for q in asked}  # covered: nothing to ask
    assert [(q.question_id, q.about) for q in asked if q.dimension == "stories"] == [
        ("M5.1", ""), ("M5.3", "")]  # fmt: skip
    assert [q.about for q in asked if q.dimension == "know_how"] == [
        "Special loads OK?", "Busy wave?", "Deviation in limits?", "Approve deviation"]  # fmt: skip
    order = [list(sensemaking.COVERAGE_QUESTIONS).index(q.dimension) for q in asked]
    assert order == sorted(order)  # in dimension order
