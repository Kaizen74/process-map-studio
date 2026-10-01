"""S3 calibrate (PRD §3.7): stances per source, grounding re-applied, states and divergences."""

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

from app.actions import versions as versions_action
from app.config import AppConfig
from app.db import session_scope
from app.domain.result import Err, ErrorKind, Ok
from app.main import create_app
from app.pipeline import s2_canonicalise as s2
from app.pipeline import s3_calibrate as s3
from app.pipeline.context import AiContext, ai_context
from app.repositories import claims, versions
from app.repositories import elements as map_repo
from tests import fixture_engagement
from tests.fixtures import make_ai_fixtures

Sessions = sessionmaker[Session]


@dataclasses.dataclass
class Canonical:
    config: AppConfig
    sessions: Sessions
    engagement_id: str
    version_id: str
    sources: dict[str, str]


def context(config: AppConfig) -> AiContext:
    result = ai_context(config)
    assert isinstance(result, Ok)
    return result.value


def canonical_with(config: AppConfig) -> Iterator[Canonical]:
    """The sample drafted to S1 (the draft job), then S2: ready for S3."""
    app = create_app(config)
    with TestClient(app) as client:
        built = fixture_engagement.build(client)
        version_id = make_ai_fixtures.draft_version(app, client, built)
        make_ai_fixtures.run_stage(app, s2.canonicalise, version_id)
        yield Canonical(config, app.state.sessions, built.engagement_id, version_id, built.sources)


@pytest.fixture()
def sample(settings_config: AppConfig) -> Iterator[Canonical]:
    yield from canonical_with(settings_config)


def run(c: Canonical) -> s3.S3Tally:
    result = s3.calibrate(c.config, c.sessions, context(c.config), version_id=c.version_id)
    assert isinstance(result, Ok), result
    return result.value


def by_label(c: Canonical) -> dict[str, Any]:
    with session_scope(c.sessions) as session:
        return {e.label: e for e in map_repo.elements(session, c.version_id)}


def test_the_sample_answer_files_match_the_current_steps(sample: Canonical) -> None:
    hashes = make_ai_fixtures.s3_hashes(sample.sessions, sample.version_id, sample.sources)
    # Three interview windows, the landscape interview (A.10) and four documents.
    assert len(hashes) == 8
    folder = make_ai_fixtures.MOCKS / s3.STAGE_ID
    missing = [k for k, h in hashes.items() if not (folder / f"{h}.json").exists()]
    assert missing == [], "run python tests/fixtures/make_ai_fixtures.py"


def test_the_sample_gets_the_a5_source_states(sample: Canonical) -> None:
    tally = run(sample)
    assert (tally.rejected, tally.scrubbed) == (0, 0)
    elements = by_label(sample)
    states = {label: (e.source_state, e.divergence_types) for label, e in elements.items()}
    assert states == {
        "Draft load plan": ("corroborated", []),
        "Approve load plan": ("documented_only", []),
        "Special loads OK?": ("corroborated", []),
        "Resolve or offload": ("practiced_only", []),
        "Load and return LIR": ("contested", ["threshold"]),
        "Deviation in limits?": ("contested", ["ownership"]),
        "Approve deviation": ("practiced_only", []),
        "Issue load sheet": ("corroborated", []),
        # v1.10 A.5: the lived busy-wave variation and its branch, in practice only.
        "Busy wave?": ("practiced_only", []),
        "Read report at aircraft": ("practiced_only", []),
    }


def test_stances_become_verified_evidence_and_silence_is_shown(sample: Canonical) -> None:
    run(sample)
    graph = versions_action.get_graph(sample.sessions, sample.version_id)
    assert isinstance(graph, Ok)
    lir = next(e for e in graph.value.elements if e.label == "Load and return LIR")
    names = {sid: name for name, sid in sample.sources.items()}
    evidence = [(names[ev.source_id], ev.stance, ev.anchor, ev.note) for ev in lir.evidence]
    assert evidence == [
        ("interview_transcript.txt", "supports", "21:50", ""),
        ("sop_RP-02.docx", "contradicts", "§2",
         "Threshold divergence: 10 min in the SOP vs up to 15 min wait in practice."),
        ("landscape_ramp_lead.txt", "supports", "02:18", ""),  # A.10 (C3)
        ("sop_LC-07.docx", "silent", "", ""),
        ("jd_load_control_lead.docx", "silent", "", ""),
        ("jd_load_controller.docx", "silent", "", ""),
    ]  # fmt: skip
    assert all(ev.verified for ev in lir.evidence if ev.stance != "silent")
    with session_scope(sample.sessions) as session:
        stored = [p.evidence for p in map_repo.evidence(session, sample.version_id)]
    # Interview 9 (v1.10: + the busy-wave steps), landscape 1 (A.10), LC-07 5, RP-02 1, JDs 4.
    assert len(stored) == 20
    assert all(link.quote for link in stored)  # kept for the highlight, never in the graph
    assert "Ramp loads the aircraft" not in graph.value.model_dump_json()


