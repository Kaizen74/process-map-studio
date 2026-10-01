"""The stored map and its graph (PRD §3.5, §3.6): repository round trips and `build_graph`."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.actions import versions as versions_action
from app.config import AppConfig
from app.db import session_scope
from app.domain.graph import (
    AiFlagRecord,
    ConstraintRecord,
    EdgeRecord,
    ElementRecord,
    EvidenceRecord,
    MergeProposalRecord,
    PhaseRecord,
    QuestionRecord,
    RaciRecord,
)
from app.domain.result import Err, ErrorKind, Ok
from app.main import create_app
from app.repositories import elements as map_repo
from app.repositories import sources as sources_repo
from app.repositories import versions
from tests import fixture_engagement

Sessions = sessionmaker[Session]


@dataclass
class Built:
    sessions: Sessions
    version_id: str
    roles: dict[str, str]
    ids: dict[str, str]  # element key → id
    sources: dict[str, str]


@pytest.fixture()
def built(settings_config: AppConfig) -> Iterator[Built]:
    """A small hand-built map: start → plan → special loads? (yes → issue; no → offload,
    which reworks the plan) → issue → end, plus an approval of the plan and a rejected step."""
    app = create_app(settings_config)
    with TestClient(app) as client:
        fx = fixture_engagement.build(client, ["interview_transcript.txt", "sop_LC-07.docx"])
        sessions: Sessions = app.state.sessions
        with session_scope(sessions) as session:
            version = versions.create(
                session, engagement_id=fx.engagement_id, label="v0.1", state="draft"
            )
            vid = version.id
            interview = sources_repo.stored_segments(
                session, fx.sources["interview_transcript.txt"]
            )
            sop = sources_repo.stored_segments(session, fx.sources["sop_LC-07.docx"])
            map_repo.add_version_sources(session, vid, list(fx.sources.values()))
            [plan_phase, load_phase] = map_repo.add_phases(
                session,
                vid,
                [
                    PhaseRecord(name="Plan", time_window="T-120 to T-90", sort_order=1),
                    PhaseRecord(name="Load", sort_order=2),
                ],
            )
            lc = fx.roles["Load controller"]

            def el(key: str, kind: str, label: str, **fields: object) -> ElementRecord:
                return ElementRecord(
                    stable_key=key, kind=kind, label=label, provenance="O", **fields
                )  # type: ignore[arg-type]

            added = map_repo.add_elements(
                session,
                vid,
                [
                    el("start", "start", "Flight scheduled"),
                    el("plan", "activity", "Draft load plan for Priya Nair", lane_role_id=lc,
                       phase_id=plan_phase.id, work_min=20, duration_text="~20 min",
                       source_state="corroborated", confidence=0.85,
                       confidence_breakdown=[{"label": "Observed (O)", "delta": 0.6}],
                       k_risk="Widebody plans rely on two senior controllers"),
                    el("approve", "approval", "Approve load plan", work_min=None,
                       lane_role_id=fx.roles["Load control lead"], phase_id=plan_phase.id),
                    el("special", "decision", "Special loads OK?", lane_role_id=lc,
                       phase_id=load_phase.id, decision_mechanism="rule_based",
                       decider_role_id=lc, rule_or_threshold="Acceptance checklist"),
                    el("offload", "activity", "Resolve or offload", work_min=40,
                       lane_role_id=fx.roles["Airline ops"], phase_id=load_phase.id),
                    el("issue", "activity", "Issue load sheet", lane_role_id=lc,
                       phase_id=load_phase.id, wait_min=5),
                    el("dropped", "activity", "Rejected step", work_min=500,
                       review_status="rejected"),
                    el("end", "end", "Final load sheet issued"),
                ],
            )  # fmt: skip
            ids = {e.stable_key: e.id for e in added}
            map_repo.add_edges(
                session,
                vid,
                [
                    EdgeRecord(from_element_id=ids[a], to_element_id=ids[b], kind=k, label=lab)
                    for a, b, k, lab in [
                        ("start", "plan", "sequence", ""),
                        ("plan", "approve", "sequence", ""),
                        ("approve", "special", "approve", "Approve"),
                        ("approve", "plan", "reject", "Rework"),
                        ("special", "offload", "no", "No"),
                        ("special", "dropped", "yes", "Yes"),
                        ("special", "issue", "yes", "Yes"),
                        ("offload", "plan", "rework", "Re-plan"),
                        ("issue", "end", "sequence", ""),
                    ]
                ],
            )
            [raci] = map_repo.add_raci(
                session, [RaciRecord(element_id=ids["plan"], role_id=lc, letter="R")]
            )
            map_repo.add_evidence(
                session,
                [
                    EvidenceRecord(element_id=ids["plan"], segment_id=interview[1].id,
                                   source_kind="interview_transcript", stance="supports",
                                   verified=True, quote="I build the preliminary load plan"),
                    EvidenceRecord(element_id=ids["plan"], segment_id=sop[2].id,
                                   source_kind="sop", stance="contradicts", verified=True,
                                   note="Timing: T-90 in the SOP vs T-120 by Priya Nair"),
                    EvidenceRecord(raci_id=raci.id, segment_id=sop[2].id, source_kind="sop",
                                   stance="supports", verified=True),
                ],
            )  # fmt: skip
            map_repo.add_constraints(
                session,
                [ConstraintRecord(element_id=ids["special"], text="Notification comes late",
                                  provenance="O", cause_type="system_fragmentation", is_key=True)],
            )  # fmt: skip
            map_repo.add_ai_flags(
                session,
                [AiFlagRecord(element_id=ids["special"], component="reasoning", input="Loads",
                              output="Accept or refuse", handoff="Load controller",
                              basis="rule_based_automate_candidate")],
            )  # fmt: skip
            map_repo.add_merge_proposals(
                session, vid, [MergeProposalRecord(claim_ids=["a", "b"], proposed_label="X",
                                                   similarity=0.85, decision="accepted")]
            )  # fmt: skip
            map_repo.add_questions(
                session,
                vid,
                [QuestionRecord(element_id=ids["approve"], question="Is it approved?",
                                reason="documented_only")],
            )  # fmt: skip
        yield Built(sessions, vid, fx.roles, ids, fx.sources)


def graph_of(built: Built) -> dict[str, object]:
    result = versions_action.get_graph(built.sessions, built.version_id)
    assert isinstance(result, Ok)
    return dict(json.loads(result.value.model_dump_json()))


def test_graph_has_the_prd_shape(built: Built) -> None:
    graph = graph_of(built)
    assert set(graph) == {"version", "process", "roles", "phases", "elements", "edges"}
    assert graph["version"] == {
        "id": built.version_id, "label": "v0.1", "state": "draft", "quality_card": None,
    }  # fmt: skip
    process = graph["process"]
    assert isinstance(process, dict)
    assert process["trigger"] == "Flight scheduled"
    assert process["end_point"] == "Final load sheet issued"
    edges = graph["edges"]
    assert isinstance(edges, list)
    # v1.10 (§3.12.10-3.12.11): why each line is there and which views draw it.
    assert set(edges[0]) == {
        "id", "from", "to", "kind", "label",
        "sequence_basis", "view_membership", "information_payload", "typical", "provenance",
    }  # fmt: skip
    elements = graph["elements"]
    assert isinstance(elements, list)
    plan = next(e for e in elements if e["stable_key"] == "plan")
    assert set(plan["handoff"]) == {"in", "out"}
    assert plan["time"] == {"work_min": 20.0, "wait_min": None, "text": "~20 min"}
    assert plan["raci"] == [
        {"role_id": built.roles["Load controller"], "letter": "R", "contested": False}
    ]
    assert plan["confidence"] == 0.85
    assert plan["confidence_breakdown"] == [{"label": "Observed (O)", "delta": 0.6}]
    special = next(e for e in elements if e["stable_key"] == "special")
    assert special["decision"]["mechanism"] == "rule_based"
    assert special["constraints"][0]["is_key"] is True
    assert special["ai_flag"]["basis"] == "rule_based_automate_candidate"
    assert next(e for e in elements if e["stable_key"] == "issue")["ai_flag"] is None


def test_evidence_lists_every_source_and_silent_ones_have_no_passage(built: Built) -> None:
    elements = graph_of(built)["elements"]
    assert isinstance(elements, list)
    plan = next(e for e in elements if e["stable_key"] == "plan")
    stances = [(ev["source_kind"], ev["stance"]) for ev in plan["evidence"]]
    assert stances == [("interview_transcript", "supports"), ("sop", "contradicts")]
    assert plan["evidence"][0]["anchor"] == "06:40"
    assert plan["evidence"][1]["anchor"].startswith("§")
    approve = next(e for e in elements if e["stable_key"] == "approve")
    assert [(ev["stance"], ev["segment_id"], ev["anchor"]) for ev in approve["evidence"]] == [
        ("silent", None, ""),
        ("silent", None, ""),
    ]
    # RACI evidence belongs to the RACI entry, not to the element's evidence list.
    assert len(plan["evidence"]) == 2


def test_graph_never_carries_quotes_or_names(built: Built) -> None:
    text = json.dumps(graph_of(built))
    assert "I build the preliminary load plan" not in text  # the stored quote
    assert "Priya" not in text
    assert "Draft load plan for Load controller" in text
    assert "T-120 by Load controller" in text


def test_cycle_time_follows_the_main_path(built: Built) -> None:
    """start → plan (20) → approve (no time) → special → issue (5 wait) → end; the offload
    exception and the rejected step are off the main path."""
    process = graph_of(built)["process"]
    assert isinstance(process, dict)
    assert process["cycle_time"] == {"elapsed_min": 25.0, "work_min": 20.0, "incomplete_steps": 1}


def test_main_path_stops_on_a_loop(built: Built) -> None:
    with session_scope(built.sessions) as session:
        elements = map_repo.elements(session, built.version_id)
        edges = [
            EdgeRecord(from_element_id=built.ids["start"], to_element_id=built.ids["plan"],
                       kind="sequence"),
            EdgeRecord(from_element_id=built.ids["plan"], to_element_id=built.ids["start"],
                       kind="sequence"),
        ]  # fmt: skip
    path = versions_action.main_path(elements, edges)
    assert [e.stable_key for e in path] == ["start", "plan"]


def test_main_path_is_empty_without_a_start() -> None:
    assert versions_action.main_path([], []) == []


def test_repository_round_trips(built: Built) -> None:
    with session_scope(built.sessions) as session:
        assert [p.name for p in map_repo.phases(session, built.version_id)] == ["Plan", "Load"]
        assert len(map_repo.elements(session, built.version_id)) == 8
        assert len(map_repo.edges(session, built.version_id)) == 9
        assert len(map_repo.raci(session, built.version_id)) == 1
        assert len(map_repo.evidence(session, built.version_id)) == 3
        assert [m.similarity for m in map_repo.merge_proposals(session, built.version_id)] == [0.85]
        [question] = map_repo.questions(session, built.version_id)
        assert (question.reason, question.status) == ("documented_only", "open")
        assert map_repo.version_source_ids(session, built.version_id) == list(
            built.sources.values()
        )


def test_claims_link_and_unlink(built: Built) -> None:
    with session_scope(built.sessions) as session:
        # Claims need real rows: borrow two from a quick insert through the claims repository.
        from app.domain.models import ClaimRecord
        from app.repositories import claims

        records = [
            ClaimRecord(source_id=built.sources["sop_LC-07.docx"], stage="S1",
                        claim_type="activity", payload={"text": t}, segment_ids=[], quote="",
                        provenance="O", basis="", verification_status="verified")
            for t in ("one", "two")
        ]  # fmt: skip
        claims.add_claims(session, built.version_id, records)
        ids = [cid for cid, _ in claims.verified_rows(session, built.version_id)]
        map_repo.link_claims(session, built.ids["plan"], ids)
        assert map_repo.element_claims(session, built.version_id) == {built.ids["plan"]: ids}
        map_repo.unlink_claims(session, ids[:1])
        assert map_repo.element_claims(session, built.version_id) == {built.ids["plan"]: ids[1:]}


def test_update_and_delete_elements(built: Built) -> None:
    with session_scope(built.sessions) as session:
        updated = map_repo.update_element(
            session, built.ids["plan"], {"needs_check": True, "source_state": "contested"}
        )
        assert updated is not None and updated.needs_check and updated.source_state == "contested"
        assert map_repo.update_element(session, "missing", {"label": "x"}) is None
        with pytest.raises(ValueError, match="not an element field"):
            map_repo.update_element(session, built.ids["plan"], {"colour": "red"})
        map_repo.delete_elements(session, [built.ids["special"]])
        map_repo.delete_elements(session, [])
        # Its edges, constraint and AI flag go with it.
        assert len(map_repo.edges(session, built.version_id)) == 5
        assert map_repo.constraints(session, built.version_id) == []
        assert map_repo.ai_flags(session, built.version_id) == []


def test_deleting_the_version_removes_its_map(built: Built) -> None:
    with session_scope(built.sessions) as session:
        versions.delete(session, built.version_id)
        assert map_repo.elements(session, built.version_id) == []
        assert map_repo.phases(session, built.version_id) == []
        assert map_repo.version_source_ids(session, built.version_id) == []


def test_missing_version_is_not_found(built: Built) -> None:
    result = versions_action.get_graph(built.sessions, "nope")
    assert isinstance(result, Err) and result.kind is ErrorKind.NOT_FOUND


def test_lint_runs_on_the_graph_and_is_stored_on_the_version(built: Built) -> None:
    result = versions_action.lint_version(built.sessions, built.version_id)
    assert isinstance(result, Ok)
    failures = {(f.rule, f.element_id) for f in result.value.failures}
    # The hand-built map has gaps on purpose: an approval with no evidence and no RACI.
    assert ("L2", built.ids["approve"]) in failures
    assert ("L11", built.ids["approve"]) in failures
    # The rejected step is left out entirely.
    assert not any(element == built.ids["dropped"] for _, element in failures)
    with session_scope(built.sessions) as session:
        stored = versions.lint_report(session, built.version_id)
    assert stored == result.value.model_dump(mode="json")
    assert versions_action.lint_version(built.sessions, "nope") == Err(
        ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING
    )


def test_a_version_without_lint_has_no_report(built: Built) -> None:
    with session_scope(built.sessions) as session:
        assert versions.lint_report(session, built.version_id) is None
        assert versions.lint_report(session, "nope") is None
