"""S3b verifier (PRD §3.8 G6, A.6 traps T7-T8): supported, partial and not_supported claims."""

from __future__ import annotations

import dataclasses
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import AppConfig
from app.db import session_scope
from app.domain.result import Err, ErrorKind, Ok
from app.main import create_app
from app.pipeline import s2_canonicalise as s2
from app.pipeline import s3_calibrate as s3
from app.pipeline import s3b_verify as s3b
from app.pipeline.context import AiContext, ai_context
from app.repositories import claims
from app.repositories import elements as map_repo
from app.repositories.tables import AiCall, Claim
from tests import fixture_engagement
from tests.fixtures import make_ai_fixtures

Sessions = sessionmaker[Session]


@dataclasses.dataclass
class Calibrated:
    config: AppConfig
    sessions: Sessions
    version_id: str


def calibrated_with(config: AppConfig, sources: list[str]) -> Iterator[Calibrated]:
    """Drafted to S1 (the draft job), then S2 and S3: ready for the verifier."""
    app = create_app(config)
    with TestClient(app) as client:
        built = fixture_engagement.build(client, sources)
        version_id = make_ai_fixtures.draft_version(app, client, built)
        make_ai_fixtures.run_stage(app, s2.canonicalise, version_id)
        make_ai_fixtures.run_stage(app, s3.calibrate, version_id)
        yield Calibrated(config, app.state.sessions, version_id)


@pytest.fixture()
def sample(settings_config: AppConfig) -> Iterator[Calibrated]:
    yield from calibrated_with(settings_config, fixture_engagement.SOURCES)


@pytest.fixture()
def traps(settings_config: AppConfig) -> Iterator[Calibrated]:
    config = dataclasses.replace(settings_config, mock_fixtures_dir=make_ai_fixtures.TRAPS)
    yield from calibrated_with(config, make_ai_fixtures.TRAP_SOURCES)


def context(config: AppConfig, **changes: object) -> AiContext:
    result = ai_context(config)
    assert isinstance(result, Ok)
    return dataclasses.replace(result.value, **changes)  # type: ignore[arg-type]


def run(c: Calibrated, **changes: object) -> s3b.S3bTally:
    result = s3b.verify(c.config, c.sessions, context(c.config, **changes), version_id=c.version_id)
    assert isinstance(result, Ok), result
    return result.value


def verdict_counts(c: Calibrated) -> dict[str, int]:
    with session_scope(c.sessions) as session:
        rows = session.execute(
            select(Claim.verifier_verdict, func.count())
            .where(Claim.version_id == c.version_id, Claim.stage != "S3")
            .group_by(Claim.verifier_verdict)
        )
        return {verdict: count for verdict, count in rows}


def calls(c: Calibrated) -> int:
    with session_scope(c.sessions) as session:
        return session.scalar(select(func.count()).select_from(AiCall)) or 0


def test_every_sample_step_has_a_verifier_answer(sample: Calibrated) -> None:
    hashes = make_ai_fixtures.s3b_hashes(sample.sessions, sample.version_id)
    assert len(hashes) == 8
    folder = make_ai_fixtures.MOCKS / s3b.STAGE_ID
    assert [k for k, (h, _) in hashes.items() if not (folder / f"{h}.json").exists()] == []


def test_the_sample_is_supported_throughout(sample: Calibrated) -> None:
    tally = run(sample)
    assert (tally.supported, tally.partial, tally.rejected, tally.removed_steps) == (21, 0, 0, 0)
    with session_scope(sample.sessions) as session:
        elements = map_repo.elements(session, sample.version_id)
    assert len(elements) == 8 and not any(e.needs_check for e in elements)
    assert verdict_counts(sample)["supported"] == 21


def test_trap_t7_is_rejected_by_the_verifier_and_t8_needs_a_check(traps: Calibrated) -> None:
    tally = run(traps)
    assert (tally.partial, tally.rejected, tally.removed_steps) == (1, 1, 1)
    with session_scope(traps.sessions) as session:
        elements = map_repo.elements(session, traps.version_id)
        register = [
            (r.payload["text"], r.rejection_guardrail, r.stage, r.rejection_reason)
            for _, r in claims.rejected_rows(session, traps.version_id)
        ]
        linked = map_repo.element_claims(session, traps.version_id)
    # T8: the step stays, marked for a check (S5 turns it into a validation question).
    assert [(e.label, e.needs_check) for e in elements] == [("Build preliminary plan", True)]
    assert len(linked[elements[0].id]) == 1
    # T7: listed in the register as rejected by the verifier; its step is gone.
    assert (
        "Control: the Load controller builds the preliminary load plan.",
        "G6",
        "S3b",
        "independent verifier: T7: the passage doesn't say this.",
    ) in register


def test_switching_the_verifier_off_makes_no_calls(sample: Calibrated) -> None:
    before = calls(sample)
    tally = run(sample, verifier_enabled=False)
    assert (tally.not_run, tally.supported) == (21, 0)
    assert calls(sample) == before
    assert verdict_counts(sample) == {"not_run": 21}


def test_a_claim_without_a_verdict_is_checked_not_assumed(
    settings_config: AppConfig, tmp_path: Path
) -> None:
    folder = tmp_path / "mocks"
    shutil.copytree(make_ai_fixtures.MOCKS, folder)
    shutil.rmtree(folder / s3b.STAGE_ID)
    (folder / s3b.STAGE_ID).mkdir()
    (folder / s3b.STAGE_ID / "default.json").write_text('{"verdicts": []}')
    config = dataclasses.replace(settings_config, mock_fixtures_dir=folder)
    for c in calibrated_with(config, fixture_engagement.SOURCES):
        tally = run(c)
        assert tally.supported == 0 and tally.partial > 0
        with session_scope(c.sessions) as session:
            assert all(e.needs_check for e in map_repo.elements(session, c.version_id))
            reasons = {
                r.verifier_reason
                for r in session.scalars(select(Claim).where(Claim.verifier_verdict == "partial"))
            }
        assert reasons == {s3b.NO_VERDICT}


def test_a_format_failure_changes_nothing(settings_config: AppConfig, tmp_path: Path) -> None:
    folder = tmp_path / "mocks"
    shutil.copytree(make_ai_fixtures.MOCKS, folder)
    shutil.rmtree(folder / s3b.STAGE_ID)
    (folder / s3b.STAGE_ID).mkdir()
    (folder / s3b.STAGE_ID / "default.json").write_text('{"verdicts": "nope"}')
    (folder / "R_repair").mkdir(exist_ok=True)
    (folder / "R_repair" / "default.json").write_text('{"still": "wrong"}')
    config = dataclasses.replace(settings_config, mock_fixtures_dir=folder)
    for c in calibrated_with(config, fixture_engagement.SOURCES):
        result = s3b.verify(c.config, c.sessions, context(c.config), version_id=c.version_id)
        assert isinstance(result, Err) and result.message == s3b.FORMAT_FAILED
        assert verdict_counts(c) == {"not_run": verdict_counts(c).get("not_run", 0)}


def test_a_missing_version_is_not_found(sample: Calibrated) -> None:
    result = s3b.verify(sample.config, sample.sessions, context(sample.config), version_id="x")
    assert isinstance(result, Err) and result.kind is ErrorKind.NOT_FOUND
