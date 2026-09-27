"""S4 assemble (PRD §3.7, A.5): the full map, every field checked, RACI contests, confidence."""

from __future__ import annotations

import copy
import dataclasses
import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.actions import versions as versions_action
from app.config import AppConfig
from app.db import session_scope
from app.domain.graph import Graph
from app.domain.result import Err, ErrorKind, Ok
from app.main import create_app
from app.pipeline import s2_canonicalise as s2
from app.pipeline import s3_calibrate as s3
from app.pipeline import s3b_verify as s3b
from app.pipeline import s4_assemble as s4
from app.pipeline.context import AiContext, ai_context
from app.repositories import claims
from tests import fixture_engagement
from tests.fixtures import make_ai_fixtures

Sessions = sessionmaker[Session]


@dataclasses.dataclass
class Verified:
    config: AppConfig
    sessions: Sessions
    version_id: str


def verified_with(config: AppConfig) -> Iterator[Verified]:
    """The sample drafted to S1, then S2, S3 and S3b: ready for S4."""
    app = create_app(config)
    with TestClient(app) as client:
        built = fixture_engagement.build(client)
        version_id = make_ai_fixtures.draft_version(app, client, built)
        for stage in (s2.canonicalise, s3.calibrate, s3b.verify):
            make_ai_fixtures.run_stage(app, stage, version_id)
        yield Verified(config, app.state.sessions, version_id)


@pytest.fixture()
def sample(settings_config: AppConfig) -> Iterator[Verified]:
    yield from verified_with(settings_config)


def context(config: AppConfig) -> AiContext:
    result = ai_context(config)
    assert isinstance(result, Ok)
    return result.value


def run(v: Verified) -> s4.S4Tally:
    result = s4.assemble(v.config, v.sessions, context(v.config), version_id=v.version_id)
    assert isinstance(result, Ok), result
    return result.value


def graph(v: Verified) -> Graph:
    result = versions_action.get_graph(v.sessions, v.version_id)
    assert isinstance(result, Ok)
    return result.value


def test_the_sample_answer_file_matches(sample: Verified) -> None:
    digest = make_ai_fixtures.s4_hash(sample.sessions, sample.version_id)
    assert (make_ai_fixtures.MOCKS / s4.STAGE_ID / f"{digest}.json").exists()


def test_the_sample_assembles_into_a_map_that_passes_lint(sample: Verified) -> None:
    """PRD A.5: lint zero failures."""
    tally = run(sample)
    assert (tally.phases, tally.edges, tally.dropped_edges) == (3, 13, 0)
    assert (tally.dropped_fields, tally.dropped_flags, tally.scrubbed) == (0, 0, 0)
    assert tally.contested_steps == ["Deviation in limits?"]
    report = versions_action.lint_version(sample.sessions, sample.version_id)
    assert isinstance(report, Ok)
    assert report.value.failures == []
    assert [w.message for w in report.value.warnings] == [
        'Approval "Approve load plan" has no time stated.',
        'Activity "Issue load sheet" has no time stated.',
    ]


