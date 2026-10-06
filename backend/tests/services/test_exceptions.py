"""Exceptions, rework and workarounds (API_CONTRACT.md → GET /versions/{vid}/exceptions; X2):
the usual route, exception routes and variations told apart from the map's structure and the
SME's own words; rework loops; workarounds; the extra hand-overs; "how often?" questions."""

from __future__ import annotations

from app.domain.sensemaking import ExceptionEdgeInput, ExceptionReport, ExceptionStepInput
from app.services import exceptions

ASK = "How often does something like that happen?"


def s(key: str, kind: str = "activity", lane: str = "Load controller", **words: object
      ) -> ExceptionStepInput:  # fmt: skip
    return ExceptionStepInput(element_id=key, label=key, kind=kind, lane=lane, **words)  # type: ignore[arg-type]


def e(a: str, b: str, kind: str = "sequence", label: str = "") -> ExceptionEdgeInput:
    return ExceptionEdgeInput(from_id=a, to_id=b, kind=kind, label=label)


def run(steps: list[ExceptionStepInput], edges: list[ExceptionEdgeInput]) -> ExceptionReport:
    return exceptions.analyse(steps, edges, "done", ASK)


def routes(report: ExceptionReport) -> dict[str, str]:
    return {x.label: x.route for x in report.steps}


# The sample's As done view in miniature (A.5, A.9): two exception routes that loop back, one
# variation tied to "on a busy wave" with the SME's reason, and a hand-over line from another
# interview (Plan → Load) that must not make the special-loads check look skipped.
SAMPLE_STEPS = [
    s("Start", "start"),
    s("Plan"),
    s("Special OK?", "decision"),
    s("Resolve", lane="Airline ops"),
    s("Load", lane="Ramp"),
    s("Busy?", "decision"),
    s(
        "Read at aircraft",
        condition="on a busy wave",
        stated_reason="otherwise we'd miss the slot",
        practiced_only=True,
    ),
    s("In limits?", "decision"),
    s("Approve deviation", "approval", lane="Captain"),
    s("Issue"),
    s("End", "end"),
]
SAMPLE_EDGES = [
    e("Start", "Plan"),
    e("Special OK?", "Load", "yes", "Yes"),
    e("Special OK?", "Resolve", "no", "No"),
    e("Resolve", "Plan", "rework", "Re-plan"),
    e("Load", "Busy?"),
    e("Busy?", "Read at aircraft", "yes", "Yes"),
    e("Busy?", "In limits?", "no", "No"),
    e("Read at aircraft", "In limits?"),
    e("In limits?", "Issue", "yes", "Within limits"),
    e("In limits?", "Approve deviation", "no", "Outside limits"),
    e("Approve deviation", "Issue", "approve", "Accept"),
    e("Approve deviation", "Load", "rework", "Re-trim"),
    e("Issue", "End"),
    e("Plan", "Load"),  # the hand-over stitched from another interview, stored first
    e("Plan", "Special OK?"),
]


def test_the_usual_route_exception_routes_and_the_variation() -> None:
    report = run(SAMPLE_STEPS, SAMPLE_EDGES)
    assert routes(report) == {
        "Plan": "usual", "Special OK?": "usual", "Resolve": "exception", "Load": "usual",
        "Busy?": "usual", "Read at aircraft": "variation", "In limits?": "usual",
        "Approve deviation": "exception", "Issue": "usual",
    }  # fmt: skip
    summary = report.summary
    assert (summary.steps, summary.usual_steps, summary.exception_steps,
            summary.variation_steps, summary.off_usual_share) == (9, 6, 2, 1, 0.33)  # fmt: skip
    assert (summary.routes, summary.rework_loops, summary.workarounds) == (3, 2, 1)


def test_each_route_says_how_it_starts_where_it_goes_and_the_hand_overs_it_adds() -> None:
    report = run(SAMPLE_STEPS, SAMPLE_EDGES)
    seen = [(r.kind, r.from_label, r.condition, r.labels, r.lanes,
             [(x.kind, x.label, x.edge_label) for x in r.exits], r.handoffs)
            for r in report.routes]  # fmt: skip
    assert seen == [
        ("exception", "Special OK?", "No", ["Resolve"], ["Airline ops"],
         [("loops_back", "Plan", "Re-plan")], 2),
        ("variation", "Busy?", "on a busy wave", ["Read at aircraft"], ["Load controller"],
         [("rejoins", "In limits?", "")], 0),
        ("exception", "In limits?", "Outside limits", ["Approve deviation"], ["Captain"],
         [("rejoins", "Issue", "Accept"), ("loops_back", "Load", "Re-trim")], 2),
    ]  # fmt: skip
    assert report.summary.extra_handoffs == 4
    assert report.routes[1].stated_reason == "otherwise we'd miss the slot"
    assert [(x.from_label, x.to_label, x.label) for x in report.loops] == [
        ("Resolve", "Plan", "Re-plan"), ("Approve deviation", "Load", "Re-trim")]  # fmt: skip


