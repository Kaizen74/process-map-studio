"""The publish quality card (PRD §7.2): each check turns red on a crafted fixture and green on the
fully reviewed sample; Q10-Q12 are only warnings (Q12 only with system records); a failing detail
never repeats a hidden name."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from app.domain.graph import Graph, GraphAiFlag, LintIssue, LintReport
from app.domain.quality import QualityInput
from app.services import export_html, quality, signal
from app.services import exports as renderers
from tests.services.test_export_html import FONTS, TOKENS
from tests.services.test_exports import data, sample_graph

HIDDEN = ["Priya Nair"]


def reviewed() -> Graph:
    graph = sample_graph()
    for e in graph.elements:
        e.review_status = "confirmed"
    return graph


def rendered(graph: Graph) -> dict[str, str]:
    inp = data(graph, quality_card=None)
    return {
        "md": renderers.render_master_map_md(inp),
        "json": renderers.render_graph_json(inp),
        "csv": renderers.render_raci_csv(inp),
        "html": export_html.render_map_html(inp, TOKENS, FONTS),
    }


def card_input(graph: Graph | None = None, **changes: object) -> QualityInput:
    graph = graph or reviewed()
    base = QualityInput(
        graph=graph,
        lint=LintReport(failures=[], warnings=[]),
        pending_merges=0,
        open_image_suggestions=0,
        unverified_claims=0,
        exports=rendered(graph),
        hidden_terms=HIDDEN,
    )
    return base.model_copy(update=changes)


def statuses(inp: QualityInput) -> dict[str, str]:
    return {c.id: c.status for c in quality.build_quality_card(inp).checks}


def test_the_reviewed_sample_is_green() -> None:
    card = quality.build_quality_card(card_input())
    # Requirement change 2026-10-06 (PRD v1.10-1.11 §7.2, K3): Q11 joins the card as a warning;
    # Q12 only when system records are used. The sample's work types are still proposed.
    assert [c.id for c in card.checks] == [f"Q{n}" for n in range(1, 12)]
    assert all(c.status == "pass" for c in card.checks if c.id != "Q11"), card.checks
    assert (card.checks[10].status, card.checks[10].hard) == ("warning", False)
    assert card.all_green and quality.hard_failures(card) == 0
    assert card.checks[0].detail == "All 10 steps are tagged O, I or R."  # v1.10 A.5
    assert card.checks[9].detail == "10 steps and 5 lanes: fits a one-hour session."


def _untagged(g: Graph) -> None:
    g.elements[1].provenance = ""


def _unreferenced(g: Graph) -> None:
    g.elements[1].provenance = "R"


def _no_passage(g: Graph) -> None:
    g.elements[1].evidence = []


def _unreviewed(g: Graph) -> None:
    g.elements[2].review_status = "draft"


def _hidden_name(g: Graph) -> None:
    g.elements[1].kpi = "Signed off by Priya Nair"


def _image(g: Graph) -> None:
    g.elements[1].kpi = "See ramp_photo.png"


def _flag_on_judgment(g: Graph) -> None:
    g.elements[6].ai_flag = GraphAiFlag(component="reasoning", input="a", output="b", handoff="c",
                                        basis="rule_based_automate_candidate")  # fmt: skip


def lint(rule: str) -> LintReport:
    return LintReport(failures=[LintIssue(rule=rule, element_id=None, message=f"{rule} broken.")],
                      warnings=[])  # fmt: skip


@pytest.mark.parametrize(
    ("check", "change_graph", "changes"),
    [
        ("Q1", _untagged, {}),
        ("Q1", _unreferenced, {}),
        ("Q2", _no_passage, {}),
        ("Q2", None, {"unverified_claims": 2}),
        ("Q3", None, {"lint": lint("L4")}),
        ("Q3", None, {"lint": lint("L5")}),
        ("Q4", None, {"lint": lint("L6")}),
        ("Q4", None, {"lint": lint("L9")}),
        ("Q4", None, {"lint": lint("L11")}),
        ("Q5", None, {"lint": lint("L10")}),
        ("Q6", _unreviewed, {}),
        ("Q6", None, {"pending_merges": 1}),
        ("Q6", None, {"open_image_suggestions": 1}),
        ("Q8", _hidden_name, {}),
        ("Q9", _image, {}),
    ],
)
def test_each_hard_check_turns_red_on_its_fixture(
    check: str, change_graph: Callable[[Graph], None] | None, changes: dict[str, object]
) -> None:
    graph = reviewed()
    if change_graph:
        change_graph(graph)
    inp = card_input(graph, **changes)
    card = quality.build_quality_card(inp)
    failing = [c.id for c in card.checks if c.status == "fail"]
    assert check in failing
    assert not card.all_green


def test_lint_l10_is_what_q5_reads() -> None:
    graph = reviewed()
    _flag_on_judgment(graph)  # the lint rules catch it (L10); the card reports their verdict
    assert statuses(card_input(graph))["Q5"] == "pass"
    assert statuses(card_input(graph, lint=lint("L10")))["Q5"] == "fail"


def test_q7_catches_mixed_sections() -> None:
    inp = card_input()
    mixed = inp.exports["md"].replace(renderers.RECOMMENDATION, "## 3. Other")
    assert (
        statuses(inp.model_copy(update={"exports": {**inp.exports, "md": mixed}}))["Q7"] == "fail"
    )
    moved = inp.exports["md"].replace(renderers.FACTS, renderers.FACTS + "\n- Component: Action")
    card = quality.build_quality_card(
        inp.model_copy(update={"exports": {**inp.exports, "md": moved}})
    )
    assert card.checks[6].status == "fail"
    assert card.checks[6].detail == "The Master Process Map mix the three sections."
    html = inp.exports["html"].replace('aria-labelledby="facts"', 'aria-labelledby="intro"')
    assert (
        statuses(inp.model_copy(update={"exports": {**inp.exports, "html": html}}))["Q7"] == "fail"
    )


def test_the_hidden_name_is_never_repeated_in_the_card() -> None:
    graph = reviewed()
    _hidden_name(graph)
    card = quality.build_quality_card(card_input(graph))
    q8 = card.checks[7]
    assert q8.status == "fail"  # the KPI is in the JSON and HTML exports (not in the md template)
    assert "in the json, html export" in q8.detail
    assert "Priya" not in card.model_dump_json()
    # Eric, 2026-10-30: the card travels in the exports others read, so "the list", not "your".
    assert q8.detail.startswith("A name from the list of names to hide appears")


def test_q8_speaks_of_the_list_not_yours_in_a_shared_export() -> None:
    q8 = quality.build_quality_card(card_input(reviewed())).checks[7]
    assert q8.status == "pass"
    assert q8.detail == "No name from the list of names to hide appears in any export."


def test_q10_is_a_warning_and_never_blocks() -> None:
    graph = reviewed()
    for e in graph.elements[1:11]:
        e.lane_role_id = f"lane-{e.id}"  # 10 lanes (v1.10 A.5: ten steps)
    card = quality.build_quality_card(card_input(graph))
    q10 = card.checks[9]
    assert (q10.status, q10.hard) == ("warning", False)
    assert q10.detail == "10 steps and 10 lanes: consider splitting by phase."
    assert card.checks[9] not in [c for c in card.checks if c.status == "fail"]


def test_rejected_steps_count_for_nothing_and_warnings_come_from_lint() -> None:
    graph = reviewed()
    graph.elements[2].review_status = "rejected"
    graph.elements[2].provenance = ""  # would fail Q1 if it were on the map
    note = LintIssue(rule="L12", element_id=None, message="2 steps have no time.")
    warnings = LintReport(failures=[], warnings=[note])
    card = quality.build_quality_card(card_input(graph, lint=warnings))
    assert card.all_green
    assert card.warnings == ["2 steps have no time."]


def test_an_interview_only_map_gets_a_warning_never_a_blocker() -> None:
    limited = quality.build_quality_card(card_input(source_kinds=["interview_transcript"]))
    assert quality.SIGNAL_WARNING in limited.warnings and limited.all_green
    strong = quality.build_quality_card(card_input(source_kinds=["interview_transcript", "sop"]))
    assert quality.SIGNAL_WARNING not in strong.warnings


def test_a_documents_only_map_gets_its_own_warning_never_a_blocker() -> None:
    """Eric, 2026-10-20: drafted from documents alone, the map shows the process as written."""
    card = quality.build_quality_card(card_input(source_kinds=["sop", "job_description"]))
    assert card.all_green and quality.SIGNAL_WARNING not in card.warnings
    assert signal.DOCUMENTS_QUALITY_WARNING in card.warnings


def test_more_than_three_names_end_with_how_many_more() -> None:
    """Bug found 2026-10-06 (Q11 on the sample): "and 2 mores" instead of "and 2 more"."""
    graph = sample_graph()
    steps = [e for e in graph.elements if e.kind in renderers.STEP_KINDS][:5]
    text = quality._names(steps)
    assert text.endswith(" and 2 more"), text


def test_q11_warns_until_every_decision_point_has_a_confirmed_work_type() -> None:
    graph = reviewed()
    deciding = [e for e in graph.elements if e.kind in ("decision", "approval")]
    assert deciding and any(e.work_type for e in graph.elements)  # a v1.10 sample
    card = quality.build_quality_card(card_input(graph))
    q11 = card.checks[10]
    assert q11.detail.startswith(f"{len(deciding)} decisions, approvals or judgment steps "
                                 "without a confirmed work type: ")  # fmt: skip
    for e in deciding:
        e.work_type_status = "confirmed"
    assert statuses(card_input(graph))["Q11"] == "pass"
    # A map drafted before v1.10 has no work types: nothing to confirm.
    for e in graph.elements:
        e.work_type, e.work_type_status = None, None
    assert statuses(card_input(graph))["Q11"] == "pass"
    assert card.all_green  # a warning never blocks publishing


def test_q12_is_on_the_card_only_with_system_records() -> None:
    assert "Q12" not in statuses(card_input())
    assert statuses(card_input(unaligned_activities=0))["Q12"] == "pass"
    card = quality.build_quality_card(card_input(unaligned_activities=2))
    q12 = card.checks[-1]
    assert (q12.id, q12.status, q12.hard) == ("Q12", "warning", False)
    assert q12.detail == "2 system activities not yet aligned to a step or marked hidden work."
    assert card.all_green