def test_the_sample_map_has_the_a5_details(sample: Verified) -> None:
    run(sample)
    g = graph(sample)
    roles = {r.id: r.name for r in g.roles}
    by = {e.label: e for e in g.elements}
    assert (g.elements[0].kind, g.elements[-1].kind) == ("start", "end")  # process order
    assert by["Flight scheduled"].kind == "start" and by["Final load sheet issued"].kind == "end"
    assert [(p.name, p.time_window) for p in g.phases] == [
        ("Plan", "T-120 to T-90"),
        ("Check and load", ""),
        ("Close out", "T-15 to T-10"),
    ]
    plan = by["Draft load plan"]
    assert (plan.time.work_min, plan.time.text) == (20, "About twenty minutes, around T-120")
    assert plan.k_risk.startswith("Widebody plans rely")
    special = by["Special loads OK?"]
    assert special.decision.mechanism == "rule_based"
    assert roles[special.decision.decider_role_id or ""] == "Load controller"
    assert [(c.text, c.cause_type, c.is_key) for c in special.constraints] == [
        ("The cargo terminal's notification often comes late", "system_fragmentation", True)
    ]
    lir = by["Load and return LIR"]
    assert (lir.time.work_min, lir.time.wait_min) == (40, 15)
    assert sum(c.is_key for c in lir.constraints) == 2
    assert lir.ai_flag is not None and lir.ai_flag.component == "perception"
    assert sum(e.ai_flag is not None for e in g.elements) == 3
    # Every decision and approval is classified (constraint 7).
    assert {e.label: e.decision.mechanism for e in g.elements if e.kind in s4.DECIDING} == {
        "Approve load plan": "judgment",
        "Special loads OK?": "rule_based",
        "Deviation in limits?": "judgment",
        "Approve deviation": "judgment",
    }
    # The re-trim loops back to loading, the offload back to planning.
    ids = {e.id: e.label for e in g.elements}
    loops = {(ids[e.from_], ids[e.to], e.label) for e in g.edges if e.kind == "rework"}
    assert loops == {
        ("Resolve or offload", "Draft load plan", "Re-plan"),
        ("Approve deviation", "Load and return LIR", "Re-trim"),
    }


def test_competing_accountable_roles_are_contested_with_their_evidence(sample: Verified) -> None:
    """A.5 'Deviation in limits?': A contested between Load control lead (SOP) and Captain."""
    run(sample)
    g = graph(sample)
    roles = {r.id: r.name for r in g.roles}
    deviation = next(e for e in g.elements if e.label == "Deviation in limits?")
    accountable = sorted((roles[r.role_id], r.contested) for r in deviation.raci if r.letter == "A")
    assert accountable == [("Captain", True), ("Load control lead", True)]
    assert "ownership" in deviation.divergence_types
    others = [r for e in g.elements if e.label != "Deviation in limits?" for r in e.raci]
    assert not any(r.contested for r in others)
    from app.repositories import elements as map_repo

    with session_scope(sample.sessions) as session:
        raci_evidence = [
            p for p in map_repo.evidence(session, sample.version_id) if p.evidence.raci_id
        ]
    assert {p.evidence.source_kind for p in raci_evidence} == {"interview_transcript", "sop"}


def test_confidence_is_computed_with_a_breakdown_that_sums(sample: Verified) -> None:
    run(sample)
    g = graph(sample)
    confidence = {e.label: e.confidence for e in g.elements}
    assert confidence["Draft load plan"] == 0.85  # O, +1 source, verifier supported
    assert confidence["Approve load plan"] == 0.70  # the job description doesn't count
    assert confidence["Load and return LIR"] == 0.60  # capped while contested
    assert confidence["Flight scheduled"] is None  # start and end are structural, not evidence
    for e in g.elements:
        if e.kind in {"activity", "decision", "approval"}:
            total = round(sum(float(t["delta"]) for t in e.confidence_breakdown), 2)  # type: ignore[arg-type]
            assert total == e.confidence, e.label
    lir = next(e for e in g.elements if e.label == "Load and return LIR")
    assert [t["label"] for t in lir.confidence_breakdown][-1] == "Capped at 0.60 while contested"


def crafted(settings_config: AppConfig, tmp_path: Path, answer: dict[str, Any]) -> AppConfig:
    folder = tmp_path / "mocks"
    shutil.copytree(make_ai_fixtures.MOCKS, folder)
    shutil.rmtree(folder / s4.STAGE_ID)
    (folder / s4.STAGE_ID).mkdir()
    (folder / s4.STAGE_ID / "default.json").write_text(json.dumps(answer))
    return dataclasses.replace(settings_config, mock_fixtures_dir=folder)


