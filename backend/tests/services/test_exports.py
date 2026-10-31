"""Export renderers (PRD §7.3, constraints 9-11), on the sample map's graph (the G1 baseline):
the fixed three-section template, provenance on every element line, role names only, no quotes,
no images, rejected steps left out."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from app.domain.exports import (
    ExportCause,
    ExportGapReport,
    ExportInput,
    ExportQuestion,
    SourceEntry,
)
from app.domain.graph import Graph
from app.domain.quality import QualityCard, QualityCheck
from app.services import exports, views

ROOT = Path(__file__).resolve().parents[3]
G1 = ROOT / "backend" / "tests" / "golden" / "G1_graph.json"
SAMPLE = ROOT / "frontend" / "tests" / "fixtures" / "sample_map.json"


def sample_graph() -> Graph:
    # The map as the exports read it (both views' steps, without the lines added for one view).
    return views.combined(Graph.model_validate(json.loads(G1.read_text(encoding="utf-8"))))


def card(green: bool = True) -> QualityCard:
    checks = [
        QualityCheck(id="Q1", name="Provenance green", status="pass", hard=True,
                     detail="All 8 steps tagged."),
        QualityCheck(id="Q10", name="60-minute validatable", status="warning", hard=False,
                     detail="8 steps, 5 lanes."),
    ]  # fmt: skip
    return QualityCard(checks=checks, warnings=["2 steps have no time."], all_green=green)


def data(graph: Graph | None = None, **changes: object) -> ExportInput:
    base = ExportInput(
        graph=graph or sample_graph(),
        sources=[
            SourceEntry(id="id-13", name="interview_transcript.txt", kind="interview_transcript",
                        version_date="", owner="", controlled_copy=False),
            SourceEntry(id="id-15", name="sop_LC-07.docx", kind="sop", version_date="2025-03-01",
                        owner="Load control office", controlled_copy=True),
        ],
        published_at="2026-09-28T09:15:00+00:00",
        validated_by="Eric Yim",
        open_questions=[
            ExportQuestion(question="Who approves a deviation?", phase_name="Close out",
                           element_label="Deviation in limits?", reason="contested"),
            ExportQuestion(question="What if the aircraft changes?", phase_name="",
                           element_label="", reason="gap"),
        ],
        quality_card=card(),
    )  # fmt: skip
    return base.model_copy(update=changes)


def test_the_master_map_follows_the_fixed_template() -> None:
    md = exports.render_master_map_md(data())
    assert md.startswith(
        "# Load control — Master Process Map\n\nVersion v0.1 · published 28 Sep 2026"
    )
    assert "validated by Eric Yim" in md.splitlines()[2]
    headings = [line for line in md.splitlines() if line.startswith("## ")]
    assert headings == [exports.FACTS, exports.INTERPRETATION, exports.RECOMMENDATION]
    assert "| Q1 Provenance green | Pass | All 8 steps tagged. |" in md
    assert "All hard checks green: yes." in md and "- 2 steps have no time." in md


def test_facts_list_sources_pain_points_and_source_states_without_quotes() -> None:
    md = exports.render_master_map_md(data())
    facts = md.split(exports.FACTS)[1].split(exports.INTERPRETATION)[0]
    assert "| sop_LC-07.docx | SOP | 2025-03-01 | Load control office | Yes |" in facts
    assert "| interview_transcript.txt | Interview | — | — | No |" in facts
    pains = [line for line in facts.splitlines() if line.startswith("- [O] ")]
    # The four observed constraints of the sample and the weakness the Ramp duty manager names
    # (A.10, C3: the paper loading report gets lost or arrives late).
    assert len(pains) == 5
    assert all("(step: " in line and "interview_transcript.txt" in line for line in pains[:1])
    assert "| Contested | 2 |" in facts and "| Corroborated | 3 |" in facts


def test_no_verbatim_passage_reaches_any_export() -> None:
    passages = [
        s["text"]
        for page in json.loads(SAMPLE.read_text(encoding="utf-8"))["segments"].values()
        for s in page["segments"]
        if len(s["text"]) > 40
    ]
    assert passages
    for text in (exports.render_master_map_md(data()), exports.render_graph_json(data()),
                 exports.render_raci_csv(data())):  # fmt: skip
        assert not [p for p in passages if p in text]


def test_every_element_line_carries_its_provenance() -> None:
    md = exports.render_master_map_md(data())
    interpretation = md.split(exports.INTERPRETATION)[1].split("### RACI")[0]
    table_rows = [
        line for line in interpretation.splitlines() if line.startswith("| ") and "---" not in line
    ]
    step_rows = [row for row in table_rows if not row.startswith("| Step |")]
    assert len(step_rows) == 5  # the sample's activities (v1.10 A.5: + Read report at aircraft)
    assert all("| [O] |" in row for row in step_rows)
    decisions = [line for line in interpretation.splitlines() if line.startswith("- ")]
    # v1.10 A.5: + Busy wave?
    assert len(decisions) == 5 and all(line.startswith("- [O] ") for line in decisions)
    assert "- [O] Special loads OK? (decision, rule-based, decider: Load controller). Exits: " in md


def test_decisions_list_every_labelled_exit_and_raci_marks_a_contest() -> None:
    md = exports.render_master_map_md(data())
    deviation = next(
        line for line in md.splitlines() if line.startswith("- [O] Deviation in limits?")
    )
    assert (
        "Within limits → Issue load sheet" in deviation
        and "Outside limits → Approve deviation" in deviation
    )
    raci = md.split("### RACI")[1].split("### Divergences")[0]
    assert "| Step | Load controller | Load control lead | Ramp | Airline ops | Captain |" in raci
    row = next(line for line in raci.splitlines() if "Deviation in limits?" in line)
    assert row == "| [O] Deviation in limits? | R | A? | · | · | A? |"
    assert (
        "| Threshold | Load and return LIR |" in md and "| Ownership | Deviation in limits? |" in md
    )


def test_recommendation_holds_flags_risks_external_practice_and_questions() -> None:
    graph = sample_graph()
    graph.elements[2].provenance = "R"
    graph.elements[2].r_reference = "IATA AHM 590"
    md = exports.render_master_map_md(data(graph))
    recommendation = md.split(exports.RECOMMENDATION)[1]
    assert recommendation.count("- Component: ") == 3
    assert "- Basis: Rule-based: an automation candidate" in recommendation
    assert "- [O] Draft load plan: Widebody plans rely on" in recommendation
    assert "- [R] Approve load plan: IATA AHM 590" in recommendation
    assert (
        "1. Who approves a deviation? (step: Deviation in limits? · Close out) · contested"
        in recommendation
    )
    assert "2. What if the aircraft changes? · gap" in recommendation
    # Recommendation-type content appears only in section 3 (the quality card's Q7).
    before = md.split(exports.RECOMMENDATION)[0]
    assert "- Component: " not in before and "IATA AHM 590" not in before


def test_rejected_steps_and_their_lines_are_left_out_everywhere() -> None:
    graph = sample_graph()
    issue = next(e for e in graph.elements if e.label == "Issue load sheet")
    issue.review_status = "rejected"
    md = exports.render_master_map_md(data(graph))
    assert "Issue load sheet" not in md
    rendered = json.loads(exports.render_graph_json(data(graph)))
    assert issue.id not in {e["id"] for e in rendered["elements"]}
    assert all(issue.id not in (e["from"], e["to"]) for e in rendered["edges"])
    assert "Issue load sheet" not in exports.render_raci_csv(data(graph))


def test_graph_json_carries_the_quality_card() -> None:
    rendered = json.loads(exports.render_graph_json(data()))
    assert rendered["version"]["quality_card"]["all_green"] is True
    assert rendered["elements"][1]["handoff"].keys() == {"in", "out"}
    assert (
        json.loads(exports.render_graph_json(data(quality_card=None)))["version"]["quality_card"]
        is None
    )


def test_raci_csv_is_steps_by_roles() -> None:
    text = exports.render_raci_csv(data())
    assert text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(text.removeprefix("﻿"))))
    assert rows[0] == ["Step", "Kind", "Lane", "Provenance", "Load controller", "Load control lead",
                       "Ramp", "Airline ops", "Captain"]  # fmt: skip
    assert len(rows) == 11  # header + 10 steps (v1.10 A.5); start and end are not steps
    assert {row[1] for row in rows[1:]} == {"Activity", "Decision", "Approval"}
    assert rows[8] == [  # after Busy wave? and Read report at aircraft (v1.10 A.5)
        "Deviation in limits?",
        "Decision",  # Eric, 2026-10-30: the words the HTML map uses, not the stored value
        "Load controller",
        "O",
        "R",
        "A?",
        "",
        "",
        "A?",
    ]


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"published_at": ""}, "Version v0.1 · not published yet · validated by Eric Yim"),
        ({"validated_by": ""}, "validated by not recorded"),
        ({"quality_card": None}, "Quality card: not worked out yet."),
        ({"open_questions": []}, "No open questions."),
    ],
)
def test_missing_facts_are_said_plainly(changes: dict[str, object], expected: str) -> None:
    assert expected in exports.render_master_map_md(data(**changes))


def test_a_map_without_pain_points_flags_or_divergences_says_so() -> None:
    graph = sample_graph()
    for e in graph.elements:
        e.constraints, e.ai_flag, e.k_risk, e.divergence_types = [], None, "", []
    md = exports.render_master_map_md(data(graph))
    said = ["None stated in the sources.", "No AI flags.", "No knowledge risks recorded.",
            "No steps from external practice.", "No divergences between the sources."]  # fmt: skip
    for line in said:
        assert line in md


def test_section_3_lists_pending_causes_and_finalised_gap_reports() -> None:
    """PRD §7.3: cause library entries (pending validation) and gap analyses (finalised only)."""
    causes = [
        ExportCause(element_label="Load and return LIR", divergence_type="threshold",
                    pattern="Threshold divergence: 10 min in the SOP vs up to 15 min in practice.",
                    inferred_cause=""),
        ExportCause(element_label="Deviation in limits?", divergence_type="ownership",
                    pattern="The sources disagree about “Deviation in limits?”.",
                    inferred_cause="Airline contracts set the tolerance."),
    ]  # fmt: skip
    reports = [
        ExportGapReport(mode="internal", finalised_at="2026-09-28T10:00:00+00:00",
                        accepted=["Offload resolution is undocumented work", "Plan approval"]),
    ]  # fmt: skip
    md = exports.render_master_map_md(data(causes=causes, gap_reports=reports))
    recommendation = md.split(exports.RECOMMENDATION)[1]
    assert (
        "- [O] Load and return LIR · threshold: Threshold divergence: 10 min in the SOP vs up to "
        "15 min in practice. Likely cause: not known yet: ask your SMEs." in recommendation
    )
    assert (
        "- [O] Deviation in limits? · ownership: The sources disagree about “Deviation in "
        "limits?”. [I] Likely cause: Airline contracts set the tolerance." in recommendation
    )
    assert (
        "- Documents vs practice · finalised 28 Sep 2026 · 2 accepted findings: Offload "
        "resolution is undocumented work; Plan approval" in recommendation
    )
    assert "No cause library entries yet." not in md and "No finalised gap analyses." not in md
    empty = exports.render_master_map_md(data())
    assert "No cause library entries yet." in empty and "No finalised gap analyses." in empty


def test_the_exports_state_the_signal_strength() -> None:
    # P12: a map made from interviews alone says so in its header (md and html).
    strong = exports.render_master_map_md(data())
    assert (
        "\nSignal strength: Strong (3 of 3). Built from interviews and a written procedure"
        in strong
    )
    interview = data().sources[:1]
    limited = exports.render_master_map_md(data(sources=interview))
    assert "\nSignal strength: Limited (1 of 3). Built from interviews only." in limited
    assert "Signal strength" not in exports.render_master_map_md(data(sources=[]))


# --- §7.3 v1.10-1.11 content (K3, 2026-10-06) ----------------------------------------------------


def sensemaking_data() -> ExportInput:
    from app.domain.exports import (
        ExportCapability,
        ExportKnowHow,
        ExportRealityGap,
        ExportStory,
        ExportTerm,
    )

    every = Graph.model_validate(json.loads(G1.read_text(encoding="utf-8")))
    graph = views.combined(every)
    deviation = next(e for e in graph.elements if e.label == "Deviation in limits?")
    return data(
        graph,
        view_graphs={v: views.view_graph(every, v) for v in views.VIEWS},
        stories=[ExportStory(label="Had to re-trim three flights in one night",
                             fragment_type="went_badly", steps=["Deviation in limits?"],
                             where="interview_transcript.txt 24:10")],
        capabilities=[
            ExportCapability(kind="strength", dimension="skillset",
                             text="Supervisors know the aircraft types.", steps=[]),
            ExportCapability(kind="weakness", dimension="systems",
                             text="The paper report gets lost.", steps=["Load and return LIR"]),
        ],
        glossary=[ExportTerm(term="wave", plain_meaning="A busy period.", steps=["Busy wave?"])],
        know_how=[ExportKnowHow(element_id=deviation.id, knowledge_risk="high",
                                dominant="heuristics")],
        reality_gaps=[ExportRealityGap(gap_class="effective_adaptation",
                                       title="The report is read at the aircraft",
                                       stated_reason="the paper sheet arrives late")],
    )  # fmt: skip


def section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def test_the_master_map_carries_the_v1_11_template() -> None:
    md = exports.render_master_map_md(sensemaking_data())
    facts = section(md, exports.FACTS, exports.INTERPRETATION)
    interpretation = section(md, exports.INTERPRETATION, exports.RECOMMENDATION)
    recommendation = md.split(exports.RECOMMENDATION, 1)[1]
    assert "- [O] Had to re-trim three flights in one night (went badly · " in facts
    assert "### Strengths as stated (preserve)" in facts
    assert "- [O] Skillset: Supervisors know the aircraft types." in facts
    assert "| Step | View | Lane |" in interpretation
    assert "| Read report at aircraft | as done |" in interpretation
    assert "- As done: 9 steps; only here: " in interpretation
    assert "- As documented: 6 steps; only here: Approve load plan." in interpretation
    assert "| [O] Deviation in limits? | Complex (proposed) | high · heuristics |" in interpretation
    assert (
        "### Official vs lived" in interpretation and "### Glossary of SME terms" in interpretation
    )
    assert "- wave: A busy period. (step: Busy wave?)" in interpretation
    assert recommendation.index("### Preserve / Improve") < recommendation.index("### AI flags")
    assert "- Systems: improve: The paper report gets lost." in recommendation
    assert ("- [I] Effective adaptation: The report is read at the aircraft "
            "(stated reason: the paper sheet arrives late)") in recommendation  # fmt: skip
    assert recommendation.count("Not used in this engagement.") == 2  # decision A: modules off
    assert "Preserve / Improve" not in facts + interpretation  # recommendations stay in section 3


def test_every_new_heading_is_printed_even_when_empty() -> None:
    md = exports.render_master_map_md(data())
    for heading in ("### Stories", "### Strengths as stated (preserve)",
                    "### Two views: as done and as documented", "### Work type and know-how",
                    "### Official vs lived", "### Glossary of SME terms", "### Preserve / Improve",
                    "### Reality gaps by gap class", "### Disposition and value",
                    "### System records"):  # fmt: skip
        assert md.count(heading) == 1, heading
    assert "No stories recorded." in md and "No SME terms recorded." in md
    assert "This map was drafted before the two views; it has one view." in md


def test_facts_say_how_much_of_the_sources_is_about_other_flows() -> None:
    # Eric, 2026-10-30: someone reading only the download should know the documents also describe
    # other flows (DECISIONS 81, 83). One line under the source registry, counts only, no quotes.
    text = exports.render_master_map_md(data(outside_flow_claims=6, outside_flow_questions=1))
    facts = text[text.index(exports.FACTS) : text.index("### Pain points as stated")]
    line = ("6 claims and 1 question in these sources are about another flow, so they are kept "
            "off this map.")  # fmt: skip
    assert line in facts
    one = exports.render_master_map_md(data(outside_flow_claims=1))
    assert "1 claim in these sources is about another flow, so it is kept off this map." in one
    assert "another flow" not in exports.render_master_map_md(data())
