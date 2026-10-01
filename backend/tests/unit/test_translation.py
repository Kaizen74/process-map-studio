"""Verbatim-to-workflow translation on the illustrative sample (PRD v1.10 §3.12.10, Appendix A.9),
through the real draft job with Claude mocked."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from app.db import session_scope
from app.domain import ai_schemas
from app.domain.models import ClaimRecord
from app.domain.result import Ok
from app.domain.sensemaking import StepPosition, Translation, TranslationEdge, TranslationStep
from app.pipeline import s1_extract
from app.repositories import claims as claims_repo
from app.services import translation
from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]
TRANSCRIPT = "interview_transcript.txt"


def transcript_id(d: Drafted) -> str:
    sources = d.client.get(f"/api/engagements/{d.engagement_id}/sources").json()
    return str(next(s["id"] for s in sources if s["filename"] == TRANSCRIPT))


def test_a9_question_matches_and_answer_blocks_after_a_draft(drafted: Drafted) -> None:
    """Step A (acceptance criterion 62): tagged 06:38 → M2.2, 24:40 → M5.s1, 29:40 → M4.3;
    untagged 21:45 → M2.4 by wording; each SME turn carries its answer block's question."""
    page = drafted.client.get(f"/api/sources/{transcript_id(drafted)}/segments").json()
    assert [(s["anchor"], s["question_id"]) for s in page["segments"]] == [
        ("06:38", "M2.2"), ("06:40", "M2.2"), ("07:55", "M2.2"), ("14:05", "M2.2"),
        ("16:22", "M2.2"), ("21:45", "M2.4"), ("21:50", "M2.4"), ("22:30", "M2.4"),
        ("24:10", "M2.4"), ("24:40", "M5.s1"), ("24:46", "M5.s1"), ("27:15", "M5.s1"),
        ("29:02", "M5.s1"), ("29:40", "M4.3"), ("29:48", "M4.3"), ("31:10", "M4.3"),
    ]  # fmt: skip
    documents = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/sources").json()
    sop = next(s["id"] for s in documents if s["filename"] == "sop_LC-07.docx")
    sop_page = drafted.client.get(f"/api/sources/{sop}/segments").json()
    assert {s["question_id"] for s in sop_page["segments"]} == {None}


def test_s1_receives_question_answer_blocks_targets_and_marker_hints(drafted: Drafted) -> None:
    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        result = s1_extract.prepare(session, transcript_id(drafted))
    assert isinstance(result, Ok)
    prepared = result.value
    assert sorted(prepared.questions) == ["M2.2", "M2.4", "M4.3", "M5.s1"]
    first, second, _third = s1_extract.chunks_for(prepared.info.kind, prepared.segments)
    [block] = s1_extract.blocks_for(prepared.info.kind, first, prepared.questions)
    text = str(block["text"])
    # The question list comes first, with each question's targets (what it is evidence for).
    assert text.startswith("<questions>")
    assert (
        '<question id="M2.2" movement="M2" targets="Flow (lived sequence, roles, handoffs' in text
    )
    # Each turn carries its block's question; the SME's turns carry the marker hints.
    assert 'anchor="06:38" speaker="Interviewer" question="M2.2">[M2.2] Walk me through' in text
    assert (
        'anchor="06:40" speaker="Load controller" question="M2.2" '
        'markers="explicit_order: First thing; variation: usually; explicit_order: around T-">'
    ) in text
    # Names stay hidden in what is sent (G10).
    assert "Priya" not in text
    [later] = s1_extract.blocks_for(prepared.info.kind, second, prepared.questions)
    assert 'markers="account_official: Officially; ' in str(later["text"])
    assert "account_lived: What actually happens" in str(later["text"])


# --- B3: accounts, stated reasons, variations and marker reviews (§3.12.3; A.8; crit. 51, 63) -


