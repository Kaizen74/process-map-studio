"""Lane-boundary findings (API_CONTRACT.md → GET /versions/{vid}/lane-boundaries; PRD F.4 L5,
F.6 F1 and F4, criterion 76; C8): one Responsible kept, other teams Consulted with a note; gaps
between teams and boundary answers flagged; the follow-up question for each finding."""

from __future__ import annotations

from app.domain.result import Ok
from app.domain.sensemaking import BoundaryClaim, BoundaryStep, LaneBoundaryFinding
from app.services import boundaries
from app.services import interview_templates as templates


def step(label: str, lane: str, *claims: tuple[str, str, str]) -> BoundaryStep:
    return BoundaryStep(
        element_id=label.lower().replace(" ", "-"), label=label, lane_role=lane,
        claims=[BoundaryClaim(question_id=q, responsible=r, text=t) for q, r, t in claims],
    )  # fmt: skip


def test_shared_delivery_keeps_one_responsible_and_lists_the_others_as_consulted() -> None:
    found = boundaries.lane_boundaries([
        step("Load the hold", "Ramp", ("M2.4", "Ramp", "Ramp loads."),
             ("M2.4", "Load controller", "We stand there with them."),
             ("", "load controller", "Again."), ("", "Cargo", "Cargo hands over.")),
    ])  # fmt: skip
    assert len(found) == 1
    f = found[0]
    assert (f.kind, f.responsible, f.consulted) == (
        "shared_delivery", "Ramp", ["Load controller", "Cargo"])  # fmt: skip
    assert "One Responsible (Ramp)" in f.note and "Load controller, Cargo" in f.note
    assert f.question_ids == []


def test_a_step_one_team_does_gives_no_finding() -> None:
    steps = [
        step("Draft plan", "Load controller", ("M2.2", "Load controller", "I draft it."),
             ("", "", "It is drafted."), ("", "load controller", "Same.")),
        step("Approve", "Lead"),
    ]  # fmt: skip
    assert boundaries.lane_boundaries(steps) == []


def test_an_answer_saying_nobody_owns_it_is_a_gap_even_when_teams_share_it() -> None:
    found = boundaries.lane_boundaries([
        step("Chase the late bags", "Ramp",
             ("L5", "Ramp", "Honestly that falls between us and baggage."),
             ("M2.4", "Baggage", "Baggage helps.")),
        step("Close the file", "", ("F1", "", "No one really owns closing it.")),
    ])  # fmt: skip
    assert [(f.kind, f.responsible, f.question_ids) for f in found] == [
        ("gap", "Ramp", ["L5"]), ("gap", "", ["F1"])]  # fmt: skip
    assert "falls between teams" in found[0].note and found[0].consulted == ["Baggage"]
    assert "no role yet" in found[1].note


def test_gap_words_count_only_on_boundary_questions() -> None:
    found = boundaries.lane_boundaries([
        step("Check fuel", "Ramp", ("M2.4", "Ramp", "Nobody waits for fuel here.")),
    ])  # fmt: skip
    assert found == []


def test_a_boundary_answer_without_overlap_is_still_listed() -> None:
    found = boundaries.lane_boundaries([
        step("Hand over the plan", "Load controller",
             ("F4", "Load controller", "We hand it to ramp at the gate."),
             ("F4", "", "Again.")),
    ])  # fmt: skip
    assert [(f.kind, f.question_ids, f.consulted) for f in found] == [("boundary", ["F4"], [])]


def test_findings_keep_process_order() -> None:
    found = boundaries.lane_boundaries([
        step("First", "A", ("", "B", "x")),
        step("Middle", "A"),
        step("Last", "A", ("L5", "", "x")),
    ])  # fmt: skip
    assert [f.label for f in found] == ["First", "Last"]


def finding(kind: str, consulted: list[str], responsible: str = "Ramp") -> LaneBoundaryFinding:
    return LaneBoundaryFinding(
        element_id="e", label="Load the hold", kind=kind,  # type: ignore[arg-type]
        responsible=responsible, consulted=consulted, note="", question_ids=[],
    )  # fmt: skip


def test_follow_up_is_f4_for_shared_delivery_and_f1_otherwise() -> None:
    shared = finding("shared_delivery", ["Load controller"])
    assert boundaries.follow_up_question(shared) == (
        "F4", "On “Load the hold”, how does your team work with Ramp? "
        "It sounds like both show up together.")  # fmt: skip
    assert boundaries.follow_up_question(finding("gap", ["Baggage"]), "Ramp") == (
        "F1", "Going back to where we left off, could you help me separate the activities "
        "managed by Ramp versus Baggage?")  # fmt: skip
    qid, wording = boundaries.follow_up_question(finding("boundary", [], responsible=""))
    assert qid == "F1" and "your team versus the other teams" in wording


def test_the_other_team_is_never_the_interviewee_s_own() -> None:
    shared = finding("shared_delivery", ["Load controller"])
    assert "work with Load controller?" in boundaries.follow_up_question(shared, "Ramp")[1]
    assert "work with Ramp?" in boundaries.follow_up_question(shared, "load controller")[1]
    _, wording = boundaries.follow_up_question(finding("gap", ["Baggage"]), "Baggage")
    assert wording.endswith("managed by Baggage versus Ramp?")
    alone = finding("shared_delivery", ["Ramp"])  # only the interviewee's own team named
    assert boundaries.follow_up_question(alone, "Ramp")[0] == "F1"


def test_follow_up_wordings_are_the_question_banks() -> None:
    """F1 and F4 (F.6) keep the bank's own wording; only the placeholders are filled."""
    bank = templates.load_bank()
    assert isinstance(bank, Ok)
    f1, f4 = bank.value.question("F1").wording, bank.value.question("F4").wording
    assert f1.replace("[your team]", "{a}").replace("[other team]", "{b}") == boundaries.F1
    assert (f4.replace("[activity]", "\u201c{step}\u201d")
            .replace("[other role's team]", "{other}")) == boundaries.F4  # fmt: skip
