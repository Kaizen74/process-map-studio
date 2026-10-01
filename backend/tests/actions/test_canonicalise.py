"""S2 canonicalise (PRD §3.7): verified claims become steps; every step is checked (G3, G5, G10)."""

from __future__ import annotations

import dataclasses
import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.config import AppConfig
from app.db import session_scope
from app.domain.result import Err, ErrorKind, Ok
from app.main import create_app
from app.pipeline import s2_canonicalise as s2
from app.pipeline.context import AiContext, ai_context
from app.repositories import claims, engagements, versions
from app.repositories import elements as map_repo
from tests.fixtures import make_ai_fixtures

Sessions = sessionmaker[Session]


@dataclasses.dataclass
class Drafted:
    config: AppConfig
    sessions: Sessions
    client: TestClient
    engagement_id: str
    version_id: str


def drafted_with(config: AppConfig) -> Iterator[Drafted]:
    """The sample engagement drafted up to S1 (the P3 draft job), ready for S2."""
    app = create_app(config)
    with TestClient(app) as client:
        from tests import fixture_engagement

        built = fixture_engagement.build(client)
        version_id = make_ai_fixtures.draft_version(app, client, built)
        yield Drafted(config, app.state.sessions, client, built.engagement_id, version_id)


@pytest.fixture()
def sample(settings_config: AppConfig) -> Iterator[Drafted]:
    yield from drafted_with(settings_config)


def crafted(settings_config: AppConfig, tmp_path: Path, answer: dict[str, Any]) -> AppConfig:
    """The sample's mock answers, with this S2 answer in place of the real one."""
    folder = tmp_path / "mocks"
    shutil.copytree(make_ai_fixtures.MOCKS, folder)
    shutil.rmtree(folder / s2.STAGE_ID)
    (folder / s2.STAGE_ID).mkdir()
    (folder / s2.STAGE_ID / "default.json").write_text(json.dumps(answer))
    return dataclasses.replace(settings_config, mock_fixtures_dir=folder)


def context(config: AppConfig) -> AiContext:
    result = ai_context(config)
    assert isinstance(result, Ok)
    return result.value


def run(d: Drafted) -> s2.S2Tally:
    result = s2.canonicalise(d.config, d.sessions, context(d.config), version_id=d.version_id)
    assert isinstance(result, Ok), result
    return result.value


def test_the_sample_answer_file_matches_the_current_claims(sample: Drafted) -> None:
    """If S1 answers, roles or rendering change, rerun tests/fixtures/make_ai_fixtures.py."""
    digest = make_ai_fixtures.s2_hash(sample.sessions, sample.version_id, sample.engagement_id)
    assert (make_ai_fixtures.MOCKS / s2.STAGE_ID / f"{digest}.json").exists()


def test_the_sample_becomes_the_eight_steps_of_a5(sample: Drafted) -> None:
    tally = run(sample)
    assert (tally.steps, tally.rejected, tally.merged, tally.pending_merges) == (8, 0, 1, 0)
    with session_scope(sample.sessions) as session:
        elements = map_repo.elements(session, sample.version_id)
        roles = {r.id: r.name for r in engagements.list_roles(session, sample.engagement_id)}
        linked = map_repo.element_claims(session, sample.version_id)
        [merge] = map_repo.merge_proposals(session, sample.version_id)
    assert [(e.label, e.kind, roles[e.lane_role_id or ""]) for e in elements] == [
        ("Draft load plan", "activity", "Load controller"),
        ("Approve load plan", "approval", "Load control lead"),
        ("Special loads OK?", "decision", "Load controller"),
        ("Resolve or offload", "activity", "Airline ops"),
        ("Load and return LIR", "activity", "Ramp"),
        ("Deviation in limits?", "decision", "Load controller"),
        ("Approve deviation", "approval", "Captain"),
        ("Issue load sheet", "activity", "Load controller"),
    ]
    assert [e.stable_key for e in elements][:2] == ["draft-load-plan", "approve-load-plan"]
    assert all(e.provenance == "O" and e.review_status == "draft" for e in elements)
    assert all(e.source_state == "not_assessed" for e in elements)  # S3 classifies
    # v1.10 sample: Load aircraft also carries the SME's official account of the return time.
    assert [len(linked[e.id]) for e in elements] == [4, 2, 3, 1, 6, 3, 1, 2]
    assert (merge.proposed_label, merge.similarity, merge.decision) == (
        "Load and return LIR",
        0.86,
        "accepted",
    )
    assert len(merge.claim_ids) == 6 and merge.decided_at  # v1.10: + the official account


BAD_STEPS = {
    "steps": [
        make_ai_fixtures.step("a", "activity", "Draft load plan", "Load controller", [1]),
        make_ai_fixtures.step("b", "activity", "Check fuel", "Load controller", [99]),
        make_ai_fixtures.step("c", "activity", "Plan in 30 min", "Load controller", [1]),
        make_ai_fixtures.step("d", "approval", "Approve plan", "Duty manager", [15]),
        make_ai_fixtures.step("e", "activity", "Priya Nair re-keys report", "Load controller", [7]),
        make_ai_fixtures.step("f", "activity", "Send notification", "Cargo terminal", [4]),
        make_ai_fixtures.step("g", "activity", "Sign off", "Terminal agent", [13]),
        make_ai_fixtures.step("a", "activity", "Draft load plan again", "Load controller", [14]),
        make_ai_fixtures.step("h", "activity", "Load aircraft", "Ramp", [6]),
        make_ai_fixtures.step("i", "activity", "Load the hold", "Ramp", [6]),
        make_ai_fixtures.step("j", "activity", "No claims", "Ramp", []),
    ],
    "new_roles": [
        {"name": "Cargo terminal", "aliases": []},
        {"name": "Terminal agent", "aliases": []},
    ],
    "merge_proposals": [
        {"step_refs": ["h", "i"], "proposed_label": "Load the aircraft", "similarity": 0.55},
        {
            "step_refs": ["h", "b"],
            "proposed_label": "Merge with a rejected step",
            "similarity": 0.9,
        },
        {"step_refs": ["h", "a"], "proposed_label": "Load within 99 min", "similarity": 0.9},
    ],
}


