"""Rule 9 of §3.12.10 and rule 10 of §3.9 (K2, 2026-10-06): landscape and practice levels.

Decision C (Eric, 2026-10-06): proved with a crafted case, because fixture A.10 has no landscape
activity. A Landscape interview (L2) names the team-level activity "Manage loading" in the Ramp
lane; a Practice interview describes "Load the aircraft" and "Return the loading report" in the
same lane and phase. The practice steps nest under the landscape activity, the map draws the
finest level, and nothing is duplicated.
"""

from __future__ import annotations

from app.domain.graph import Graph, GraphElement
from app.domain.sensemaking import StepPosition, TranslationStep
from app.services import layout, translation, views
from tests.services.test_lint import CAPTAIN, LC, clean, edge, element

RAMP = CAPTAIN  # a second lane of the crafted map


def step(key: str, *questions: str, kind: str = "activity", lane: str = RAMP, phase: str = "p1",
         documents: bool = False) -> TranslationStep:  # fmt: skip
    return TranslationStep(
        id=key, kind=kind, label=key.replace("_", " ").capitalize(), source_state="corroborated",
        provenance="O", lane=lane, phase=phase,
        interview=[StepPosition(source_id="s", seq=i, question_ids=[q])
                   for i, q in enumerate(questions)],
        documents=[StepPosition(source_id="sop", seq=1)] if documents else [],
    )  # fmt: skip


def test_landscape_answers_make_a_landscape_activity_and_practice_steps_nest_under_it() -> None:
    steps = [
        step("manage_loading", "L2"),
        step("load_the_aircraft", "M2.2"),
        step("return_the_loading_report", "M2.2", "L3"),  # one practice answer is enough
        step("plan_the_load", "M2.2", lane=LC),  # another lane: no parent
        step("check_the_sheet", "M3.2", phase="p2"),  # another phase: no parent
    ]
    assert translation.levels(steps) == {
        "manage_loading": ("landscape", None),
        "load_the_aircraft": ("practice", "manage_loading"),
        "return_the_loading_report": ("practice", "manage_loading"),
        "plan_the_load": ("practice", None),
        "check_the_sheet": ("practice", None),
    }


def test_one_level_maps_keep_no_level_and_documents_are_never_landscape() -> None:
    assert translation.levels([step("a", "M2.2"), step("b", "M4.1")]) == {
        "a": (None, None),
        "b": (None, None),
    }
    # A step a document also describes, or with an unmatched answer, is not landscape.
    assert translation.levels([step("a", "L2", documents=True)]) == {"a": (None, None)}
    unmatched = step("a", "L2").model_copy(
        update={"interview": [StepPosition(source_id="s", seq=1)]}
    )
    assert translation.levels([unmatched]) == {"a": (None, None)}


def test_with_two_landscape_activities_the_closer_label_wins_and_a_tie_nests_nowhere() -> None:
    steps = [
        step("manage_loading", "L2"),
        step("manage_catering", "L2"),
        step("check_loading_weights", "M2.2"),
        step("walk_the_ramp", "M2.2"),
    ]
    result = translation.levels(steps)
    assert result["check_loading_weights"] == ("practice", "manage_loading")
    assert result["walk_the_ramp"] == ("practice", None)


def nested_graph() -> Graph:
    """start → manage (landscape) → end, with load → report under manage."""
    graph = clean()
    start, end = graph.elements[0], graph.elements[-1]
    manage = element("manage", "activity", lane_role_id=RAMP, level="landscape")
    load = element("load", "activity", lane_role_id=RAMP, level="practice",
                   parent_element_id="manage")  # fmt: skip
    report = element("report", "activity", lane_role_id=RAMP, level="practice",
                     parent_element_id="manage")  # fmt: skip
    elements: list[GraphElement] = [start, manage, load, report, end]
    edges = [edge("start", "manage"), edge("manage", "end"), edge("load", "report")]
    return graph.model_copy(update={"elements": elements, "edges": edges})


def test_the_map_draws_the_finest_level_and_rejoins_the_flow() -> None:
    graph = nested_graph()
    drawn = views.finest_level(graph)
    assert [e.id for e in drawn.elements] == ["start", "load", "report", "end"]
    assert [(e.from_, e.to) for e in drawn.edges] == [
        ("start", "load"),  # the line into "manage" now starts its own flow
        ("report", "end"),  # and the line out leaves from where it ends
        ("load", "report"),
    ]
    boxes = {n.id for n in layout.compute_layout(drawn).nodes}
    assert "manage" not in boxes and {"load", "report"} <= boxes  # no duplicated activity
    # Each view draws the finest level too (the per-view graph, layout and flow checks).
    assert "manage" not in {e.id for e in views.view_graph(graph, "done").elements}


def test_a_landscape_activity_without_practice_steps_is_drawn_as_usual() -> None:
    graph = nested_graph()
    loose = [e.model_copy(update={"parent_element_id": None}) for e in graph.elements]
    alone = graph.model_copy(update={"elements": loose})
    assert views.finest_level(alone) is alone
