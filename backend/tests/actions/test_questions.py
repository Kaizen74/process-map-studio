"""S5 questions (PRD §3.7, §3.8 G7-G8, A.6 T8): who needs asking, and every unknown kept."""

from __future__ import annotations

import dataclasses
import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import AppConfig
from app.db import session_scope
from app.domain.graph import ElementRecord
from app.domain.result import Err, ErrorKind, Ok
from app.main import create_app
from app.pipeline import s2_canonicalise as s2
from app.pipeline import s3_calibrate as s3
from app.pipeline import s3b_verify as s3b
from app.pipeline import s4_assemble as s4
from app.pipeline import s5_questions as s5
from app.pipeline.context import AiContext, ai_context
from app.pipeline.s3_calibrate import StepRef
from app.repositories import elements as map_repo
from app.repositories import versions
from app.repositories.tables import AiCall
from tests import fixture_engagement
from tests.fixtures import make_ai_fixtures

Sessions = sessionmaker[Session]


@dataclasses.dataclass
class Assembled:
    config: AppConfig
    sessions: Sessions
    engagement_id: str
    version_id: str


def assembled_with(config: AppConfig, sources: list[str]) -> Iterator[Assembled]:
    app = create_app(config)
    with TestClient(app) as client:
        built = fixture_engagement.build(client, sources)
        version_id = make_ai_fixtures.draft_version(app, client, built)
        for stage in (s2.canonicalise, s3.calibrate, s3b.verify, s4.assemble):
            make_ai_fixtures.run_stage(app, stage, version_id)
        yield Assembled(config, app.state.sessions, built.engagement_id, version_id)


@pytest.fixture()
def sample(settings_config: AppConfig) -> Iterator[Assembled]:
    yield from assembled_with(settings_config, fixture_engagement.SOURCES)


def context(config: AppConfig) -> AiContext:
    result = ai_context(config)
    assert isinstance(result, Ok)
    return result.value


def run(a: Assembled) -> s5.S5Tally:
    result = s5.ask(a.config, a.sessions, context(a.config), version_id=a.version_id)
    assert isinstance(result, Ok), result
    return result.value


def questions(a: Assembled) -> list[tuple[str, str, str | None, str | None]]:
    """(reason, question, step label, phase name) in the order stored."""
    with session_scope(a.sessions) as session:
        labels = {e.id: e.label for e in map_repo.elements(session, a.version_id)}
        phases = {p.id: p.name for p in map_repo.phases(session, a.version_id)}
        return [
            (q.reason, q.question, labels.get(q.element_id or ""), phases.get(q.phase_id or ""))
            for q in map_repo.questions(session, a.version_id)
        ]


def test_the_sample_answer_file_matches(sample: Assembled) -> None:
    digest = make_ai_fixtures.s5_hash(sample.sessions, sample.version_id)
    assert (make_ai_fixtures.MOCKS / s5.STAGE_ID / f"{digest}.json").exists()


def test_the_sample_gets_its_questions_and_every_unknown(sample: Assembled) -> None:
    tally = run(sample)
    assert (tally.questions, tally.gaps, tally.templated) == (5, 2, 0)
    found = questions(sample)
    assert [(r, label, phase) for r, _, label, phase in found] == [
        ("documented_only", "Approve load plan", "Plan"),
        ("contested", "Load and return LIR", "Check and load"),
        ("contested", "Deviation in limits?", "Close out"),
        ("gap", None, None),
        ("gap", None, None),
    ]
    assert found[1][1].startswith("The SOP asks for the loading report within 10 minutes")
    # G8: the unknowns are asked as Claude raised them, never turned into steps.
    assert [q for r, q, _, _ in found if r == "gap"] == [
        "Who approves the preliminary load plan before it is released?",
        "Which role issues the final load sheet?",
    ]


def test_trap_t8_partial_support_gets_a_question(settings_config: AppConfig) -> None:
    config = dataclasses.replace(settings_config, mock_fixtures_dir=make_ai_fixtures.TRAPS)
    for a in assembled_with(config, make_ai_fixtures.TRAP_SOURCES):
        tally = run(a)
        assert tally.templated == 1
        assert questions(a) == [
            (
                "partial_support",
                'The independent check found only partial support for "Build preliminary plan". '
                "Is it described correctly?",
                "Build preliminary plan",
                None,
            )
        ]


def test_ungrounded_numbers_fall_back_and_names_are_scrubbed(
    settings_config: AppConfig, tmp_path: Path
) -> None:
    folder = tmp_path / "mocks"
    shutil.copytree(make_ai_fixtures.MOCKS, folder)
    shutil.rmtree(folder / s5.STAGE_ID)
    (folder / s5.STAGE_ID).mkdir()
    answer = {
        "questions": [
            {"ref": "q1", "question": "Is the plan approved within 30 minutes?"},
            {"ref": "q2", "question": "Should we ask Priya Nair about the loading report?"},
            {"ref": "q9", "question": "A question for a step nobody asked about?"},
        ]
    }
    (folder / s5.STAGE_ID / "default.json").write_text(json.dumps(answer))
    config = dataclasses.replace(settings_config, mock_fixtures_dir=folder)
    for a in assembled_with(config, fixture_engagement.SOURCES):
        tally = run(a)
        assert tally.templated == 2  # q1 (30 isn't stated) and q3 (not answered)
        found = [q for _, q, _, _ in questions(a)][:3]
        assert found == [
            'The documents describe "Approve load plan", but the interview doesn\'t mention it. '
            "Is it done in practice?",
            "Should we ask Load controller about the loading report?",
            'The sources disagree about "Deviation in limits?". Which version is right in '
            "practice?",
        ]