def claims_at(d: Drafted) -> dict[str, list[ClaimRecord]]:
    """The version's verified interview claims by the anchor of the passage they cite."""
    sessions = d.client.app.state.sessions  # type: ignore[attr-defined]
    page = d.client.get(f"/api/sources/{transcript_id(d)}/segments").json()["segments"]
    anchors = {s["id"]: s["anchor"] for s in page}
    out: dict[str, list[ClaimRecord]] = {}
    with session_scope(sessions) as session:
        for c in claims_repo.list_claims(session, d.version_id, "verified"):
            if c.account_type is not None:
                out.setdefault(anchors[c.segment_ids[0]], []).append(c)
    return out


def test_a8_account_tags_with_quoted_cues(drafted: Drafted) -> None:
    by_anchor = claims_at(drafted)
    official, lived = by_anchor["22:30"]
    assert (official.account_type, official.payload["account_cue"]) == ("official", "Officially")
    assert (lived.account_type, lived.payload["account_cue"]) == ("lived", "What actually happens")
    # The lived account keeps the SME's stated reason and the condition of the variation.
    assert lived.payload["stated_reason"] == "otherwise we'd miss the slot"
    assert lived.payload["variation_condition"] == "on a busy wave"
    assert {c.account_type for c in by_anchor["21:50"]} >= {"lived"}
    # Every interview claim carries an account; documents' claims carry none.
    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        verified = claims_repo.list_claims(session, drafted.version_id, "verified")
    interview_source = transcript_id(drafted)
    assert all((c.account_type is not None) == (c.source_id == interview_source) for c in verified)


def test_marker_hints_are_confirmed_or_set_aside_with_a_quote(drafted: Drafted) -> None:
    [plan] = [c for c in claims_at(drafted)["06:40"]]
    assert plan.payload["markers"] == [
        {"marker": "explicit_order: First thing", "confirmed": True, "quote": "First thing"},
        {"marker": "variation: usually", "confirmed": False, "quote": "usually around T-120"},
    ]
    assert plan.payload["markers_dropped"] == 0


def element_named(d: Drafted, label: str) -> dict[str, Any]:
    graph = d.client.get(f"/api/versions/{d.version_id}/graph").json()
    element = next(e for e in graph["elements"] if e["label"] == label)
    return dict(d.client.get(f"/api/elements/{element['id']}").json())


def test_each_step_shows_its_accounts_and_the_questions_behind_its_answers(
    drafted: Drafted,
) -> None:
    lir = element_named(drafted, "Load and return LIR")
    assert lir["account_summary"] == {"official": 1, "lived": 3, "unclear": 1}
    assert lir["practice_described"] is True
    official = next(a for a in lir["answers"] if a["account_type"] == "official")
    assert official == {
        "quote": "Officially the ramp should send the report within ten minutes.",
        "account_type": "official",
        "account_cue": "Officially",
        "stated_reason": "",
        "variation_condition": "",
        "source_id": transcript_id(drafted),
        "segment_id": official["segment_id"],
        "anchor": "22:30",
        "question_id": "M2.4",
        "question": "How long did each part take, and where were you waiting on someone or "
        "something?",
    }
    # A step only the documents describe has no account; the interview is silent on it.
    approve = element_named(drafted, "Approve load plan")
    assert approve["account_summary"] == {"official": 0, "lived": 0, "unclear": 0}
    assert approve["practice_described"] is None and approve["answers"] == []
    # Names stay hidden in the answers (G10).
    assert "Priya" not in json.dumps(lir)


def test_practice_not_described_when_only_the_official_account_speaks() -> None:
    summary = translation.account_summary(["official", "unclear", None])
    assert summary.model_dump() == {"official": 1, "lived": 0, "unclear": 1}
    assert translation.practice_described(summary) is False
    assert translation.practice_described(translation.account_summary(["lived"])) is True
    assert translation.practice_described(translation.account_summary([None, "unclear"])) is None


