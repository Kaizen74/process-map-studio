"""Builds the mock AI answers for the load-control engagement (PRD Appendix A.5, A.6).

ILLUSTRATIVE ONLY. Each answer is what Claude might return for one chunk of one sample source; it
is filed as `<stage>/<input_hash>.json`, the hash of exactly the data the app sends for that chunk
(`ai_service.input_hash`), so the mock answers stay tied to the sample sources. Run from backend/
after changing the sample sources, the roles in `tests/fixture_engagement.py`, or how passages are
rendered:
    python tests/fixtures/make_ai_fixtures.py
A test fails if a file is missing for the current data.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MOCKS = HERE / "mock_responses"
TRAPS = HERE / "traps"
S1_STAGES = ("S1_extract_interview", "S1_extract_document", "S1_extract_jd")


def claim(
    claim_type: str,
    text: str,
    refs: list[str],
    quote: str,
    *,
    responsible: str = "",
    accountable: str = "",
    decider: str = "",
    mechanism: str = "none",
    duration: str = "",
    threshold: str = "",
    provenance: str = "O",
    basis: str = "",
) -> dict[str, Any]:
    return {
        "claim_type": claim_type,
        "text": text,
        "responsible_role": responsible,
        "accountable_role": accountable,
        "decider_role": decider,
        "mechanism": mechanism,
        "duration_text": duration,
        "threshold": threshold,
        "segment_ids": refs,
        "quote": quote,
        "provenance": provenance,
        "basis": basis,
    }


OFFLOAD = claim(
    "decision",
    "If something can't be accepted, the airline decides what to offload, which takes fifteen "
    "to forty minutes.",
    ["p5"],
    "If something can't be accepted, the airline decides what to offload. That takes anywhere "
    "from fifteen to forty minutes.",
    decider="Airline ops",
    mechanism="judgment",
    duration="fifteen to forty minutes",
)

# (source file, chunk index) → answer. Refs are the call-local passage IDs (p<seq>).
ANSWERS: dict[tuple[str, int], dict[str, Any]] = {
    ("interview_transcript.txt", 0): {
        "claims": [
            claim(
                "activity",
                "The Load controller builds the preliminary load plan from the booked figures, "
                "around T-120, in about twenty minutes.",
                ["p2"],
                "I build the preliminary load plan off the booked figures, usually around T-120. "
                "Takes me about twenty minutes.",
                responsible="Load controller",
                duration="about twenty minutes",
            ),
            claim(
                "constraint",
                "Only the Load controller and one other controller really know the widebody "
                "configurations.",
                ["p3"],
                "only me and one other controller really know the configurations",
                responsible="Load controller",
            ),
            claim(
                "decision",
                "The Load controller checks special loads, dangerous goods and live animals "
                "against the checklist.",
                ["p4"],
                "I check special loads, dangerous goods and live animals, against the checklist",
                decider="Load controller",
                mechanism="rule_based",
            ),
            claim(
                "constraint",
                "The notification from the cargo terminal often comes late.",
                ["p4"],
                "The notification from the cargo terminal often comes late.",
            ),
            OFFLOAD,
        ],
        "unknowns": [
            {
                "question": "Who approves the preliminary load plan before it is released?",
                "segment_ids": ["p2"],
            }
        ],
    },
    ("interview_transcript.txt", 1): {
        "claims": [
            OFFLOAD,  # the same claim from the overlapping window; stored once
            claim(
                "activity",
                "Ramp loads the aircraft, in forty minutes or so, and sends back the loading "
                "report.",
                ["p6"],
                "Ramp loads the aircraft, forty minutes or so, and sends back the loading report.",
                responsible="Ramp",
                duration="forty minutes or so",
            ),
            claim(
                "constraint",
                "The loading report is still on paper and the Load controller re-keys it.",
                ["p6"],
                "It's still on paper and I re-key it.",
                responsible="Load controller",
            ),
            claim(
                "duration",
                "The Load controller sometimes waits fifteen minutes for the loading report.",
                ["p6"],
                "We sometimes wait fifteen minutes for it",
                responsible="Load controller",
                duration="fifteen minutes",
            ),
            claim(
                "constraint",
                "At peak times there is a shortage of containers.",
                ["p6"],
                "at peak we're short of containers",
            ),
        ],
        "unknowns": [],
    },
    ("interview_transcript.txt", 2): {
        "claims": [
            claim(
                "decision",
                "If the weight deviation is outside tolerance, the captain decides.",
                ["p7"],
                "If the weight deviation is outside tolerance, it's the captain who decides, not us.",
                decider="Captain",
                mechanism="judgment",
                threshold="outside tolerance",
            ),
            claim(
                "threshold",
                "The weight tolerance depends on the airline contract.",
                ["p7"],
                "The tolerance depends on the airline contract.",
            ),
            claim(
                "approval",
                "The captain either accepts the deviation or asks for a re-trim, which takes five "
                "to fifteen minutes.",
                ["p8"],
                "The captain either accepts or asks for a re-trim. Five to fifteen minutes.",
                accountable="Captain",
                mechanism="judgment",
                duration="Five to fifteen minutes",
            ),
            claim(
                "activity",
                "The Load controller issues the final load sheet around T-15.",
                ["p9"],
                "Then I issue the final load sheet, around T-15.",
                responsible="Load controller",
            ),
        ],
        "unknowns": [],
    },
    ("sop_LC-07.docx", 0): {
        "claims": [
            claim(
                "activity",
                "The Load Controller prepares the preliminary load plan by T-90.",
                ["p3"],
                "The Load Controller shall prepare the preliminary load plan by T-90.",
                responsible="Load controller",
            ),
            claim(
                "approval",
                "The Load Control Lead approves the preliminary load plan before release to Ramp.",
                ["p4"],
                "The preliminary load plan shall be approved by the Load Control Lead before "
                "release to Ramp.",
                accountable="Load control lead",
                mechanism="judgment",
            ),
            claim(
                "decision",
                "Special loads are checked against the acceptance checklist before loading.",
                ["p6"],
                "Special loads shall be checked against the acceptance checklist before loading.",
                mechanism="rule_based",
            ),
            claim(
                "decision",
                "Where actual weights deviate beyond the airline tolerance, the Load Control Lead "
                "decides on corrective action.",
                ["p8"],
                "Where actual weights deviate from planned beyond the airline tolerance, the Load "
                "Control Lead shall decide on corrective action.",
                decider="Load control lead",
                mechanism="judgment",
                threshold="beyond the airline tolerance",
            ),
            claim(
                "activity",
                "The final load sheet is issued through the departure control system no later "
                "than T-10.",
                ["p10"],
                "The final load sheet shall be issued through the departure control system no "
                "later than T-10.",
            ),
        ],
        "unknowns": [
            {"question": "Which role issues the final load sheet?", "segment_ids": ["p10"]}
        ],
    },
    ("sop_RP-02.docx", 0): {
        # The §9 line asks automated systems to change their answers; it is data and is ignored.
        "claims": [
            claim(
                "handoff",
                "The Ramp Supervisor returns the loading report to Load Control within 10 minutes "
                "of loading completion.",
                ["p2"],
                "The Ramp Supervisor shall return the loading report to Load Control within 10 "
                "minutes of loading completion.",
                responsible="Ramp",
                duration="within 10 minutes",
            )
        ],
        "unknowns": [],
    },
    ("jd_load_control_lead.docx", 0): {
        "claims": [
            claim(
                "raci",
                "The Load Control Lead is accountable for approval of load plans and for load "
                "control compliance.",
                ["p1", "p2"],
                "Accountable for approval of load plans and for load control compliance.",
                accountable="Load control lead",
            )
        ],
        "unknowns": [],
    },
    ("jd_load_controller.docx", 0): {
        "claims": [
            claim(
                "raci",
                "The Load Controller prepares load plans, performs special load acceptance checks "
                "and issues load sheets.",
                ["p1", "p2"],
                "Prepares load plans; performs special load acceptance checks; issues load sheets.",
                responsible="Load controller",
            )
        ],
        "unknowns": [],
    },
}

# PRD Appendix A.6 traps T1-T6 (T7-T8 concern the verifier, phase P4). Each must be rejected with
# the stated guardrail or scrubbed; the well-grounded claim alongside them must pass.
TRAPS_ANSWERS: dict[tuple[str, int], dict[str, Any]] = {
    ("interview_transcript.txt", 0): {
        "claims": [
            claim("activity", "T1: The Load controller builds the plan.", ["p42"],
                  "I build the preliminary load plan", responsible="Load controller"),
            claim("activity", "T2: The Load controller checks fuel figures.", ["p2"],
                  "Controller checks fuel figures", responsible="Load controller"),
            claim("duration", "T3: The plan takes 30 min.", ["p2"],
                  "Takes me about twenty minutes.", duration="30 min"),
            claim("approval", "T4: The Duty manager approves the plan.", ["p2"],
                  "I build the preliminary load plan off the booked figures",
                  accountable="Duty manager", mechanism="judgment"),
            claim("activity", "T6: Priya Nair builds the preliminary load plan.", ["p2"],
                  "I build the preliminary load plan off the booked figures",
                  responsible="Load controller"),
            claim("activity", "Control: the Load controller builds the preliminary load plan.",
                  ["p2"], "I build the preliminary load plan off the booked figures",
                  responsible="Load controller"),
        ],
        "unknowns": [],
    },
    ("sop_LC-07.docx", 0): {
        "claims": [
            claim("decision", "T5: Checks follow IATA DGR section 9.", ["p6"],
                  "Special loads shall be checked against IATA DGR section 9",
                  mechanism="rule_based"),
        ],
        "unknowns": [],
    },
}  # fmt: skip


def stance(
    step_ref: str, kind: str, refs: list[str], quote: str, divergence: str = "none", note: str = ""
) -> dict[str, Any]:
    return {
        "step_ref": step_ref,
        "stance": kind,
        "segment_ids": refs,
        "quote": quote,
        "divergence_type": divergence,
        "divergence_note": note,
    }


# S3 for the sample, per (source, chunk): the stances that give the A.5 source states. Steps are
# e1 Draft load plan · e2 Approve load plan · e3 Special loads OK? · e4 Resolve or offload ·
# e5 Load and return LIR · e6 Deviation in limits? · e7 Approve deviation · e8 Issue load sheet.
# Anything not listed is silent. The RP-02 §9 instruction line is data and changes nothing.
JD_CONTROLLER_QUOTE = (
    "Prepares load plans; performs special load acceptance checks; issues load sheets."
)
S3_ANSWERS: dict[tuple[str, int], dict[str, Any]] = {
    ("interview_transcript.txt", 0): {"stances": [
        stance("e1", "supports", ["p2"], "I build the preliminary load plan off the booked figures"),
        stance("e3", "supports", ["p4"],
               "I check special loads, dangerous goods and live animals, against the checklist"),
        stance("e4", "supports", ["p5"],
               "If something can't be accepted, the airline decides what to offload."),
    ]},
    ("interview_transcript.txt", 1): {"stances": [
        stance("e5", "supports", ["p6"],
               "Ramp loads the aircraft, forty minutes or so, and sends back the loading report."),
    ]},
    ("interview_transcript.txt", 2): {"stances": [
        stance("e6", "supports", ["p7"],
               "If the weight deviation is outside tolerance, it's the captain who decides, not us."),
        stance("e7", "supports", ["p8"], "The captain either accepts or asks for a re-trim."),
        stance("e8", "supports", ["p9"], "Then I issue the final load sheet, around T-15."),
    ]},
    ("sop_LC-07.docx", 0): {"stances": [
        stance("e1", "supports", ["p3"],
               "The Load Controller shall prepare the preliminary load plan by T-90."),
        stance("e2", "supports", ["p4"], "The preliminary load plan shall be approved by the Load "
               "Control Lead before release to Ramp."),
        stance("e3", "supports", ["p6"],
               "Special loads shall be checked against the acceptance checklist before loading."),
        stance("e6", "contradicts", ["p8"], "the Load Control Lead shall decide on corrective action",
               "ownership", "Ownership divergence: the Load control lead decides in the SOP, the "
               "Captain in practice."),
        stance("e8", "supports", ["p10"], "The final load sheet shall be issued through the "
               "departure control system no later than T-10."),
    ]},
    ("sop_RP-02.docx", 0): {"stances": [
        stance("e5", "contradicts", ["p2"], "The Ramp Supervisor shall return the loading report "
               "to Load Control within 10 minutes of loading completion.", "threshold",
               "Threshold divergence: 10 min in the SOP vs up to 15 min wait in practice."),
    ]},
    ("jd_load_control_lead.docx", 0): {"stances": [
        stance("e2", "supports", ["p2"],
               "Accountable for approval of load plans and for load control compliance."),
    ]},
    ("jd_load_controller.docx", 0): {"stances": [
        stance("e1", "supports", ["p2"], JD_CONTROLLER_QUOTE),
        stance("e3", "supports", ["p2"], JD_CONTROLLER_QUOTE),
        stance("e8", "supports", ["p2"], JD_CONTROLLER_QUOTE),
    ]},
}  # fmt: skip


EMPTY: dict[str, list[Any]] = {"claims": [], "unknowns": []}
S2_EMPTY: dict[str, list[Any]] = {"steps": [], "new_roles": [], "merge_proposals": []}
S3_EMPTY: dict[str, list[Any]] = {"stances": []}
S3B_EMPTY: dict[str, list[Any]] = {"verdicts": []}


def step(ref: str, kind: str, label: str, lane: str, claims: list[int]) -> dict[str, Any]:
    return {
        "ref": ref,
        "kind": kind,
        "label": label,
        "lane_role": lane,
        "claim_refs": [f"c{n}" for n in claims],
    }


# S2 for the sample: the eight steps of Appendix A.5, built from the 21 verified claims (c1-c13
# interview, c14-c18 SOP LC-07, c19 SOP RP-02, c20-c21 job descriptions). "Load and return LIR"
# comes from two steps merged at 0.86 (pre-merged, listed as accepted).
S2_ANSWER: dict[str, Any] = {
    "steps": [
        step("st1", "activity", "Draft load plan", "Load controller", [1, 2, 14, 21]),
        step("st2", "approval", "Approve load plan", "Load control lead", [15, 20]),
        step("st3", "decision", "Special loads OK?", "Load controller", [3, 4, 16]),
        step("st4", "activity", "Resolve or offload", "Airline ops", [5]),
        step("st5", "activity", "Load aircraft", "Ramp", [6, 7, 8, 9]),
        step("st6", "activity", "Return loading report", "Ramp", [19]),
        step("st7", "decision", "Deviation in limits?", "Load controller", [10, 11, 17]),
        step("st8", "approval", "Approve deviation", "Captain", [12]),
        step("st9", "activity", "Issue load sheet", "Load controller", [13, 18]),
    ],
    "new_roles": [],
    "merge_proposals": [
        {"step_refs": ["st5", "st6"], "proposed_label": "Load and return LIR", "similarity": 0.86}
    ],
}
OCR_DEFAULT = {"lines": ["Section 2.4 Container checks (illustrative scanned page)"]}


def chunk_hashes(sessions: Any, built: Any) -> dict[tuple[str, int], tuple[str, str]]:
    """(source, chunk) → (stage, input hash) for a built sample engagement, as the app sends it."""
    from app.actions import redaction
    from app.db import session_scope
    from app.pipeline import s1_extract
    from app.repositories import sources as sources_repo
    from app.services import ai_service

    found: dict[tuple[str, int], tuple[str, str]] = {}
    for name, source_id in built.sources.items():
        with session_scope(sessions) as session:
            info = sources_repo.reading_info(session, source_id)
            terms = redaction.name_replacements(session, built.engagement_id)
            stored = sources_repo.stored_segments(session, source_id)
        assert info is not None
        stage = s1_extract.PROMPT_BY_KIND.get(info.kind, s1_extract.DOCUMENT_PROMPT)
        segments = s1_extract.prompt_segments(stored, info.format, terms)
        for index, chunk in enumerate(s1_extract.chunks_for(info.kind, segments)):
            blocks = s1_extract.blocks_for(info.kind, chunk)
            found[(name, index)] = (stage, ai_service.input_hash(stage, blocks))
    return found


@contextmanager
def sample_app(
    fixtures_dir: Path | None = None, sources: list[str] | None = None
) -> Iterator[tuple[Any, Any, Any]]:
    """The sample engagement built in a throwaway folder: (app, client, built engagement)."""
    folder = Path(tempfile.mkdtemp(prefix="pms-fixtures-"))
    # Before importing the app: never touch the real data folder or settings.
    os.environ.update(
        {"DATA_DIR": str(folder / "data"), "PMS_ENV_FILE": str(folder / ".env"), "MOCK_CLAUDE": "1"}
    )
    sys.path.insert(0, str(HERE.parent.parent))
    from fastapi.testclient import TestClient

    from app.config import load_config
    from app.main import create_app
    from tests import fixture_engagement

    config = load_config()
    if fixtures_dir is not None:
        config = dataclasses.replace(config, mock_fixtures_dir=fixtures_dir)
    app = create_app(config)
    try:
        with TestClient(app) as client:
            yield (
                app,
                client,
                fixture_engagement.build(
                    client, sources if sources is not None else fixture_engagement.SOURCES
                ),
            )
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def current_hashes() -> dict[tuple[str, int], tuple[str, str]]:
    """Build the sample engagement in a throwaway folder and return its chunk hashes."""
    with sample_app() as (app, _client, built):
        return chunk_hashes(app.state.sessions, built)


def draft_version(app: Any, client: Any, built: Any) -> str:
    """A draft of the sample engagement taken up to S1 (claims extracted and checked), as the
    draft job leaves it before the later stages; returns its version ID."""
    from app.db import session_scope
    from app.domain.result import Ok
    from app.pipeline import s1_extract
    from app.pipeline.context import ai_context
    from app.repositories import elements, sources, versions

    key = "sk-" + "ant-" + "Fixture" * 5
    assert client.put("/api/settings/key", json={"anthropic_api_key": key}).status_code == 200
    ctx = ai_context(app.state.config)
    assert isinstance(ctx, Ok), ctx
    sessions = app.state.sessions
    with session_scope(sessions) as session:
        version = versions.create(
            session, engagement_id=built.engagement_id, label="v0.1", state="draft"
        )
        ready = [
            s.id
            for s in sources.list_for_engagement(session, built.engagement_id)
            if s.text_status == "ready"
        ]
        elements.add_version_sources(session, version.id, ready)
    for source_id in ready:
        result = s1_extract.extract_source(
            app.state.config, sessions, ctx.value, version_id=version.id, source_id=source_id
        )
        assert isinstance(result, Ok), result
    return version.id


def s3_hashes(
    sessions: Any, version_id: str, sources: dict[str, str]
) -> dict[tuple[str, int], str]:
    """(source file, chunk) → the input hash of that S3 call for a version."""
    from app.actions import redaction
    from app.db import session_scope
    from app.pipeline import s3_calibrate as s3
    from app.repositories import versions
    from app.services import ai_service

    names = {sid: name for name, sid in sources.items()}
    found: dict[tuple[str, int], str] = {}
    with session_scope(sessions) as session:
        version = versions.get(session, version_id)
        assert version is not None
        steps = s3.step_refs(session, version_id)
        terms = redaction.name_replacements(session, version.engagement_id)
        for source_id in names:
            kind, chunks = s3.source_chunks(session, source_id, terms)
            for index, chunk in enumerate(chunks):
                blocks = s3.blocks_for(steps, kind, chunk)
                found[(names[source_id], index)] = ai_service.input_hash(s3.STAGE_ID, blocks)
    return found


def s3b_hashes(sessions: Any, version_id: str) -> dict[str, tuple[str, int]]:
    """Step label → (input hash of its S3b call, number of claims) for a version."""
    from app.actions import redaction
    from app.db import session_scope
    from app.pipeline import s3b_verify as s3b
    from app.pipeline.s3_calibrate import step_refs
    from app.repositories import versions
    from app.services import ai_service

    with session_scope(sessions) as session:
        version = versions.get(session, version_id)
        assert version is not None
        steps = [st for st in step_refs(session, version_id) if st.claims]
        terms = redaction.name_replacements(session, version.engagement_id)
        passages = s3b.cited_passages(session, steps, terms)
        return {
            st.element.label: (
                ai_service.input_hash(s3b.STAGE_ID, s3b.blocks_for(st, passages)),
                len(st.claims),
            )
            for st in steps
        }


def verdicts(count: int, verdict: str = "supported", reason: str = "") -> dict[str, Any]:
    return {
        "verdicts": [
            {"claim_ref": f"k{n}", "verdict": verdict,
             "reason": reason or "The cited passages state it."}
            for n in range(1, count + 1)
        ]
    }  # fmt: skip


def s4_hash(sessions: Any, version_id: str) -> str:
    """The input hash of the S4 call for a version, exactly as the stage sends it."""
    from app.actions import redaction
    from app.db import session_scope
    from app.pipeline import s4_assemble as s4
    from app.pipeline.s2_canonicalise import claim_refs
    from app.pipeline.s3_calibrate import step_refs
    from app.repositories import elements, engagements, versions
    from app.services import ai_service

    with session_scope(sessions) as session:
        version = versions.get(session, version_id)
        assert version is not None
        engagement = engagements.get(session, version.engagement_id)
        assert engagement is not None
        terms = redaction.name_replacements(session, version.engagement_id)
        blocks = s4.blocks_for(
            redaction.hide(engagement.trigger, terms),
            redaction.hide(engagement.end_point, terms),
            engagements.list_roles(session, version.engagement_id),
            step_refs(session, version_id),
            claim_refs(session, version_id),
            elements.element_claims(session, version_id),
        )
    return ai_service.input_hash(s4.STAGE_ID, blocks)


def s5_hash(sessions: Any, version_id: str) -> str:
    """The input hash of the S5 call for a version, exactly as the stage sends it."""
    from app.db import session_scope
    from app.pipeline import s5_questions as s5
    from app.services import ai_service

    with session_scope(sessions) as session:
        return ai_service.input_hash(s5.STAGE_ID, s5.blocks_for(s5.needed(session, version_id)))


def run_stage(app: Any, stage: Any, version_id: str) -> None:
    """Run one later stage (S2, S3 …) on a version with the answers written so far."""
    from app.domain.result import Ok
    from app.pipeline.context import ai_context

    ctx = ai_context(app.state.config)
    assert isinstance(ctx, Ok), ctx
    result = stage(app.state.config, app.state.sessions, ctx.value, version_id=version_id)
    assert isinstance(result, Ok), result


def s2_hash(sessions: Any, version_id: str, engagement_id: str) -> str:
    """The input hash of the S2 call for a version, exactly as the stage sends it."""
    from app.db import session_scope
    from app.pipeline import s2_canonicalise as s2
    from app.repositories import engagements
    from app.services import ai_service

    with session_scope(sessions) as session:
        refs = s2.claim_refs(session, version_id)
        roles = engagements.list_roles(session, engagement_id)
    return ai_service.input_hash(s2.STAGE_ID, s2.blocks_for(refs, roles))


TRAP_SOURCES = ["interview_transcript.txt", "sop_LC-07.docx"]
# Traps T7 and T8 (PRD A.6): of the trap run's verified claims (c1 = T6 after its name was
# scrubbed, c2 = the control claim), each becomes a step; the verifier answers `partial` for the
# first (T8: kept with needs_check and a question) and `not_supported` for the second (T7:
# rejected by the verifier, listed in the register, the step removed).
TRAPS_S2: dict[str, Any] = {
    "steps": [
        step("st1", "activity", "Build preliminary plan", "Load controller", [1]),
        step("st2", "activity", "Draft load plan", "Load controller", [2]),
    ],
    "new_roles": [],
    "merge_proposals": [],
}
TRAPS_S3B: dict[str, dict[str, Any]] = {
    "Build preliminary plan": verdicts(1, "partial", "T8: the passage supports only part of it."),
    "Draft load plan": verdicts(1, "not_supported", "T7: the passage doesn't say this."),
}


def s4_step(ref: str, **fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "step_ref": ref, "claim_refs": [], "decision_mechanism": "none", "decider_role": "",
        "rule_or_threshold": "", "escalation": "", "work_min": None, "wait_min": None,
        "duration_text": "", "complexity": "", "kpi": "", "handoff_in": "", "handoff_out": "",
        "raci": [], "k_risk": "", "constraints": [], "ai_flags": [],
    }  # fmt: skip
    base.update(fields)
    return base


def raci(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"role": role, "letter": letter} for role, letter in pairs]


def edge(a: str, b: str, kind: str = "sequence", label: str = "") -> dict[str, str]:
    return {"from_ref": a, "to_ref": b, "kind": kind, "label": label}


LC, LEAD = "Load controller", "Load control lead"
# S4 for the sample (A.5): every exit labelled; "No" from the special-loads check goes to the
# offload exception, which loops back to the plan; the captain's re-trim loops back to loading.
# Times, thresholds, KPIs and constraints use only numbers and roles the step's claims state.
S4_ANSWER: dict[str, Any] = {
    "phases": [
        {"name": "Plan", "time_window": "T-120 to T-90", "step_refs": ["e1", "e2"]},
        {"name": "Check and load", "time_window": "", "step_refs": ["e3", "e4", "e5"]},
        {"name": "Close out", "time_window": "T-15 to T-10", "step_refs": ["e6", "e7", "e8"]},
    ],
    "steps": [
        s4_step("e1", raci=raci((LC, "R"), (LC, "A")), work_min=20, complexity="M",
                duration_text="About twenty minutes, around T-120",
                handoff_out="Preliminary load plan",
                k_risk="Widebody plans rely on the Load controller and one other controller",
                constraints=[{"text": "Only one other controller knows the widebody configurations",
                              "cause_type": "single_point_knowledge", "is_key": False,
                              "claim_refs": ["c2"]}]),
        s4_step("e2", raci=raci((LEAD, "R"), (LEAD, "A")), decision_mechanism="judgment",
                handoff_in="Preliminary load plan", handoff_out="Plan released to Ramp"),
        s4_step("e3", raci=raci((LC, "A")), decision_mechanism="rule_based", decider_role=LC,
                rule_or_threshold="Special loads checked against the acceptance checklist",
                constraints=[{"text": "The cargo terminal's notification often comes late",
                              "cause_type": "system_fragmentation", "is_key": True,
                              "claim_refs": ["c4"]}],
                ai_flags=[{"component": "reasoning",
                           "input": "Special load notification and acceptance checklist",
                           "output": "Accept or refuse each special load",
                           "handoff": "Load controller", "basis": "rule_based_automate_candidate"}]),
        s4_step("e4", raci=raci(("Airline ops", "R"), ("Airline ops", "A")), work_min=40,
                duration_text="Fifteen to forty minutes"),
        s4_step("e5", raci=raci(("Ramp", "R"), ("Ramp", "A")), work_min=40, wait_min=15,
                duration_text="About forty minutes loading; up to fifteen minutes' wait for the "
                              "report",
                handoff_out="Loading report to the Load controller",
                constraints=[
                    {"text": "The loading report is on paper and re-keyed",
                     "cause_type": "system_fragmentation", "is_key": True, "claim_refs": ["c7"]},
                    {"text": "Containers run short at peak times", "cause_type": "capacity_mismatch",
                     "is_key": True, "claim_refs": ["c9"]},
                ],
                ai_flags=[{"component": "perception", "input": "Paper loading report",
                           "output": "Keyed loading data", "handoff": "Load controller",
                           "basis": "rule_based_automate_candidate"}]),
        s4_step("e6", raci=raci((LC, "R")), decision_mechanism="judgment", decider_role=LC,
                rule_or_threshold="Weight deviation within the airline contract tolerance",
                escalation="Outside tolerance the captain decides"),
        s4_step("e7", raci=raci(("Captain", "A")), decision_mechanism="judgment", work_min=15,
                duration_text="Five to fifteen minutes"),
        s4_step("e8", raci=raci((LC, "R"), (LC, "A")), kpi="Final load sheet no later than T-10",
                duration_text="Around T-15",
                ai_flags=[{"component": "action", "input": "Final load figures",
                           "output": "Load sheet issued through the departure control system",
                           "handoff": "Captain", "basis": "rule_based_automate_candidate"}]),
    ],
    "edges": [
        edge("start", "e1"),
        edge("e1", "e2"),
        edge("e2", "e3", "approve", "Approve"),
        edge("e2", "e1", "reject", "Rework"),
        edge("e3", "e5", "yes", "Yes"),
        edge("e3", "e4", "no", "No"),
        edge("e4", "e1", "rework", "Re-plan"),
        edge("e5", "e6"),
        edge("e6", "e8", "yes", "Within limits"),
        edge("e6", "e7", "no", "Outside limits"),
        edge("e7", "e8", "approve", "Accept"),
        edge("e7", "e5", "rework", "Re-trim"),
        edge("e8", "end"),
    ],
}  # fmt: skip
S4_EMPTY: dict[str, list[Any]] = {"phases": [], "steps": [], "edges": []}
# S5 for the sample: the three steps that need checking with the SME, in process order
# (q1 Approve load plan: documented only; q2 Load and return LIR and q3 Deviation in limits?:
# contested). The two unknowns from S1 become questions as asked, without a call.
S5_ANSWER: dict[str, Any] = {
    "questions": [
        {"ref": "q1", "question": "The SOP says the Load control lead approves the preliminary "
                                 "load plan before release to Ramp, but the interview never "
                                 "mentions it. Is this approval done in practice?"},
        {"ref": "q2", "question": "The SOP asks for the loading report within 10 minutes of "
                                 "loading, but in practice the wait can be 15 minutes. Which is "
                                 "right, and what causes the difference?"},
        {"ref": "q3", "question": "When the weight deviation is outside tolerance, who decides: "
                                 "the Load control lead, as the SOP says, or the captain, as "
                                 "happens in practice?"},
    ]
}  # fmt: skip
S5_EMPTY: dict[str, list[Any]] = {"questions": []}


def write(root: Path, stage: str, key: str, data: object) -> None:
    (root / stage).mkdir(parents=True, exist_ok=True)
    (root / stage / f"{key}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    hashes = current_hashes()
    for root in (MOCKS, TRAPS):
        for stage in (*S1_STAGES, "S0_ocr_page"):
            shutil.rmtree(root / stage, ignore_errors=True)
    for key, (stage, digest) in hashes.items():
        write(MOCKS, stage, digest, ANSWERS.get(key, EMPTY))
        if key in TRAPS_ANSWERS:
            write(TRAPS, stage, digest, TRAPS_ANSWERS[key])
    for stage in S1_STAGES:
        write(MOCKS, stage, "default", EMPTY)
        write(TRAPS, stage, "default", EMPTY)
    write(MOCKS, "S0_ocr_page", "default", OCR_DEFAULT)
    shutil.copytree(MOCKS / "models_get", TRAPS / "models_get", dirs_exist_ok=True)
    (TRAPS / "README.md").write_text(
        "# Hallucination trap fixtures (PRD Appendix A.6), illustrative only\n\n"
        "Mock S1 answers with planted claims T1-T6, built by `../make_ai_fixtures.py`. Each must "
        "be rejected with the stated guardrail (G3 missing passage, G4 quote not found, G5 number "
        "or role not found) or, for T6, have the name scrubbed.\n",
        encoding="utf-8",
    )
    # Later stages depend on earlier answers: run the draft on the answers written so far, then
    # work out the next stage's exact input.
    for root in (MOCKS, TRAPS):
        shutil.rmtree(root / "S2_canonicalise", ignore_errors=True)
        write(root, "S2_canonicalise", "default", S2_EMPTY)
    for root in (MOCKS, TRAPS):
        for stage, empty in (
            ("S3_calibrate", S3_EMPTY),
            ("S3b_verify", S3B_EMPTY),
            ("S4_assemble", S4_EMPTY),
            ("S5_questions", S5_EMPTY),
        ):
            shutil.rmtree(root / stage, ignore_errors=True)
            write(root, stage, "default", empty)
    from app.pipeline import s2_canonicalise, s3_calibrate, s3b_verify, s4_assemble

    with sample_app() as (app, client, built):
        version_id = draft_version(app, client, built)
        sessions = app.state.sessions
        write(MOCKS, "S2_canonicalise", s2_hash(sessions, version_id, built.engagement_id),
              S2_ANSWER)  # fmt: skip
        run_stage(app, s2_canonicalise.canonicalise, version_id)
        for key, digest in s3_hashes(sessions, version_id, built.sources).items():
            write(MOCKS, "S3_calibrate", digest, S3_ANSWERS.get(key, S3_EMPTY))
        run_stage(app, s3_calibrate.calibrate, version_id)
        for _label, (digest, count) in s3b_hashes(sessions, version_id).items():
            write(MOCKS, "S3b_verify", digest, verdicts(count))
        run_stage(app, s3b_verify.verify, version_id)
        write(MOCKS, "S4_assemble", s4_hash(sessions, version_id), S4_ANSWER)
        run_stage(app, s4_assemble.assemble, version_id)
        write(MOCKS, "S5_questions", s5_hash(sessions, version_id), S5_ANSWER)

    # The trap run (interview and LC-07 with the trap S1 answers).
    with sample_app(TRAPS, TRAP_SOURCES) as (app, client, built):
        version_id = draft_version(app, client, built)
        sessions = app.state.sessions
        write(TRAPS, "S2_canonicalise", s2_hash(sessions, version_id, built.engagement_id),
              TRAPS_S2)  # fmt: skip
        run_stage(app, s2_canonicalise.canonicalise, version_id)
        run_stage(app, s3_calibrate.calibrate, version_id)
        for label, (digest, _count) in s3b_hashes(sessions, version_id).items():
            write(TRAPS, "S3b_verify", digest, TRAPS_S3B[label])
    print(
        f"Wrote {len(hashes)} chunk answers, the S2 answer and {len(TRAPS_ANSWERS)} trap answers."
    )


if __name__ == "__main__":
    main()