def test_at_most_six_step_questions_per_phase(sample: Assembled) -> None:
    with session_scope(sample.sessions) as session:
        elements = map_repo.elements(session, sample.version_id)
        phase = map_repo.phases(session, sample.version_id)[0].id
        for e in elements:
            map_repo.update_element(session, e.id, {"source_state": "contested", "phase_id": phase})
        assert len(s5.needed(session, sample.version_id)) == 6


def test_reasons_follow_the_priority_order() -> None:
    def ref(**fields: object) -> StepRef:
        element = ElementRecord.model_validate(
            {"stable_key": "x", "kind": "activity", "label": "X", "provenance": "O", **fields}
        )
        return StepRef(ref="e1", element=element, lane="", claims=())

    assert s5.reason_for(ref(source_state="trace_contradicted", needs_check=True)) == "contested"
    assert s5.reason_for(ref(source_state="documented_only", provenance="I")) == "documented_only"
    assert s5.reason_for(ref(provenance="I", needs_check=True)) == "inferred"
    assert s5.reason_for(ref(needs_check=True, confidence=0.2)) == "partial_support"
    assert s5.reason_for(ref(confidence=0.45)) == "low_confidence"
    assert s5.reason_for(ref(confidence=0.5, source_state="corroborated")) is None


def test_no_step_needing_a_question_means_no_call(sample: Assembled) -> None:
    with session_scope(sample.sessions) as session:
        empty = versions.create(
            session, engagement_id=sample.engagement_id, label="v0.2", state="draft"
        )
        before = session.scalar(select(func.count()).select_from(AiCall))
    result = s5.ask(sample.config, sample.sessions, context(sample.config), version_id=empty.id)
    assert result == Ok(s5.S5Tally())
    with session_scope(sample.sessions) as session:
        assert session.scalar(select(func.count()).select_from(AiCall)) == before
    missing = s5.ask(sample.config, sample.sessions, context(sample.config), version_id="x")
    assert isinstance(missing, Err) and missing.kind is ErrorKind.NOT_FOUND


def test_a_format_failure_saves_nothing(settings_config: AppConfig, tmp_path: Path) -> None:
    folder = tmp_path / "mocks"
    shutil.copytree(make_ai_fixtures.MOCKS, folder)
    shutil.rmtree(folder / s5.STAGE_ID)
    (folder / s5.STAGE_ID).mkdir()
    (folder / s5.STAGE_ID / "default.json").write_text('{"questions": "nope"}')
    (folder / "R_repair").mkdir(exist_ok=True)
    (folder / "R_repair" / "default.json").write_text('{"still": "wrong"}')
    config = dataclasses.replace(settings_config, mock_fixtures_dir=folder)
    for a in assembled_with(config, fixture_engagement.SOURCES):
        result = s5.ask(a.config, a.sessions, context(a.config), version_id=a.version_id)
        assert isinstance(result, Err) and result.message == s5.FORMAT_FAILED
        assert questions(a) == []


def test_a_documents_only_map_never_mentions_a_missing_interview(
    settings_config: AppConfig, tmp_path: Path
) -> None:
    """Eric, 2026-10-20: with no interview behind the map, the fallback wording for a step only
    the documents describe says no interview has described it yet."""
    folder = tmp_path / "mocks"
    shutil.copytree(make_ai_fixtures.MOCKS, folder)
    shutil.rmtree(folder / s5.STAGE_ID)
    (folder / s5.STAGE_ID).mkdir()
    (folder / s5.STAGE_ID / "default.json").write_text('{"questions": []}')
    config = dataclasses.replace(settings_config, mock_fixtures_dir=folder)
    for a in assembled_with(config, make_ai_fixtures.DOCUMENTS_ONLY):
        tally = run(a)
        assert tally.templated == 6
        found = [(r, q) for r, q, _, _ in questions(a) if r == "documented_only"]
        assert found[1] == (
            "documented_only",
            'The documents describe "Approve load plan"; no interview has described it yet. Is '
            "it done this way in practice?",
        )
        assert all("interview doesn't" not in q for _, q in found)


def test_the_documents_only_sample_gets_a_question_for_every_step(
    settings_config: AppConfig,
) -> None:
    for a in assembled_with(settings_config, make_ai_fixtures.DOCUMENTS_ONLY):
        tally = run(a)
        assert (tally.questions, tally.gaps, tally.templated) == (7, 1, 0)
        assert [(r, label) for r, _, label, _ in questions(a)] == [
            ("documented_only", "Draft load plan"),
            ("documented_only", "Approve load plan"),
            ("documented_only", "Special loads OK?"),
            ("documented_only", "Return loading report"),
            ("documented_only", "Deviation in limits?"),
            ("documented_only", "Issue load sheet"),
            ("gap", None),
        ]