def bad_answer() -> dict[str, Any]:
    answer = copy.deepcopy(make_ai_fixtures.S4_ANSWER)
    steps = {s["step_ref"]: s for s in answer["steps"]}
    steps["e1"].update(work_min=30, kpi="Plan by T-45",
                       raci=[{"role": "Load controller", "letter": "R"},
                             {"role": "Duty manager", "letter": "A"}])  # fmt: skip
    steps["e1"]["constraints"].append(
        {"text": "No claim says this", "cause_type": "none", "is_key": False, "claim_refs": []}
    )
    steps["e3"]["decision_mechanism"] = "none"
    steps["e3"]["decider_role"] = "Priya Nair"
    steps["e6"]["ai_flags"] = [
        {"component": "reasoning", "input": "Weights", "output": "Decision", "handoff": "Captain",
         "basis": "rule_based_automate_candidate"}
    ]  # fmt: skip
    steps["e5"]["handoff_out"] = "Report to Priya Nair"
    answer["phases"][0]["time_window"] = "T-200 to T-90"
    answer["edges"].append(make_ai_fixtures.edge("e8", "e99", "sequence", ""))
    answer["edges"].append(make_ai_fixtures.edge("end", "e1", "sequence", ""))
    answer["edges"].append(make_ai_fixtures.edge("e1", "e2"))  # a duplicate
    return answer


def test_every_field_is_checked_against_the_steps_claims(
    settings_config: AppConfig, tmp_path: Path
) -> None:
    for v in verified_with(crafted(settings_config, tmp_path, bad_answer())):
        tally = run(v)
        assert tally.dropped_edges == 2 and tally.edges == 13
        assert tally.dropped_flags == 1  # automation on a judgment step (constraint 7)
        with session_scope(v.sessions) as session:
            register = [
                (r.payload["text"], r.rejection_guardrail, r.rejection_reason, r.stage)
                for _, r in claims.rejected_rows(session, v.version_id)
            ]
        assert register == [
            ("Draft load plan: Plan by T-45", "G5", "number not found in cited text: T-45", "S4"),
            ("Draft load plan: work 30 min", "G5", "number not found in claims: 30", "S4"),
            ("Draft load plan: Duty manager", "G5", "role not found in cited text: Duty manager",
             "S4"),
            ("Draft load plan: No claim says this", "G3", "cites no claim", "S4"),
        ]  # fmt: skip
        # "Priya Nair" named as the decider became her mapped role (G10), never stored as a name.
        assert tally.scrubbed == 2
        g = graph(v)
        by = {e.label: e for e in g.elements}
        plan = by["Draft load plan"]
        assert (plan.time.work_min, plan.kpi) == (None, "")
        assert g.phases[0].time_window == ""  # T-200 isn't in the claims
        special = by["Special loads OK?"]
        assert special.decision.mechanism == "rule_based"  # derived from its claims
        roles = {r.id: r.name for r in g.roles}
        assert roles[special.decision.decider_role_id or ""] == "Load controller"
        assert "Priya" not in g.model_dump_json()
        assert by["Load and return LIR"].handoff.out == "Report to Load controller"


def test_a_format_failure_saves_nothing(settings_config: AppConfig, tmp_path: Path) -> None:
    config = crafted(settings_config, tmp_path, {"phases": "nope"})
    (config.mock_fixtures_dir / "R_repair").mkdir(exist_ok=True)
    (config.mock_fixtures_dir / "R_repair" / "default.json").write_text('{"still": "wrong"}')
    for v in verified_with(config):
        result = s4.assemble(v.config, v.sessions, context(v.config), version_id=v.version_id)
        assert isinstance(result, Err) and result.message == s4.FORMAT_FAILED
        assert graph(v).edges == [] and graph(v).phases == []


def test_a_missing_version_is_not_found(sample: Verified) -> None:
    result = s4.assemble(sample.config, sample.sessions, context(sample.config), version_id="x")
    assert isinstance(result, Err) and result.kind is ErrorKind.NOT_FOUND