def test_ungrounded_cues_reasons_conditions_and_marker_quotes_are_dropped() -> None:
    cited = "Load controller: Officially the ramp should send the report within ten minutes."
    claim = ai_schemas.S1InterviewClaim(
        claim_type="threshold",
        text="The Ramp should send the report within ten minutes.",
        responsible_role="Ramp",
        accountable_role="",
        decider_role="",
        mechanism="none",
        duration_text="",
        threshold="",
        segment_ids=["p8"],
        quote="Officially the ramp should send the report within ten minutes.",
        provenance="O",
        basis="",
        account_type="lived",
        account_cue="What actually happens",  # not in the cited passage
        stated_reason="because the SOP is old",  # invented
        variation_condition="officially",  # in the passage: kept
        markers=[
            ai_schemas.S1MarkerReview(
                marker="account_official: Officially", confirmed=True, quote="Officially"
            ),
            ai_schemas.S1MarkerReview(marker="wait: wait", confirmed=True, quote="we wait"),
        ],
    )
    account, fields = s1_extract.check_interview_fields(claim, cited)
    assert account == "unclear"
    assert fields["account_cue"] == "" and fields["account_cue_dropped"] is True
    assert fields["stated_reason"] == "" and fields["variation_condition"] == "officially"
    assert fields["markers"] == [
        {"marker": "account_official: Officially", "confirmed": True, "quote": "Officially"}
    ]
    assert fields["markers_dropped"] == 1


# --- Views and sequence basis (§3.12.10 rules 1-7, §3.12.11; A.9; acceptance criteria 63-65) ---


def lines(graph: dict[str, Any], view: str) -> list[tuple[str, str, str, str]]:
    """The lines a view draws: (from, to, kind, sequence basis)."""
    named = {e["id"]: e["label"] for e in graph["elements"]}
    keep = {"both", f"{view}_only"}
    return [
        (named[e["from"]], named[e["to"]], e["kind"], e["sequence_basis"])
        for e in graph["edges"]
        if e["view_membership"] in keep
    ]


def test_a9_as_done_and_as_documented_from_one_draft(drafted: Drafted) -> None:
    graph = drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()
    views = {e["label"]: e["view_membership"] for e in graph["elements"]}
    assert views == {
        "Flight scheduled": "both",
        "Draft load plan": "both",
        "Approve load plan": "documented_only",  # not described in practice
        "Special loads OK?": "both",
        "Resolve or offload": "done_only",
        "Load and return LIR": "both",  # contested: in both, with variants
        "Busy wave?": "done_only",
        "Read report at aircraft": "done_only",
        "Deviation in limits?": "both",
        "Approve deviation": "done_only",
        "Issue load sheet": "both",
        "Final load sheet issued": "both",
    }
    # As done: the SME states the next step after drafting ("Then I check special loads"), so
    # the line is explicit order and there is no "not described" connector (A.9).
    assert lines(graph, "done") == [
        ("Flight scheduled", "Draft load plan", "sequence", "explicit_order"),
        ("Special loads OK?", "Load and return LIR", "yes", "explicit_order"),
        ("Special loads OK?", "Resolve or offload", "no", "explicit_order"),
        ("Resolve or offload", "Draft load plan", "rework", "explicit_order"),
        ("Load and return LIR", "Busy wave?", "sequence", "narration_order"),
        ("Busy wave?", "Read report at aircraft", "yes", "explicit_order"),
        ("Busy wave?", "Deviation in limits?", "no", "explicit_order"),
        ("Read report at aircraft", "Deviation in limits?", "sequence", "narration_order"),
        ("Deviation in limits?", "Issue load sheet", "yes", "explicit_order"),
        ("Deviation in limits?", "Approve deviation", "no", "explicit_order"),
        ("Approve deviation", "Issue load sheet", "approve", "explicit_order"),
        ("Approve deviation", "Load and return LIR", "rework", "explicit_order"),
        ("Issue load sheet", "Final load sheet issued", "sequence", "explicit_order"),
        ("Draft load plan", "Special loads OK?", "sequence", "explicit_order"),
    ]
    assert not [e for e in graph["edges"] if e["kind"] == "gap"]
    # As documented: the SOP's order (LC-07 §3.1 before §3.2); RP-02 and LC-07 don't say which
    # of the loading report and the deviation check comes first, so that line is narration order.
    assert lines(graph, "documented") == [
        ("Flight scheduled", "Draft load plan", "sequence", "explicit_order"),
        ("Draft load plan", "Approve load plan", "sequence", "document_order"),
        ("Approve load plan", "Special loads OK?", "approve", "explicit_order"),
        ("Approve load plan", "Draft load plan", "reject", "explicit_order"),
        ("Special loads OK?", "Load and return LIR", "yes", "explicit_order"),
        ("Deviation in limits?", "Issue load sheet", "yes", "explicit_order"),
        ("Issue load sheet", "Final load sheet issued", "sequence", "explicit_order"),
        ("Load and return LIR", "Deviation in limits?", "sequence", "narration_order"),
    ]
    # Each line resting only on the order of mentioning becomes a validation question, written
    # after the step questions (and the S1 gaps).
    questions = drafted.client.get(f"/api/versions/{drafted.version_id}/questions").json()
    assert [q["reason"] for q in questions] == [
        "documented_only", "contested", "contested", "gap", "gap",
        "sequence", "sequence", "sequence",
    ]  # fmt: skip
    assert questions[-3]["question"] == (
        'Does "Busy wave?" come right after "Load and return LIR"? The sources mention it later '
        "but don't say it comes next."
    )
    assert {q["element_label"] for q in questions[-3:]} == {"Busy wave?", "Deviation in limits?"}


