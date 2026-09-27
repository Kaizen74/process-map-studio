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

EMPTY: dict[str, list[Any]] = {"claims": [], "unknowns": []}
S2_EMPTY: dict[str, list[Any]] = {"steps": [], "new_roles": [], "merge_proposals": []}


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
def sample_app() -> Iterator[tuple[Any, Any, Any]]:
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

    app = create_app(load_config())
    try:
        with TestClient(app) as client:
            yield app, client, fixture_engagement.build(client)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def current_hashes() -> dict[tuple[str, int], tuple[str, str]]:
    """Build the sample engagement in a throwaway folder and return its chunk hashes."""
    with sample_app() as (app, _client, built):
        return chunk_hashes(app.state.sessions, built)


def draft_version(app: Any, client: Any, built: Any) -> str:
    """Run the draft job on the sample engagement (mock answers) and return its version ID."""
    key = "sk-" + "ant-" + "Fixture" * 5
    assert client.put("/api/settings/key", json={"anthropic_api_key": key}).status_code == 200
    job = client.post(f"/api/engagements/{built.engagement_id}/draft").json()["job_id"]
    assert app.state.worker.drain(60)
    body = client.get(f"/api/jobs/{job}").json()
    assert body["status"] == "done", body
    return str(body["target_id"])


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
    with sample_app() as (app, client, built):
        version_id = draft_version(app, client, built)
        write(MOCKS, "S2_canonicalise", s2_hash(app.state.sessions, version_id,
                                                built.engagement_id), S2_ANSWER)  # fmt: skip
    print(
        f"Wrote {len(hashes)} chunk answers, the S2 answer and {len(TRAPS_ANSWERS)} trap answers."
    )


if __name__ == "__main__":
    main()