def test_a_workaround_is_the_step_done_another_way_never_the_routing_call() -> None:
    steps = [*SAMPLE_STEPS]
    steps[5] = s("Busy?", "decision", stated_reason="otherwise we'd miss the slot",
                 practiced_only=True)  # fmt: skip
    report = run(steps, SAMPLE_EDGES)
    assert [(w.label, w.condition, w.stated_reason, w.basis) for w in report.workarounds] == [
        ("Read at aircraft", "on a busy wave", "otherwise we'd miss the slot", "stated_reason")
    ]
    assert {x.label for x in report.steps if x.workaround} == {"Read at aircraft"}


def test_a_workaround_story_or_a_practised_only_step_with_a_reason_is_a_workaround() -> None:
    steps = [
        s("Start", "start"), s("Plan", workaround_story=True, frequency="most nights"),
        s("Re-key report", stated_reason="the system is down at night", practiced_only=True),
        s("Check", stated_reason="it is the rule"),  # a reason on a documented usual step: not one
        s("End", "end"),
    ]  # fmt: skip
    edges = [e("Start", "Plan"), e("Plan", "Re-key report"), e("Re-key report", "Check"),
             e("Check", "End")]  # fmt: skip
    report = run(steps, edges)
    assert [(w.label, w.basis, w.frequency) for w in report.workarounds] == [
        ("Plan", "story", "most nights"), ("Re-key report", "stated_reason", "")]  # fmt: skip
    # Every step is on the usual route: a workaround can be the usual way of working.
    assert set(routes(report).values()) == {"usual"}
    assert [q.about for q in report.questions] == ["the workaround at Re-key report"]


def test_how_often_comes_from_the_sme_and_otherwise_becomes_a_question() -> None:
    steps = [*SAMPLE_STEPS]
    steps[3] = s("Resolve", lane="Airline ops", frequency="maybe once a month")
    report = run(steps, SAMPLE_EDGES)
    assert report.routes[0].frequency == "maybe once a month"
    assert report.summary.frequency_stated == 1
    assert [(q.question_id, q.wording, q.about) for q in report.questions] == [
        ("M5.s2", ASK, "Busy? → on a busy wave: Read at aircraft"),
        ("M5.s2", ASK, "In limits? → Outside limits: Approve deviation"),
    ]


def test_a_route_of_several_steps_across_lanes_that_ends_the_process() -> None:
    steps = [
        s("Start", "start"), s("Check", "decision"), s("Do"),
        s("Escalate", lane="Duty manager"), s("Cancel", lane="Airline ops"), s("End", "end"),
    ]  # fmt: skip
    edges = [e("Start", "Check"), e("Check", "Do", "yes", "Fine"), e("Do", "End"),
             e("Check", "Escalate", "exception", ""), e("Escalate", "Cancel"),
             e("Cancel", "End")]  # fmt: skip
    report = run(steps, edges)
    route = report.routes[0]
    assert (route.condition, route.labels, route.lanes) == (
        "Exception", ["Escalate", "Cancel"], ["Duty manager", "Airline ops"])  # fmt: skip
    assert [(x.kind, x.label) for x in route.exits] == [("ends", "End")]
    assert route.handoffs == 2  # into the duty manager's lane, then to airline ops


def test_a_reject_line_forward_is_an_exception_route_and_backward_a_loop() -> None:
    steps = [s("Start", "start"), s("Draft"), s("Approve", "approval", lane="Lead"),
             s("Return to requester"), s("Issue"), s("End", "end")]  # fmt: skip
    forward = [e("Start", "Draft"), e("Draft", "Approve"), e("Approve", "Issue", "approve"),
               e("Approve", "Return to requester", "reject", "Reject"),
               e("Return to requester", "End"), e("Issue", "End")]  # fmt: skip
    report = run(steps, forward)
    assert routes(report)["Return to requester"] == "exception" and report.loops == []
    back = [*forward[:4], e("Approve", "Draft", "reject", "Rework"), forward[5]]
    report = run(steps, back)
    assert [(x.from_label, x.to_label) for x in report.loops] == [("Approve", "Draft")]


def test_an_empty_map_and_a_map_with_one_route_only() -> None:
    empty = run([s("Start", "start"), s("End", "end")], [e("Start", "End")])
    assert empty.summary.steps == 0 and empty.summary.off_usual_share == 0.0
    assert empty.routes == [] and empty.questions == []
    straight = run([s("Start", "start"), s("Do"), s("End", "end")],
                   [e("Start", "Do"), e("Do", "End")])  # fmt: skip
    assert straight.summary.usual_steps == 1 and straight.routes == []


def test_lines_to_unknown_or_rejected_steps_are_ignored_and_cycles_end() -> None:
    steps = [s("Start", "start"), s("A"), s("B"), s("End", "end")]
    edges = [e("Start", "A"), e("A", "B"), e("B", "A"), e("B", "End"), e("A", "gone")]
    report = run(steps, edges)
    assert routes(report) == {"A": "usual", "B": "usual"}