def step(
    sid: str,
    state: str,
    interview: Sequence[tuple[int, bool, bool]] = (),
    documents: Sequence[int] = (),
    kind: str = "activity",
) -> TranslationStep:
    return TranslationStep(
        id=sid, kind=kind, label=sid.upper(), source_state=state, provenance="O",
        interview=[StepPosition(source_id="t", seq=s, lived=lived, explicit=explicit)
                   for s, lived, explicit in interview],
        documents=[StepPosition(source_id="sop", seq=s) for s in documents],
    )  # fmt: skip


def line(a: str, b: str, kind: str = "sequence", label: str = "") -> TranslationEdge:
    return TranslationEdge(id=f"{a}{b}", from_id=a, to_id=b, kind=kind, label=label)


def drawn(result: Translation, view: str) -> list[tuple[str, str, str, str, str]]:
    keep = {"both", f"{view}_only"}
    return [
        (e.from_id, e.to_id, e.kind, e.label, e.sequence_basis)
        for e in result.edges
        if e.view_membership in keep
    ]


def test_a_jump_in_the_lived_account_becomes_a_not_described_connector() -> None:
    """Rule 7 (criterion 65): "…and then it's done" where the SOP shows two steps in between:
    As done gets a dashed "not described" connector and a follow-up question, never a step."""
    steps = [
        step("a", "corroborated", [(1, True, False)], [1]),
        step("b", "documented_only", documents=[2]),
        step("c", "documented_only", documents=[3]),
        step("d", "corroborated", [(2, True, False)], [4]),
    ]
    result = translation.translate(steps, [line("a", "b"), line("b", "c"), line("c", "d")])
    assert drawn(result, "documented") == [
        ("a", "b", "sequence", "", "document_order"),
        ("b", "c", "sequence", "", "document_order"),
        ("c", "d", "sequence", "", "document_order"),
    ]
    assert drawn(result, "done") == [("a", "d", "gap", "Not described", "document_order")]
    assert [(q.element_id, q.reason) for q in result.questions] == [("d", "not_described")]
    assert result.questions[0].question == (
        'The documents describe "B", "C" between "A" and "D", but the interview doesn\'t say what '
        "happens there. What happens in practice?"
    )
    # Running it again on its own output changes nothing (a refresh, a second pass).
    again = translation.translate(steps, [
        TranslationEdge(**e.model_dump(exclude={"sequence_basis", "view_membership"}))
        for e in result.edges
    ])  # fmt: skip
    assert drawn(again, "done") == drawn(result, "done")
    assert drawn(again, "documented") == drawn(result, "documented")