def test_every_step_is_checked_before_it_is_kept(
    settings_config: AppConfig, tmp_path: Path
) -> None:
    for d in drafted_with(crafted(settings_config, tmp_path, BAD_STEPS)):
        tally = run(d)
        with session_scope(d.sessions) as session:
            labels = [e.label for e in map_repo.elements(session, d.version_id)]
            rejected = [
                (r.payload["text"], r.rejection_guardrail, r.rejection_reason, r.stage)
                for _, r in claims.rejected_rows(session, d.version_id)
            ]
            roles = [r.name for r in engagements.list_roles(session, d.engagement_id)]
            merges = map_repo.merge_proposals(session, d.version_id)
        assert labels == [
            "Draft load plan",
            "Load controller re-keys report",  # the name was scrubbed (G10)
            "Send notification",
            "Load aircraft",
            "Load the hold",
        ]
        assert tally.scrubbed == 1
        assert rejected == [
            ("Check fuel", "G3", "cites a claim that wasn't provided", "S2"),
            ("Plan in 30 min", "G5", "number not found in cited text: 30", "S2"),
            ("Approve plan", "G5", "role not found in cited text: Duty manager", "S2"),
            ("Sign off", "G5", "role not found in cited text: Terminal agent", "S2"),
            ("Draft load plan again", "G3", "the same step was listed twice", "S2"),
            ("No claims", "G3", "cites a claim that wasn't provided", "S2"),
        ]
        # A role the claims name ("the cargo terminal") is created; one they don't is not.
        assert "Cargo terminal" in roles and "Terminal agent" not in roles
        assert tally.roles_created == 1
        # Below 0.80 the steps stay separate and the proposal waits; proposals with a rejected
        # step or an ungrounded number are dropped.
        assert [(m.proposed_label, m.decision, m.decided_at) for m in merges] == [
            ("Load the aircraft", "pending", None)
        ]
        assert (tally.merged, tally.pending_merges) == (0, 1)


def test_a_version_without_verified_claims_needs_no_call(sample: Drafted) -> None:
    with session_scope(sample.sessions) as session:
        empty = versions.create(
            session, engagement_id=sample.engagement_id, label="v0.2", state="draft"
        )
    result = s2.canonicalise(
        sample.config, sample.sessions, context(sample.config), version_id=empty.id
    )
    assert result == Ok(s2.S2Tally())


def test_a_missing_version_is_not_found(sample: Drafted) -> None:
    result = s2.canonicalise(
        sample.config, sample.sessions, context(sample.config), version_id="nope"
    )
    assert isinstance(result, Err) and result.kind is ErrorKind.NOT_FOUND


def test_a_format_failure_saves_nothing(settings_config: AppConfig, tmp_path: Path) -> None:
    config = crafted(settings_config, tmp_path, {"steps": "nope"})
    repair = config.mock_fixtures_dir / "R_repair"
    repair.mkdir(exist_ok=True)
    (repair / "default.json").write_text('{"still": "wrong"}')
    for d in drafted_with(config):
        result = s2.canonicalise(d.config, d.sessions, context(d.config), version_id=d.version_id)
        assert isinstance(result, Err) and result.kind is ErrorKind.AI_FORMAT
        assert result.message == s2.FORMAT_FAILED
        with session_scope(d.sessions) as session:
            assert map_repo.elements(session, d.version_id) == []


def test_stable_keys_are_unique_and_readable() -> None:
    taken: set[str] = set()
    keys = [s2.stable_key(label, taken) for label in ("Draft load plan", "Draft load plan!", "?")]
    assert keys == ["draft-load-plan", "draft-load-plan-2", "step"]


def test_a_person_named_as_a_lane_or_role_becomes_their_role(
    settings_config: AppConfig, tmp_path: Path
) -> None:
    """G10: a name in Claude's answer is replaced by the mapped role before anything is checked
    or stored, so it can never reach a role, a lane or the rejected-claims register."""
    answer = {
        "steps": [
            make_ai_fixtures.step("a", "activity", "Re-key report", "Priya Nair", [7]),
            make_ai_fixtures.step("b", "activity", "Plan by Priya Nair", "Priya Nair", [6]),
        ],
        "new_roles": [{"name": "Priya Nair", "aliases": ["Priya Nair"]}],
        "merge_proposals": [],
    }
    for d in drafted_with(crafted(settings_config, tmp_path, answer)):
        run(d)
        with session_scope(d.sessions) as session:
            stored = json.dumps(
                [r.model_dump() for _, r in claims.rejected_rows(session, d.version_id)]
            )
            roles = [r.name for r in engagements.list_roles(session, d.engagement_id)]
            labels = [e.label for e in map_repo.elements(session, d.version_id)]
        assert "Priya" not in stored and "Priya Nair" not in roles
        # Both steps are kept in the Load controller lane (the speaker of the cited passages).
        assert labels == ["Re-key report", "Plan by Load controller"]