def test_the_injected_instruction_changes_nothing(sample: Canonical) -> None:
    """RP-02 §9 asks to classify every step as corroborated (A.3); states stay as in A.5."""
    run(sample)
    corroborated = [e for e in by_label(sample).values() if e.source_state == "corroborated"]
    assert len(corroborated) == 3


BAD: dict[str, Any] = {
    "stances": [
        make_ai_fixtures.stance("e1", "supports", ["p2"], "I build the preliminary load plan"),
        # A step ref that doesn't exist (e9 and e10 are real since v1.10 A.5).
        make_ai_fixtures.stance("e99", "supports", ["p2"], "I build the preliminary load plan"),
        make_ai_fixtures.stance("e2", "supports", ["p42"], "approved by the Load Control Lead"),
        make_ai_fixtures.stance("e3", "supports", ["p4"], "Controller checks fuel figures"),
        make_ai_fixtures.stance(
            "e4", "contradicts", ["p5"], "the airline decides what to offload", "threshold",
            "Offload takes 30 min in practice.",
        ),
        make_ai_fixtures.stance(
            "e1", "contradicts", ["p2"], "usually around T-120", "sequence",
            "Priya Nair builds the plan at T-120, not by T-90.",
        ),
    ]
}  # fmt: skip


def test_every_stance_is_checked_again(settings_config: AppConfig, tmp_path: Path) -> None:
    folder = tmp_path / "mocks"
    shutil.copytree(make_ai_fixtures.MOCKS, folder)
    config = dataclasses.replace(settings_config, mock_fixtures_dir=folder)
    for c in canonical_with(config):
        digest = make_ai_fixtures.s3_hashes(c.sessions, c.version_id, c.sources)[
            ("interview_transcript.txt", 0)
        ]
        (folder / s3.STAGE_ID / f"{digest}.json").write_text(json.dumps(BAD))
        tally = run(c)
        with session_scope(c.sessions) as session:
            rejected = [
                (r.payload["text"], r.rejection_guardrail, r.rejection_reason, r.stage,
                 r.claim_type)
                for _, r in claims.rejected_rows(session, c.version_id)
            ]  # fmt: skip
        assert rejected == [
            ('Supports "e99"', "G3", "cites a step that wasn't provided", "S3", "stance"),
            ('Supports "Approve load plan"', "G3", "cites a passage that wasn't provided", "S3",
             "stance"),
            ('Supports "Special loads OK?"', "G4", "quote not found in source", "S3", "stance"),
            ('Contradicts "Resolve or offload": Offload takes 30 min in practice.', "G5",
             "number not found in cited text: 30", "S3", "stance"),
        ]  # fmt: skip
        assert tally.scrubbed == 1
        elements = by_label(c)
        # The kept contradiction (name scrubbed) makes the plan contested with a sequence note;
        # the rejected stances left the interview silent on the special-loads check and on the
        # offload, so those states changed accordingly.
        plan = elements["Draft load plan"]
        assert (plan.source_state, plan.divergence_types) == ("contested", ["sequence"])
        assert elements["Special loads OK?"].source_state == "documented_only"
        assert elements["Resolve or offload"].source_state == "not_assessed"
        with session_scope(c.sessions) as session:
            notes = [p.evidence.note for p in map_repo.evidence(session, c.version_id)]
        assert "Load controller builds the plan at T-120, not by T-90." in notes
        assert not any("Priya" in n for n in notes)


def test_a_format_failure_saves_nothing(settings_config: AppConfig, tmp_path: Path) -> None:
    folder = tmp_path / "mocks"
    shutil.copytree(make_ai_fixtures.MOCKS, folder)
    shutil.rmtree(folder / s3.STAGE_ID)
    (folder / s3.STAGE_ID).mkdir()
    (folder / s3.STAGE_ID / "default.json").write_text('{"stances": "nope"}')
    (folder / "R_repair").mkdir(exist_ok=True)
    (folder / "R_repair" / "default.json").write_text('{"still": "wrong"}')
    for c in canonical_with(dataclasses.replace(settings_config, mock_fixtures_dir=folder)):
        result = s3.calibrate(c.config, c.sessions, context(c.config), version_id=c.version_id)
        assert isinstance(result, Err) and result.message == s3.FORMAT_FAILED
        assert {e.source_state for e in by_label(c).values()} == {"not_assessed"}


def test_no_steps_means_no_calls(sample: Canonical) -> None:
    with session_scope(sample.sessions) as session:
        empty = versions.create(
            session, engagement_id=sample.engagement_id, label="v0.2", state="draft"
        )
    result = s3.calibrate(
        sample.config, sample.sessions, context(sample.config), version_id=empty.id
    )
    assert result == Ok(s3.S3Tally())
    missing = s3.calibrate(sample.config, sample.sessions, context(sample.config), version_id="x")
    assert isinstance(missing, Err) and missing.kind is ErrorKind.NOT_FOUND