def test_a_stated_next_step_bridges_without_a_connector() -> None:
    """Rule 1: "first … then" in the lived account is explicit order across the skipped step."""
    steps = [
        step("a", "corroborated", [(1, True, True)], [1]),
        step("b", "documented_only", documents=[2]),
        step("c", "corroborated", [(2, True, True)], [3]),
    ]
    result = translation.translate(steps, [line("a", "b"), line("b", "c")])
    assert drawn(result, "done") == [("a", "c", "sequence", "", "explicit_order")]
    assert result.questions == []


def test_sequence_basis_strongest_first() -> None:
    told = step("a", "corroborated", [(1, True, False)], [1])
    later = step("b", "corroborated", [(2, True, True)], [2])
    assert translation.sequence_basis(told, later, "sequence") == "explicit_order"
    sop_only = step("b", "corroborated", [(2, False, False)], [2])
    assert translation.sequence_basis(told, sop_only, "sequence") == "document_order"
    hand = told.model_copy(update={"handoff_out": "Load plan", "documents": []})
    takes = sop_only.model_copy(update={"handoff_in": "load  plan", "documents": []})
    assert translation.sequence_basis(hand, takes, "sequence") == "dependency"
    assert translation.sequence_basis(hand, sop_only.model_copy(update={"documents": []}),
                                      "sequence") == "narration_order"  # fmt: skip
    # A stated exit or loop is explicit; so are the trigger and the end point.
    assert translation.sequence_basis(hand, takes, "no") == "explicit_order"
    assert translation.sequence_basis(step("s", "not_assessed", kind="start"), takes,
                                      "sequence") == "explicit_order"  # fmt: skip


def test_recommended_practice_is_documented_only() -> None:
    added = step("r", "not_assessed").model_copy(update={"provenance": "R"})
    assert translation.element_view(added) == "documented_only"
    assert translation.element_view(step("t", "trace_contradicted")) == "both"


def test_each_view_of_the_sample_passes_its_flow_checks(drafted: Drafted) -> None:
    """B5 (§3.12.11): `?view=` gives one view's steps and lines; both views pass the flow checks
    on their own; the three narration-order lines are warnings (with their questions)."""
    url = f"/api/versions/{drafted.version_id}/graph"
    done = drafted.client.get(url, params={"view": "done"}).json()
    documented = drafted.client.get(url, params={"view": "documented"}).json()
    assert [e["label"] for e in done["elements"]] == [
        "Flight scheduled", "Draft load plan", "Special loads OK?", "Resolve or offload",
        "Load and return LIR", "Busy wave?", "Read report at aircraft", "Deviation in limits?",
        "Approve deviation", "Issue load sheet", "Final load sheet issued",
    ]  # fmt: skip
    assert [e["label"] for e in documented["elements"]] == [
        "Flight scheduled", "Draft load plan", "Approve load plan", "Special loads OK?",
        "Load and return LIR", "Deviation in limits?", "Issue load sheet",
        "Final load sheet issued",
    ]  # fmt: skip
    assert len(done["edges"]) == 14 and len(documented["edges"]) == 8
    # Cycle time per view (§3.12.11): each view's main path has two steps without time; the map
    # as one has three (Approve load plan is only in As documented).
    assert done["process"]["cycle_time"] == documented["process"]["cycle_time"] == {
        "elapsed_min": 75.0, "work_min": 60.0, "incomplete_steps": 2,
    }  # fmt: skip
    assert drafted.client.get(url).json()["process"]["cycle_time"]["incomplete_steps"] == 3
    bad = drafted.client.get(url, params={"view": "both"})
    assert bad.status_code == 422
    lint = drafted.client.get(f"/api/versions/{drafted.version_id}/lint").json()
    assert [f for f in lint["failures"] if f["view"]] == []
    narration = [w["message"] for w in lint["warnings"] if "order the sources" in w["message"]]
    assert narration == [
        'The line from "Load and return LIR" to "Busy wave?" rests only on the order the sources '
        "mention them.",
        'The line from "Read report at aircraft" to "Deviation in limits?" rests only on the order '
        "the sources mention them.",
        'The line from "Load and return LIR" to "Deviation in limits?" rests only on the order the '
        "sources mention them.",
    ]


def test_views_are_kept_up_to_date_on_drafts_only(drafted: Drafted) -> None:
    """After an edit the views are worked out again (no AI); a published version never changes
    (constraint 8), even when its lint report is worked out again."""
    from sqlalchemy import update

    from app.actions import versions as versions_action
    from app.repositories import elements as map_repo
    from app.repositories.tables import MapVersion

    sessions = drafted.client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        plan = next(e for e in map_repo.elements(session, drafted.version_id)
                    if e.label == "Draft load plan")  # fmt: skip
        map_repo.update_element(session, plan.id, {"view_membership": None})
    versions_action.lint_version(sessions, drafted.version_id)
    with session_scope(sessions) as session:
        assert map_repo.element(session, plan.id).view_membership == "both"  # type: ignore[union-attr]
        map_repo.update_element(session, plan.id, {"view_membership": None})
        before = len(map_repo.edges(session, drafted.version_id))
        session.execute(
            update(MapVersion).where(MapVersion.id == drafted.version_id).values(state="published")
        )
    versions_action.lint_version(sessions, drafted.version_id)
    with session_scope(sessions) as session:
        assert map_repo.element(session, plan.id).view_membership is None  # type: ignore[union-attr]
        assert len(map_repo.edges(session, drafted.version_id)) == before


def test_each_view_is_laid_out_and_the_other_view_can_be_shown_ghosted(drafted: Drafted) -> None:
    """V1 (§3.12.11): the layout of one view; with Show the other view, the steps and lines only
    in the other view are placed too and marked ghost (no marker is added)."""
    url = f"/api/versions/{drafted.version_id}/layout"
    graph = drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()
    named = {e["id"]: e["label"] for e in graph["elements"]}
    edges = {e["id"]: (named[e["from"]], named[e["to"]]) for e in graph["edges"]}
    done = drafted.client.get(url, params={"view": "done"}).json()
    assert done["view"] == "done" and not any(n["ghost"] for n in done["nodes"])
    assert "Approve load plan" not in [named[n["id"]] for n in done["nodes"]]
    shown = drafted.client.get(url, params={"view": "done", "show_other": "true"}).json()
    assert [named[n["id"]] for n in shown["nodes"] if n["ghost"]] == ["Approve load plan"]
    assert sorted(edges[e["id"]] for e in shown["edges"] if e["ghost"]) == [
        ("Approve load plan", "Draft load plan"),
        ("Approve load plan", "Special loads OK?"),
        ("Draft load plan", "Approve load plan"),
    ]
    # As done's own line from drafting to the special-loads check is drawn; As documented's
    # line from loading to the deviation check is not.
    drawn = [edges[e["id"]] for e in shown["edges"]]
    assert ("Draft load plan", "Special loads OK?") in drawn
    assert ("Load and return LIR", "Deviation in limits?") not in drawn
    assert drafted.client.get(url, params={"view": "later"}).status_code == 422
    combined = drafted.client.get(url).json()
    assert combined["view"] is None and len(combined["nodes"]) == 12
