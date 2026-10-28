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


INTERVIEW_FIELDS: dict[str, Any] = {
    "account_type": "unclear",
    "account_cue": "",
    "stated_reason": "",
    "variation_condition": "",
    "markers": [],
}


def told(
    found: dict[str, Any],
    account: str,
    cue: str,
    *,
    reason: str = "",
    condition: str = "",
    markers: tuple[tuple[str, bool, str], ...] = (),
) -> dict[str, Any]:
    """An interview claim with the account it gives (PRD §3.12.3, A.8), the SME's stated reason
    and variation condition, and the marker hints it confirms or sets aside (§3.12.10 B)."""
    return found | {
        "account_type": account,
        "account_cue": cue,
        "stated_reason": reason,
        "variation_condition": condition,
        "markers": [{"marker": m, "confirmed": ok, "quote": q} for m, ok, q in markers],
    }


def as_interview(answer: dict[str, Any]) -> dict[str, Any]:
    """Every interview claim carries the interview fields (unclear and empty unless told)."""
    return answer | {"claims": [INTERVIEW_FIELDS | c for c in answer["claims"]]}


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
            told(
                claim(
                    "activity",
                    "The Load controller builds the preliminary load plan from the booked "
                    "figures, around T-120, in about twenty minutes.",
                    ["p2"],
                    "I build the preliminary load plan off the booked figures, usually around "
                    "T-120. Takes me about twenty minutes.",
                    responsible="Load controller",
                    duration="about twenty minutes",
                ),
                "lived",
                "I build the preliminary load plan",
                markers=(
                    ("explicit_order: First thing", True, "First thing"),
                    # "usually" here is about timing, not a variant path: set aside (crit. 63).
                    ("variation: usually", False, "usually around T-120"),
                ),
            ),
            claim(
                "constraint",
                "Only the Load controller and one other controller really know the widebody "
                "configurations.",
                ["p3"],
                "only me and one other controller really know the configurations",
                responsible="Load controller",
            ),
            told(
                claim(
                    "decision",
                    "The Load controller checks special loads, dangerous goods and live animals "
                    "against the checklist.",
                    ["p4"],
                    "I check special loads, dangerous goods and live animals, against the "
                    "checklist",
                    decider="Load controller",
                    mechanism="rule_based",
                ),
                "lived",
                "Then I check special loads",
                markers=(
                    ("explicit_order: Then", True, "Then I check special loads"),
                    ("control_note: check", True, "I check special loads"),
                    ("work_type_clear: checklist", True, "against the checklist"),
                ),
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
            told(
                claim(
                    "activity",
                    "Ramp loads the aircraft, in forty minutes or so, and sends back the loading "
                    "report.",
                    ["p7"],
                    "Ramp loads the aircraft, forty minutes or so, and sends back the loading "
                    "report.",
                    responsible="Ramp",
                    duration="forty minutes or so",
                ),
                "lived",
                "It's still on paper and I re-key it",
                markers=(("handoff: sends back", True, "sends back the loading report"),),
            ),
            told(
                claim(
                    "constraint",
                    "The loading report is still on paper and the Load controller re-keys it.",
                    ["p7"],
                    "It's still on paper and I re-key it.",
                    responsible="Load controller",
                ),
                "lived",
                "I re-key it",
            ),
            told(
                claim(
                    "duration",
                    "The Load controller sometimes waits fifteen minutes for the loading report.",
                    ["p7"],
                    "We sometimes wait fifteen minutes for it",
                    responsible="Load controller",
                    duration="fifteen minutes",
                ),
                "lived",
                "We sometimes wait fifteen minutes for it",
                markers=(("wait: wait", True, "We sometimes wait fifteen minutes for it"),),
            ),
            claim(
                "constraint",
                "At peak times there is a shortage of containers.",
                ["p7"],
                "at peak we're short of containers",
            ),
            # 22:30 (A.8): the first sentence is the official account, the second the lived one.
            told(
                claim(
                    "threshold",
                    "The Ramp should send the loading report within ten minutes.",
                    ["p8"],
                    "Officially the ramp should send the report within ten minutes.",
                    responsible="Ramp",
                    threshold="within ten minutes",
                ),
                "official",
                "Officially",
                markers=(("account_official: Officially", True, "Officially"),),
            ),
            told(
                claim(
                    "exception",
                    "On a busy wave the Load controller walks down to the aircraft and reads the "
                    "loading report off the ramp's sheet.",
                    ["p8"],
                    "What actually happens on a busy wave is I walk down and read it off their "
                    "sheet, otherwise we'd miss the slot.",
                    responsible="Load controller",
                ),
                "lived",
                "What actually happens",
                reason="otherwise we'd miss the slot",
                condition="on a busy wave",
                markers=(
                    ("account_lived: What actually happens", True, "What actually happens"),
                    ("variation: on a busy wave", True, "on a busy wave"),
                ),
            ),
        ],
        "unknowns": [],
    },
    ("interview_transcript.txt", 2): {
        "claims": [
            claim(
                "decision",
                "If the weight deviation is outside tolerance, the captain decides.",
                ["p12"],
                "If the weight deviation is outside tolerance, it's the captain who decides, not us.",
                decider="Captain",
                mechanism="judgment",
                threshold="outside tolerance",
            ),
            claim(
                "threshold",
                "The weight tolerance depends on the airline contract.",
                ["p12"],
                "The tolerance depends on the airline contract.",
            ),
            claim(
                "approval",
                "The captain either accepts the deviation or asks for a re-trim, which takes five "
                "to fifteen minutes.",
                ["p13"],
                "The captain either accepts or asks for a re-trim. Five to fifteen minutes.",
                accountable="Captain",
                mechanism="judgment",
                duration="Five to fifteen minutes",
            ),
            told(
                claim(
                    "activity",
                    "The Load controller issues the final load sheet around T-15.",
                    ["p16"],
                    "Then I issue the final load sheet, around T-15.",
                    responsible="Load controller",
                ),
                "lived",
                "Then I issue the final load sheet",
                markers=(("explicit_order: Then", True, "Then I issue"),),
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


def grounded(refs: list[str], quote: str, **fields: Any) -> dict[str, Any]:
    return {"segment_ids": refs, "quote": quote} | fields


# What else the A.1 interview tells (PRD §3.12.2, A.8; C1): the 24:10 story with the SME's own
# signifier and frequency (24:46), the know-how at the special-loads and deviation decisions, the
# SME terms, and what the deviation call attends to. S3c links them to the steps.
SENSE: dict[tuple[str, int], dict[str, Any]] = {
    ("interview_transcript.txt", 0): {
        "know_how": [
            grounded(
                ["p4"],
                "against the checklist",
                category="artefacts",
                text="The special loads checklist.",
                about="Special loads OK?",
                provenance="O",
                basis="",
            ),
        ],
    },
    ("interview_transcript.txt", 1): {
        "stories": [
            grounded(
                ["p9", "p11"],
                "I learned it after we had to re-trim three flights in one night.",
                label="Had to re-trim three flights in one night",
                fragment_type="went_badly",
                signifiers=["Firefighting"],
                frequency="maybe once a month",
                about="Draft load plan; Deviation in limits?",
            ),
        ],
        "know_how": [
            grounded(
                ["p9"],
                "if the forward hold looks heavy on the plan, I call the ramp before "
                "they start, not after",
                category="heuristics",
                text="If the forward hold looks heavy on the plan, call the ramp before they "
                "start, not after.",
                about="Deviation in limits?",
                provenance="O",
                basis="",
            ),
            grounded(
                ["p9"],
                "Nobody taught me that; I learned it after we had to re-trim three "
                "flights in one night.",
                category="experience",
                text="The rule of thumb was learned, not taught, after re-trimming three "
                "flights in one night.",
                about="Deviation in limits?",
                provenance="O",
                basis="",
            ),
            grounded(
                ["p7"],
                "sends back the loading report",
                category="artefacts",
                text="The loading report from Ramp.",
                about="Deviation in limits?",
                provenance="O",
                basis="",
            ),
        ],
        "terms": [
            grounded(
                ["p9"],
                "we had to re-trim three flights",
                term="re-trim",
                plain_meaning="Rebalance an aircraft's load after it has been planned.",
            ),
            grounded(
                ["p8"], "on a busy wave", term="wave", plain_meaning="A busy period of departures."
            ),
            grounded(
                ["p9"],
                "if the forward hold looks heavy on the plan",
                term="forward hold",
                plain_meaning="The cargo hold at the front of the aircraft.",
            ),
        ],
    },
    ("interview_transcript.txt", 2): {
        "decision_info": [
            grounded(
                ["p15"],
                "It depends on the captain, the weather, what's still on the belt.",
                about="Deviation in limits?",
                cadence="none",
                received=[],
                attended=["the captain", "the weather", "what's still on the belt"],
                wanted=[],
                communicated_via=[],
            ),
        ],
    },
}
# Information in and out of steps in the A.1 interview (rule 8: what a step passes on and what
# another receives), for stitching with the landscape interview (A.10, C3).
SENSE[("interview_transcript.txt", 0)]["decision_info"] = [
    grounded(
        ["p2"],
        "I build the preliminary load plan",
        about="Draft load plan",
        cadence="none",
        received=[],
        attended=[],
        wanted=[],
        communicated_via=["the preliminary load plan"],
    ),
]
SENSE[("interview_transcript.txt", 1)]["decision_info"] = [
    grounded(
        ["p7"],
        "sends back the loading report",
        about="Deviation in limits?",
        cadence="none",
        received=["the loading report"],
        attended=[],
        wanted=[],
        communicated_via=[],
    ),
]
# A.10: the Ramp duty manager's landscape interview (L3 interfaces, L6 capability).
ANSWERS[("landscape_ramp_lead.txt", 0)] = {
    "claims": [
        told(
            claim(
                "handoff",
                "Ramp gets the preliminary load plan from Load control.",
                ["p2"],
                "We get the preliminary load plan from load control",
                responsible="Ramp",
            ),
            "lived",
            "We get the preliminary load plan",
        ),
        told(
            claim(
                "handoff",
                "Once loading is done, Ramp sends the loading report to Load control.",
                ["p2"],
                "once loading is done we send them the loading report",
                responsible="Ramp",
            ),
            "lived",
            "we send them the loading report",
        ),
        claim(
            "constraint",
            "The loading report is on paper; it gets lost or arrives late.",
            ["p4"],
            "The weakness is the paper loading report; it gets lost or arrives late.",
        ),
    ],
    "unknowns": [],
    "decision_info": [
        grounded(
            ["p2"],
            "We get the preliminary load plan from load control, and once loading "
            "is done we send them the loading report.",
            about="Load and return LIR",
            cadence="none",
            received=["the preliminary load plan"],
            attended=[],
            wanted=[],
            communicated_via=["the loading report"],
        ),
    ],
    "capability_notes": [
        grounded(
            ["p4"],
            "The strength is the supervisors know the aircraft types inside out.",
            kind="strength",
            dimension="skillset",
            text="Ramp supervisors know the aircraft types inside out.",
            cause_type="none",
        ),
        grounded(
            ["p4"],
            "The weakness is the paper loading report; it gets lost or arrives late.",
            kind="weakness",
            dimension="systems",
            text="The paper loading report gets lost or arrives late.",
            cause_type="system_fragmentation",
        ),
    ],
}
for _key, _items in SENSE.items():
    ANSWERS[_key] = ANSWERS[_key] | _items

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
        stance("e5", "supports", ["p7"],
               "Ramp loads the aircraft, forty minutes or so, and sends back the loading report."),
        stance("e6", "supports", ["p8"], "What actually happens on a busy wave"),
        stance("e7", "supports", ["p8"], "I walk down and read it off their sheet"),
    ]},
    ("interview_transcript.txt", 2): {"stances": [
        stance("e8", "supports", ["p12"],
               "If the weight deviation is outside tolerance, it's the captain who decides, not us."),
        stance("e9", "supports", ["p13"], "The captain either accepts or asks for a re-trim."),
        stance("e10", "supports", ["p16"], "Then I issue the final load sheet, around T-15."),
    ]},
    ("sop_LC-07.docx", 0): {"stances": [
        stance("e1", "supports", ["p3"],
               "The Load Controller shall prepare the preliminary load plan by T-90."),
        stance("e2", "supports", ["p4"], "The preliminary load plan shall be approved by the Load "
               "Control Lead before release to Ramp."),
        stance("e3", "supports", ["p6"],
               "Special loads shall be checked against the acceptance checklist before loading."),
        stance("e8", "contradicts", ["p8"], "the Load Control Lead shall decide on corrective action",
               "ownership", "Ownership divergence: the Load control lead decides in the SOP, the "
               "Captain in practice."),
        stance("e10", "supports", ["p10"], "The final load sheet shall be issued through the "
               "departure control system no later than T-10."),
    ]},
    ("landscape_ramp_lead.txt", 0): {"stances": [
        stance("e5", "supports", ["p2"], "once loading is done we send them the loading report"),
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
        stance("e10", "supports", ["p2"], JD_CONTROLLER_QUOTE),
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


# S2 for the sample: the eight steps of Appendix A.5, built from the 23 verified claims (c1-c15
# interview, c16-c20 SOP LC-07, c21 SOP RP-02, c22-c23 job descriptions). "Load and return LIR"
# comes from two steps merged at 0.86 (pre-merged, listed as accepted); it also carries the
# SME's official account of the return time (c10). The lived busy-wave variation (c11) is left
# out here: translation places it (B4).
S2_ANSWER: dict[str, Any] = {
    "steps": [
        step("st1", "activity", "Draft load plan", "Load controller", [1, 2, 16, 23]),
        step("st2", "approval", "Approve load plan", "Load control lead", [17, 22]),
        step("st3", "decision", "Special loads OK?", "Load controller", [3, 4, 18]),
        step("st4", "activity", "Resolve or offload", "Airline ops", [5]),
        # A.10 (C3): the landscape interview's hand-offs and constraint (c24-c26).
        step("st5", "activity", "Load aircraft", "Ramp", [6, 7, 8, 9, 10, 24, 26]),
        step("st6", "activity", "Return loading report", "Ramp", [21, 25]),
        # Translation rule 2 (A.5, A.9): the lived variation "on a busy wave" (c11) becomes a
        # decision on that condition with the lived alternative as its "Yes" branch; listed where
        # it happens in the process.
        step("st7", "decision", "Busy wave?", "Load controller", [11]),
        step("st8", "activity", "Read report at aircraft", "Load controller", [11]),
        step("st9", "decision", "Deviation in limits?", "Load controller", [12, 13, 19]),
        step("st10", "approval", "Approve deviation", "Captain", [14]),
        step("st11", "activity", "Issue load sheet", "Load controller", [15, 20]),
    ],
    "new_roles": [],
    "merge_proposals": [
        {"step_refs": ["st5", "st6"], "proposed_label": "Load and return LIR", "similarity": 0.86}
    ],
}
OCR_DEFAULT = {"lines": ["Section 2.4 Container checks (illustrative scanned page)"]}


def chunk_hashes(sessions: Any, built: Any) -> dict[tuple[str, int], tuple[str, str]]:
    """(source, chunk) → (stage, input hash) for a built sample engagement, as the app sends it."""
    from app.db import session_scope
    from app.domain.result import Ok
    from app.pipeline import s1_extract
    from app.services import ai_service

    found: dict[tuple[str, int], tuple[str, str]] = {}
    for name, source_id in built.sources.items():
        with session_scope(sessions) as session:
            result = s1_extract.prepare(session, source_id)  # exactly as S1 prepares it
        assert isinstance(result, Ok), result
        prepared = result.value
        kind = prepared.info.kind
        stage = s1_extract.PROMPT_BY_KIND.get(kind, s1_extract.DOCUMENT_PROMPT)
        for index, chunk in enumerate(s1_extract.chunks_for(kind, prepared.segments)):
            blocks = s1_extract.blocks_for(kind, chunk, prepared.questions)
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
        # The app answers only its own address (DNS-rebinding guard, deep review 2026-10-19).
        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
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


S3C_EMPTY: dict[str, Any] = {"work_types": [], "links": []}


def s3c_call(sessions: Any, version_id: str) -> tuple[str, dict[str, str], list[tuple[str, str]]]:
    """The S3c call for a version: its input hash, the call's source ref per file name and the
    item ref per item text, exactly as the stage sends them."""
    from app.actions import redaction
    from app.db import session_scope
    from app.pipeline import s3c_sensemaking as s3c
    from app.pipeline.s3_calibrate import step_refs
    from app.repositories import sources, versions
    from app.services import ai_service

    with session_scope(sessions) as session:
        version = versions.get(session, version_id)
        assert version is not None
        terms = redaction.name_replacements(session, version.engagement_id)
        steps = step_refs(session, version_id)
        items = s3c.items_for(session, version_id)
        passages = s3c.passages_for(session, steps, items, terms)
        names = {}
        for sref, _kind, segments in passages:
            owner = sources.segment_source(session, segments[0].segment_id)
            found = sources.get(session, owner or "")
            assert found is not None
            names[found.filename] = sref
        blocks = s3c.blocks_for(steps, items, passages)
    item_refs = [(str(i.record.payload["text"]), i.ref) for i in items]
    return ai_service.input_hash(s3c.STAGE_ID, blocks), names, item_refs


def s3c_answer(names: dict[str, str], items: list[tuple[str, str]]) -> dict[str, Any]:
    """A.8 work types with quoted cues, and what each story, know-how item, term and decision
    information item is about (C2)."""
    interview, sop = names["interview_transcript.txt"], names["sop_LC-07.docx"]

    def cue(source: str, seq: int, quote: str) -> dict[str, Any]:
        return {"segment_ids": [f"{source}.p{seq}"], "quote": quote}

    def item(text_start: str) -> str:
        return next(ref for text, ref in items if text.startswith(text_start))

    def refs_of(text: str) -> list[str]:
        return [ref for t, ref in items if t == text]

    return {
        "work_types": [
            {"step_ref": "e1", "work_type": "complicated",
             "cues": [cue(interview, 3, "only me and one other controller really know the "
                                        "configurations")],
             "basis": "The plan for widebodies needs someone experienced."},
            {"step_ref": "e3", "work_type": "clear",
             "cues": [cue(interview, 4, "against the checklist"),
                      cue(sop, 6, "Special loads shall be checked against the acceptance "
                                  "checklist")],
             "basis": "Special loads are checked against a fixed checklist."},
            {"step_ref": "e8", "work_type": "complex",
             "cues": [cue(interview, 15, "There's no fixed answer."),
                      cue(interview, 15, "You read the situation.")],
             "basis": "The SME says there is no fixed answer and the situation is read."},
            {"step_ref": "e10", "work_type": "clear",
             "cues": [cue(sop, 10, "The final load sheet shall be issued through the departure "
                                  "control system")],
             "basis": "Issuing the load sheet follows a fixed rule."},
        ],
        "links": [
            {"item_ref": item("The special loads checklist"), "step_refs": ["e3"]},
            {"item_ref": item("Had to re-trim"), "step_refs": ["e1", "e8"]},
            {"item_ref": item("If the forward hold"), "step_refs": ["e8"]},
            {"item_ref": item("The rule of thumb"), "step_refs": ["e8"]},
            {"item_ref": item("The loading report"), "step_refs": ["e8"]},
            {"item_ref": item("re-trim:"), "step_refs": ["e9"]},
            {"item_ref": item("wave:"), "step_refs": ["e6"]},
            {"item_ref": item("forward hold:"), "step_refs": ["e1"]},
            *({"item_ref": ref, "step_refs": [step]} for ref, step in (
                (refs_of("Deviation in limits?")[0], "e8"),
                (refs_of("Deviation in limits?")[1], "e8"),
                (item("Draft load plan"), "e1"),
                (item("Load and return LIR"), "e5"),
                (item("Ramp supervisors know"), "e5"),
                (item("The paper loading report"), "e5"),
            )),
        ],
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
    from app.actions import redaction
    from app.db import session_scope
    from app.pipeline import s2_canonicalise as s2
    from app.repositories import engagements
    from app.services import ai_service, prompts

    with session_scope(sessions) as session:
        refs = s2.claim_refs(session, version_id)
        roles = engagements.list_roles(session, engagement_id)
        engagement = engagements.get(session, engagement_id)
        terms = redaction.name_replacements(session, engagement_id)
    conventions = prompts.render_conventions(
        engagement.conventions.model_dump() if engagement else None
    )
    flow = s2.render_flow(engagement, terms)
    return ai_service.input_hash(s2.STAGE_ID, s2.blocks_for(refs, roles, conventions, flow))


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


def variant(**values: str) -> dict[str, str]:
    return {"owner": "", "threshold": "", "time": "", "trigger": ""} | values


def s4_step(ref: str, **fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "step_ref": ref, "claim_refs": [], "decision_mechanism": "none", "decider_role": "",
        "rule_or_threshold": "", "escalation": "", "work_min": None, "wait_min": None,
        "duration_text": "", "complexity": "", "kpi": "", "handoff_in": "", "handoff_out": "",
        "raci": [], "k_risk": "", "constraints": [], "ai_flags": [],
        "variant_done": variant(), "variant_documented": variant(),
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
        {"name": "Check and load", "time_window": "", "step_refs": ["e3", "e4", "e5", "e6", "e7"]},
        {"name": "Close out", "time_window": "T-15 to T-10", "step_refs": ["e8", "e9", "e10"]},
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
                           "basis": "rule_based_automate_candidate"}],
                # A.9 variants: the documents' ten minutes against practice's wait of up to 15.
                variant_done=variant(time="Up to fifteen minutes' wait for the report"),
                variant_documented=variant(time="Within 10 minutes of loading completion")),
        s4_step("e8", raci=raci((LC, "R")), decision_mechanism="judgment", decider_role=LC,
                rule_or_threshold="Weight deviation within the airline contract tolerance",
                escalation="Outside tolerance the captain decides",
                # A.9 variants: who decides outside tolerance, in practice and per the SOP.
                variant_done=variant(owner="Captain"),
                variant_documented=variant(owner="Load control lead")),
        s4_step("e9", raci=raci(("Captain", "A")), decision_mechanism="judgment", work_min=15,
                duration_text="Five to fifteen minutes"),
        s4_step("e10", raci=raci((LC, "R"), (LC, "A")), kpi="Final load sheet no later than T-10",
                duration_text="Around T-15",
                ai_flags=[{"component": "action", "input": "Final load figures",
                           "output": "Load sheet issued through the departure control system",
                           "handoff": "Captain", "basis": "rule_based_automate_candidate"}]),
        # The busy-wave decision (A.5: rule-based, the condition is stated) and its lived branch.
        s4_step("e6", raci=raci((LC, "R"), (LC, "A")), decision_mechanism="rule_based",
                decider_role=LC, rule_or_threshold="On a busy wave"),
        s4_step("e7", raci=raci((LC, "R"), (LC, "A")),
                handoff_in="Loading report on the ramp's sheet"),
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
        edge("e6", "e7", "yes", "Yes"),
        edge("e6", "e8", "no", "No"),
        edge("e7", "e8"),
        edge("e8", "e10", "yes", "Within limits"),
        edge("e8", "e9", "no", "Outside limits"),
        edge("e9", "e10", "approve", "Accept"),
        edge("e9", "e5", "rework", "Re-trim"),
        edge("e10", "end"),
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


# Gap analysis A (PRD Appendix A.7): the four expected findings and the unexplained cause. The
# divergence IDs (d1 …) and passage IDs (e1 …) are the ones the app gives the sample map's
# divergence set: d1 Approve load plan, d2 Resolve or offload, d3 Load and return LIR,
# d4 Deviation in limits?, d5 Approve deviation.
def ga_finding(
    finding_type: str, title: str, text: str, refs: list[str], evidence: list[tuple[str, str]]
) -> dict[str, Any]:
    return {
        "finding_type": finding_type,
        "section": "fact",
        "title": title,
        "text": text,
        "step_refs": refs,
        "evidence": [{"segment_id": seg, "quote": quote} for seg, quote in evidence],
        "basis": "",
        "basis_segment_ids": [],
    }


GA_INTERNAL_ANSWER: dict[str, Any] = {
    "findings": [
        ga_finding(
            "dead_control_candidate",
            "Plan approval by the Load control lead is documented but never mentioned in practice",
            "SOP LC-07 §3.2 and the Load control lead's job description say the Load control lead "
            "approves the load plan before release to Ramp. The interview never mentions this "
            "approval.",
            ["d1"],
            [
                (
                    "e2",
                    "The preliminary load plan shall be approved by the Load Control Lead "
                    "before release to Ramp",
                ),
                ("e1", "Accountable for approval of load plans"),
            ],
        ),
        ga_finding(
            "threshold_gap",
            "Loading report return: 10 minutes in SOP RP-02, up to 15 minutes' wait in practice",
            "SOP RP-02 §2 has the Ramp Supervisor return the loading report within 10 minutes of "
            "loading completion; the Load controller says they sometimes wait fifteen minutes "
            "for it.",
            ["d3"],
            [
                (
                    "e6",  # A.10 (C3): the landscape interview's passage is e5
                    "return the loading report to Load Control within 10 minutes of loading "
                    "completion",
                ),
                ("e4", "We sometimes wait fifteen minutes for it"),
            ],
        ),
        ga_finding(
            "ownership_mismatch",
            "Weight-deviation decision: the Load control lead in SOP LC-07, the Captain in "
            "practice",
            "SOP LC-07 §5 has the Load Control Lead decide on corrective action when weights "
            "deviate beyond the airline tolerance; in practice the captain decides. The job "
            "descriptions are silent.",
            ["d6"],
            [
                ("e9", "the Load Control Lead shall decide on corrective action"),
                ("e8", "it's the captain who decides, not us"),
            ],
        ),
        # A.8 (C4b): the reality gaps. The official account (22:30, first sentence) is on the
        # loading step, the lived one with its stated reason on reading the report at the aircraft.
        ga_finding(
            "known_adaptation",
            "Loading report: sent within ten minutes officially, read at the aircraft on a busy "
            "wave",
            "Officially the Ramp sends the loading report within ten minutes; on a busy wave the "
            "Load controller walks down and reads it off the Ramp's sheet instead.",
            ["d3", "d5"],
            [
                ("e7", "Officially the ramp should send the report within ten minutes"),
                (
                    "e7",
                    "What actually happens on a busy wave is I walk down and read it off their "
                    "sheet",
                ),
            ],
        )
        | {
            "gap_class": "effective_adaptation",
            "stated_reason": "otherwise we'd miss the slot",
            "cause_type": "capacity_mismatch",
        },
        ga_finding(
            "constraint_mismatch",
            "Weight-deviation call: a fixed decider in SOP LC-07 for work the Load controller "
            "describes as having no fixed answer",
            "SOP LC-07 §5 sets who decides on corrective action when weights deviate; the Load "
            "controller describes it as a call with no fixed answer, where you read the "
            "situation.",
            ["d6"],
            [
                ("e9", "the Load Control Lead shall decide on corrective action"),
                ("e10", "There's no fixed answer"),
            ],
        )
        | {
            "section": "interpretation",
            "basis": "The Load controller says there is no fixed answer and that you read the "
            "situation, which marks the call as complex work rather than a set rule.",
            "basis_segment_ids": ["e10"],
        },
        ga_finding(
            "undocumented_work",
            "Offload resolution is undocumented work",
            "When something can't be accepted, the airline decides what to offload, which takes "
            "fifteen to forty minutes before the Load controller re-plans. No SOP or job "
            "description covers it.",
            ["d2"],
            [("e3", "If something can't be accepted, the airline decides what to offload")],
        ),
    ],
    "unknowns": [
        {
            "finding_type": "dead_control_candidate",
            "step_refs": ["d1"],
            "question": "Is the load plan approved by the Load control lead before release to "
            "Ramp, and if not, why not?",
        }
    ],
}


def resolve_ga_refs(dset: Any) -> None:
    """Check each finding's evidence names the passage that holds its quote, as the call numbers
    them (`e<n>` follow the diverging steps, so a new source shifts them): fails with the right
    number so the answer above can be corrected (the tests read it as written)."""
    from app.services import grounding

    def ref_for(quote: str) -> str:
        wanted = grounding.normalise_text(quote)
        for ref, passage in dset.passages.items():
            if wanted in grounding.normalise_text(passage.segment.text):
                return str(ref)
        raise AssertionError(f"no passage holds: {quote}")

    for finding in GA_INTERNAL_ANSWER["findings"]:
        for e in finding["evidence"]:
            right = ref_for(e["quote"])
            assert e["segment_id"] == right, f"{e['quote']!r} is in {right}, not {e['segment_id']}"


def ga_hashes(sessions: Any, version_id: str) -> tuple[str, str]:
    """The input hashes of the GA_internal call and, with its answer as filed, the GA_verify call."""
    from app.db import session_scope
    from app.domain.ai_schemas import GAInternalOutput
    from app.pipeline import ga_internal as ga
    from app.services import ai_service

    with session_scope(sessions) as session:
        dset = ga.divergence_set(session, version_id)
    assert dset is not None
    resolve_ga_refs(dset)
    output = GAInternalOutput.model_validate(GA_INTERNAL_ANSWER)
    checked = [ga.check(dset, f) for f in output.findings]
    rejected = [c.finding.rejection_reason for c in checked if c.finding.rejection_reason]
    assert not rejected, rejected  # every A.7 finding passes the gate
    return (
        ai_service.input_hash(ga.STAGE_ID, ga.blocks_for(dset)),
        ai_service.input_hash(ga.VERIFY_STAGE, ga.verify_blocks(dset, checked)),
    )


def ga_verdicts(count: int) -> dict[str, Any]:
    return {
        "verdicts": [
            {"finding_ref": f"f{n}", "verdict": "supported",
             "reason": "The cited passages state it."}
            for n in range(1, count + 1)
        ]
    }  # fmt: skip


# Gap analysis B (PRD Appendix A.7 traps TE1-TE9), on the drafted sample with the A.7 Setup.
# One mocked research turn: three pages returned, one search stopped by the limit (TE6), and the
# answer citing those pages plus one page the search never returned (TE1). ILLUSTRATIVE ONLY:
# the domains decide the source tiers; the pages and their words are invented.
IATA = "https://www.iata.org/illustrative/load-control-guidance"
EASA = "https://www.easa.europa.eu/illustrative/mass-and-balance"
VENDOR = "https://loadplanning-software.example.com/blog/automation"
UNLISTED = "https://www.unlisted.example.org/loading-kpi"


def cite(url: str, title: str, text: str) -> dict[str, Any]:
    return {"type": "web_search_result_location", "url": url, "title": title,
            "encrypted_index": "MOCK", "cited_text": text}  # fmt: skip


IATA_T = "Illustrative industry guidance on load control"
EASA_T = "Illustrative regulator material on mass and balance"
VENDOR_T = "Illustrative vendor blog on automated load planning"
GB_RESEARCH_ANSWER: dict[str, Any] = {
    "responses": [
        {
            "id": "msg_mock_gap_research",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": [
                {"type": "server_tool_use", "id": "srvtoolu_gap_1", "name": "web_search",
                 "input": {"query": "load control second person check load sheet guidance"}},
                {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_gap_1", "content": [
                    {"type": "web_search_result", "url": IATA, "title": IATA_T,
                     "encrypted_content": "MOCK", "page_age": "March 2024"},
                    {"type": "web_search_result", "url": EASA, "title": EASA_T,
                     "encrypted_content": "MOCK", "page_age": "January 2025"},
                    {"type": "web_search_result", "url": VENDOR, "title": VENDOR_T,
                     "encrypted_content": "MOCK", "page_age": "June 2025"},
                ]},
                {"type": "server_tool_use", "id": "srvtoolu_gap_2", "name": "web_search",
                 "input": {"query": "loading report return time benchmark"}},
                {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_gap_2",
                 "content": {"type": "web_search_tool_result_error",
                             "error_code": "max_uses_exceeded"}},
                {"type": "text", "text": "Comparable operations have a second qualified person "
                 "check the load sheet before it is signed.", "citations": [
                    cite(IATA, IATA_T, "The load sheet shall be checked by a second qualified "
                         "person before it is signed."),
                    cite(EASA, EASA_T, "Operators shall ensure that mass and balance "
                         "documentation is checked by a second qualified person before it is "
                         "signed.")]},
                {"type": "text", "text": " Guidance sets a time for the final load sheet.",
                 "citations": [cite(IATA, IATA_T, "The final load sheet is issued no later than "
                                    "15 minutes before departure.")]},
                {"type": "text", "text": " Vendors describe automated checks.", "citations": [
                    cite(VENDOR, VENDOR_T, "Automated tools check the load sheet and flag "
                         "deviations.")]},
                {"type": "text", "text": " The loading report return time is tracked.",
                 "citations": [cite(UNLISTED, "Unlisted page", "Loading report return time is "
                                    "tracked as a key performance indicator.")]},
                {"type": "text", "text": " Tolerances are agreed with each airline.",
                 "citations": [cite(EASA, EASA_T, "Deviation tolerances are agreed with each "
                                    "airline in writing.")]},
                {"type": "text", "text": " A final walk-round is described.", "citations": [
                    cite(IATA, IATA_T, "A final walk-round confirms the hold doors and loading "
                         "before departure.")]},
                {"type": "text", "text": " The load plan is approved before release.",
                 "citations": [cite(IATA, IATA_T, "The load plan is approved before it is "
                                    "released to the ramp.")]},
            ],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 3100, "output_tokens": 420,
                      "server_tool_use": {"web_search_requests": 2, "web_fetch_requests": 0}},
        }
    ]
}  # fmt: skip


# Any other brief: one search, nothing reliable found.
GB_RESEARCH_NOTHING: dict[str, Any] = {
    "responses": [
        {"id": "msg_mock_gap_nothing", "type": "message", "role": "assistant",
         "model": "claude-opus-5-5",
         "content": [{"type": "text", "text": "No reliable source found.", "citations": None}],
         "stop_reason": "end_turn", "stop_sequence": None,
         "usage": {"input_tokens": 900, "output_tokens": 12,
                   "server_tool_use": {"web_search_requests": 1, "web_fetch_requests": 0}}}
    ]
}  # fmt: skip


def gb_finding(
    finding_type: str,
    title: str,
    claim: str,
    quote: str,
    cites: list[str],
    refs: list[str],
    comparison: str,
) -> dict[str, Any]:
    return {"finding_type": finding_type, "title": title, "claim": claim, "quote": quote,
            "citation_ids": cites, "step_refs": refs, "comparison": comparison}  # fmt: skip


# Citations as the app numbers them: c1 IATA second-person check, c2 EASA second-person check,
# c3 IATA 15 minutes, c4 vendor, c5 the unlisted page, c6 EASA tolerances, c7 IATA walk-round,
# c8 IATA plan approval. Steps: m1 Draft load plan … m6 Deviation in limits? … m8 Issue load sheet.
GB_STRUCTURE_ANSWER: dict[str, Any] = {
    "findings": [
        gb_finding("missing_control", "Second-person check of the load sheet before signing",
                   "Guidance and regulator material have a second qualified person check the load "
                   "sheet before it is signed.",
                   "checked by a second qualified person before it is signed",
                   ["c1", "c2"], ["m10"], "different"),
        gb_finding("time_or_threshold_benchmark", "Final load sheet issued by a set time",
                   "Guidance issues the final load sheet no later than 15 minutes before "
                   "departure.",
                   "The final load sheet is issued no later than 15 minutes before departure",
                   ["c3"], [], "absent"),
        # TE4: a vendor blog only → kept, weak evidence, Low.
        gb_finding("technology_enabler", "Automated checks of the load sheet",
                   "Automated tools check the load sheet and flag deviations.",
                   "Automated tools check the load sheet and flag deviations",
                   ["c4"], ["m10"], "absent"),
        # TE1: a page the search never returned → GX2.
        gb_finding("kpi_practice", "Loading report return time as a KPI",
                   "Loading report return time is tracked as a key performance indicator.",
                   "Loading report return time is tracked as a key performance indicator",
                   ["c5"], ["m5"], "absent"),
        # TE2: no citation → GX1.
        gb_finding("other_difference", "Load controllers rotate shifts weekly",
                   "Load controllers rotate shifts weekly.", "", [], [], "absent"),
        # TE3: a number the cited text doesn't have → GX3.
        gb_finding("time_or_threshold_benchmark", "Deviation decisions within 5 minutes",
                   "Deviation tolerances are agreed with each airline and decided within "
                   "5 minutes.",
                   "Deviation tolerances are agreed with each airline in writing",
                   ["c6"], ["m8"], "different"),
        # TE7: one link to a step that isn't on the map → link removed and flagged.
        gb_finding("decision_rights_difference", "Deviation tolerances agreed in writing",
                   "Deviation tolerances are agreed with each airline in writing.",
                   "Deviation tolerances are agreed with each airline in writing",
                   ["c6"], ["m8", "m99"], "different"),
        # TE8: well cited, but the verifier answers not_supported → rejected GAV.
        gb_finding("missing_step", "Final walk-round before departure",
                   "A final walk-round confirms the hold doors and loading before departure.",
                   "A final walk-round confirms the hold doors and loading before departure",
                   ["c7"], [], "absent"),
        # TE9: already present and aligned → left out as not a gap.
        gb_finding("missing_step", "Load plan approved before release",
                   "The load plan is approved before it is released to the ramp.",
                   "The load plan is approved before it is released to the ramp",
                   ["c8"], ["m2"], "aligned"),
    ]
}  # fmt: skip
# Verified in order: the first check, the benchmark, the vendor claim, the tolerances, the walk-round.
GB_VERIFY_ANSWER: dict[str, Any] = {
    "verdicts": [
        {"finding_ref": "f1", "verdict": "supported", "reason": "Both excerpts state it."},
        {"finding_ref": "f2", "verdict": "supported", "reason": "The excerpt states it."},
        {"finding_ref": "f3", "verdict": "supported", "reason": "The excerpt states it."},
        {"finding_ref": "f4", "verdict": "supported", "reason": "The excerpt states it."},
        {"finding_ref": "f5", "verdict": "not_supported",
         "reason": "TE8: the excerpt is about a walk-round, not a separate step in this process."},
    ]
}  # fmt: skip


def gb_hashes(client: Any, app: Any, engagement_id: str, version_id: str) -> tuple[str, str, str]:
    """The research key, and the structuring and verifier input hashes, for the sample with the
    A.7 Setup and its drafted brief, confirmed as it stands."""
    from datetime import date

    from app.db import session_scope
    from app.domain.ai_schemas import GBStructureOutput
    from app.domain.models import ResearchAnswer
    from app.pipeline import gb_external as gb
    from app.repositories import engagements
    from app.services import ai_service
    from tests import fixture_engagement

    patched = client.patch(f"/api/engagements/{engagement_id}", json=fixture_engagement.GAP_SETUP)
    assert patched.status_code == 200, patched.text
    started = client.post(f"/api/versions/{version_id}/gap-analyses/external").json()
    brief = started["brief"]
    assert brief["scan"]["hits"] == [], brief["scan"]  # the drafted brief passes its own scan
    call = ai_service.ResearchCall(
        stage_id=gb.RESEARCH_STAGE, prompt_version="1", system="", brief=brief["text"],
        model="", max_uses=brief["brief"]["max_searches"],
    )  # fmt: skip
    research = ai_service.research_key(call)
    import anthropic

    messages = [anthropic.types.Message.model_validate(r) for r in GB_RESEARCH_ANSWER["responses"]]
    passages, results, errors, searches = ai_service._read_answer(messages)
    answer = ResearchAnswer(passages=passages, results=results, tool_errors=errors,
                            search_count=searches, stop_reason="end_turn", calls=[])  # fmt: skip
    captured = gb.capture(answer)
    with session_scope(app.state.sessions) as session:
        steps = gb.step_refs(gb.steps_of(session, version_id))
        lanes = {r.id: r.name for r in engagements.list_roles(session, engagement_id)}
    structure = ai_service.input_hash(
        gb.STRUCTURE_STAGE, gb.structure_blocks(captured, steps, lanes)
    )
    output = GBStructureOutput.model_validate(GB_STRUCTURE_ANSWER)
    checked = [
        gb.check(captured, steps, f, recency_years=5, this_year=date.today().year, terms=[])
        for f in output.findings
    ]
    verify = ai_service.input_hash(
        gb.VERIFY_STAGE, gb.verify_blocks(captured, gb.to_verify(checked))
    )
    return research, structure, verify


def write_gap() -> None:
    """The Analysis A answers for the drafted sample (after the draft answers are written)."""
    for stage in ("GA_internal", "GA_verify", "GB_research", "GB_structure", "GB_verify"):
        shutil.rmtree(MOCKS / stage, ignore_errors=True)
    with sample_app() as (app, client, built):
        key = "sk-" + "ant-" + "Fixture" * 5
        assert client.put("/api/settings/key", json={"anthropic_api_key": key}).status_code == 200
        job_id = client.post(f"/api/engagements/{built.engagement_id}/draft").json()["job_id"]
        assert app.state.worker.drain(60)
        version_id = client.get(f"/api/jobs/{job_id}").json()["target_id"]
        synthesis, verification = ga_hashes(app.state.sessions, version_id)
        research, structure, checked = gb_hashes(client, app, built.engagement_id, version_id)
    write(MOCKS, "GA_internal", "default", {"findings": [], "unknowns": []})
    write(MOCKS, "GA_verify", "default", {"verdicts": []})
    write(MOCKS, "GA_internal", synthesis, GA_INTERNAL_ANSWER)
    write(MOCKS, "GA_verify", verification, ga_verdicts(len(GA_INTERNAL_ANSWER["findings"])))
    write(MOCKS, "GB_research", "default", GB_RESEARCH_NOTHING)
    write(MOCKS, "GB_research", research, GB_RESEARCH_ANSWER)
    write(MOCKS, "GB_structure", "default", {"findings": []})
    write(MOCKS, "GB_structure", structure, GB_STRUCTURE_ANSWER)
    write(MOCKS, "GB_verify", "default", {"verdicts": []})
    write(MOCKS, "GB_verify", checked, GB_VERIFY_ANSWER)


# The interview-only sample (P12): the same engagement with the transcript as its only source, so
# the draft, review, publish and export path is tested without documents. Its S1 answers are the
# full sample's (same passages sent); the later stages keep only what the interview says: seven
# steps (no plan approval and no loading report, which only the SOPs describe), every exit
# labelled, and the S3 stances and S4 details of the full sample for those steps.
INTERVIEW_ONLY = ["interview_transcript.txt"]
INTERVIEW_ONLY_S2: dict[str, Any] = {
    "steps": [
        step("st1", "activity", "Draft load plan", "Load controller", [1, 2]),
        step("st2", "decision", "Special loads OK?", "Load controller", [3, 4]),
        step("st3", "activity", "Resolve or offload", "Airline ops", [5]),
        step("st4", "activity", "Load aircraft", "Ramp", [6, 7, 8, 9, 10]),
        step("st5", "decision", "Busy wave?", "Load controller", [11]),
        step("st6", "activity", "Read report at aircraft", "Load controller", [11]),
        step("st7", "decision", "Deviation in limits?", "Load controller", [12, 13]),
        step("st8", "approval", "Approve deviation", "Captain", [14]),
        step("st9", "activity", "Issue load sheet", "Load controller", [15]),
    ],
    "new_roles": [],
    "merge_proposals": [],
}
# The full sample's step refs (see S3_ANSWERS) → labels in the interview-only draft.
FULL_LABELS = {
    "e1": "Draft load plan", "e3": "Special loads OK?", "e4": "Resolve or offload",
    "e5": "Load aircraft", "e8": "Deviation in limits?", "e9": "Approve deviation",
    "e10": "Issue load sheet", "e6": "Busy wave?", "e7": "Read report at aircraft",
}  # fmt: skip


def step_ref_by_label(sessions: Any, version_id: str) -> dict[str, str]:
    from app.db import session_scope
    from app.pipeline.s3_calibrate import step_refs

    with session_scope(sessions) as session:
        return {st.element.label: st.ref for st in step_refs(session, version_id)}


def remap(full_ref: str, refs: dict[str, str]) -> str:
    return refs[FULL_LABELS[full_ref]] if full_ref in FULL_LABELS else full_ref


def interview_only_s3(refs: dict[str, str]) -> dict[tuple[str, int], dict[str, Any]]:
    return {
        key: {"stances": [{**s, "step_ref": remap(s["step_ref"], refs)} for s in a["stances"]]}
        for key, a in S3_ANSWERS.items()
        if key[0] in INTERVIEW_ONLY
    }


def interview_only_s4(refs: dict[str, str]) -> dict[str, Any]:
    """S4_ANSWER without the plan approval (e2): the plan goes straight to the special-loads
    check, and the constraints and flags stay on the steps whose interview claims state them.
    The deviation check is the Load controller's (in the full sample the SOP names its
    Accountable role); the T-10 KPI stays in, and is rejected, because only the SOP states it."""
    steps = [
        {**s, "step_ref": remap(s["step_ref"], refs)}
        | (
            {"raci": raci((LC, "R"), (LC, "A"))}
            if FULL_LABELS.get(s["step_ref"]) == "Deviation in limits?"
            else {}
        )
        # With no document, nothing differs from one: no variants (§3.12.11).
        | {"variant_done": variant(), "variant_documented": variant()}
        for s in S4_ANSWER["steps"]
        if s["step_ref"] != "e2"
    ]
    edges = [
        {**e, "from_ref": remap(e["from_ref"], refs), "to_ref": remap(e["to_ref"], refs)}
        for e in S4_ANSWER["edges"]
        if "e2" not in (e["from_ref"], e["to_ref"])
    ]
    edges.insert(1, edge(remap("e1", refs), remap("e3", refs)))
    phases = [
        {**p, "step_refs": [remap(r, refs) for r in p["step_refs"] if r != "e2"]}
        for p in S4_ANSWER["phases"]
    ]
    return {"phases": phases, "steps": steps, "edges": edges}


def write_interview_only() -> None:
    """The later-stage answers for the interview-only sample (after the draft answers exist)."""
    with sample_app(sources=INTERVIEW_ONLY) as (app, client, built):
        from app.pipeline import s2_canonicalise, s3_calibrate, s3b_verify

        version_id = draft_version(app, client, built)
        sessions = app.state.sessions
        write(MOCKS, "S2_canonicalise", s2_hash(sessions, version_id, built.engagement_id),
              INTERVIEW_ONLY_S2)  # fmt: skip
        run_stage(app, s2_canonicalise.canonicalise, version_id)
        refs = step_ref_by_label(sessions, version_id)
        answers = interview_only_s3(refs)
        for key, digest in s3_hashes(sessions, version_id, built.sources).items():
            write(MOCKS, "S3_calibrate", digest, answers.get(key, S3_EMPTY))
        run_stage(app, s3_calibrate.calibrate, version_id)
        for _label, (digest, count) in s3b_hashes(sessions, version_id).items():
            write(MOCKS, "S3b_verify", digest, verdicts(count))
        run_stage(app, s3b_verify.verify, version_id)
        run_stage(app, s3_calibrate.ground_in_claims, version_id)
        write(MOCKS, "S4_assemble", s4_hash(sessions, version_id), interview_only_s4(refs))


# The documents-only sample (Eric, 2026-10-20): the same engagement with its two SOPs and two job
# descriptions as the only sources, so a map can be drafted before any interview. Its S1 answers
# are the full sample's (same passages sent): eight claims, c1-c5 from SOP LC-07, c6 from SOP
# RP-02, c7-c8 from the job descriptions. Six steps, each only what the documents state. The
# documents never say what happens when a special load can't be accepted or a deviation is outside
# tolerance, so those two exits are left out (L4 fails) for Eric to add; nothing is invented.
DOCUMENTS_ONLY = ["sop_LC-07.docx", "sop_RP-02.docx", "jd_load_control_lead.docx",
                  "jd_load_controller.docx"]  # fmt: skip
DOCUMENTS_ONLY_S2: dict[str, Any] = {
    "steps": [
        step("st1", "activity", "Draft load plan", "Load controller", [1, 8]),
        step("st2", "approval", "Approve load plan", "Load control lead", [2, 7]),
        step("st3", "decision", "Special loads OK?", "Load controller", [3, 8]),
        step("st4", "activity", "Return loading report", "Ramp", [6]),
        step("st5", "decision", "Deviation in limits?", "Load control lead", [4]),
        step("st6", "activity", "Issue load sheet", "Load controller", [5, 8]),
    ],
    "new_roles": [],
    "merge_proposals": [],
}
DOCUMENTS_LABELS = {
    "e1": "Draft load plan", "e2": "Approve load plan", "e3": "Special loads OK?",
    "e8": "Deviation in limits?", "e10": "Issue load sheet",
}  # fmt: skip


def documents_only_s3(refs: dict[str, str]) -> dict[tuple[str, int], dict[str, Any]]:
    """The full sample's document stances, on this draft's steps. The SOP's corrective-action
    passage supports the deviation check here (with no interview, nothing contradicts it), and
    RP-02's loading report supports the return step."""
    answers: dict[tuple[str, int], dict[str, Any]] = {}
    for key, answer in S3_ANSWERS.items():
        if key[0] not in DOCUMENTS_ONLY:
            continue
        stances = []
        for s in answer["stances"]:
            if key[0] == "sop_RP-02.docx":
                stances.append(stance(refs["Return loading report"], "supports", s["segment_ids"],
                                      s["quote"]))  # fmt: skip
            elif s["step_ref"] in DOCUMENTS_LABELS:
                ref = refs[DOCUMENTS_LABELS[s["step_ref"]]]
                stances.append(stance(ref, "supports", s["segment_ids"], s["quote"]))
        answers[key] = {"stances": stances}
    return answers


def documents_only_s4(refs: dict[str, str]) -> dict[str, Any]:
    """Phases, RACI and details only from what the SOPs and job descriptions state."""
    plan, approve = refs["Draft load plan"], refs["Approve load plan"]
    special, report = refs["Special loads OK?"], refs["Return loading report"]
    deviation, issue = refs["Deviation in limits?"], refs["Issue load sheet"]
    return {
        "phases": [
            {"name": "Plan", "time_window": "", "step_refs": [plan, approve]},
            {"name": "Check and load", "time_window": "", "step_refs": [special, report]},
            {"name": "Close out", "time_window": "", "step_refs": [deviation, issue]},
        ],
        "steps": [
            s4_step(plan, raci=raci((LC, "R"), (LC, "A")), duration_text="By T-90",
                    handoff_out="Preliminary load plan"),
            s4_step(approve, raci=raci((LEAD, "R"), (LEAD, "A")), decision_mechanism="judgment",
                    handoff_in="Preliminary load plan", handoff_out="Plan released to Ramp"),
            s4_step(special, raci=raci((LC, "R"), (LC, "A")), decision_mechanism="rule_based",
                    decider_role=LC,
                    rule_or_threshold="Special loads checked against the acceptance checklist"),
            s4_step(report, raci=raci(("Ramp", "R"), ("Ramp", "A")),
                    duration_text="Within 10 minutes of loading completion",
                    handoff_out="Loading report to Load Control"),
            s4_step(deviation, raci=raci((LEAD, "R"), (LEAD, "A")),
                    decision_mechanism="judgment", decider_role=LEAD,
                    rule_or_threshold="Actual weights within the airline tolerance"),
            s4_step(issue, raci=raci((LC, "R"), (LC, "A")),
                    kpi="Final load sheet no later than T-10"),
        ],
        "edges": [
            edge("start", plan),
            edge(plan, approve),
            edge(approve, special, "approve", "Approve"),
            edge(approve, plan, "reject", "Rework"),
            edge(special, report, "yes", "Yes"),
            edge(report, deviation),
            edge(deviation, issue, "yes", "Within tolerance"),
            edge(issue, "end"),
        ],
    }  # fmt: skip


# S5 for the documents-only sample: every step is documented only, so each is asked about.
DOCUMENTS_ONLY_S5: dict[str, Any] = {
    "questions": [
        {"ref": "q1", "question": "The SOP says the Load controller prepares the preliminary load "
                                 "plan by T-90. Is that how and when it is done in practice?"},
        {"ref": "q2", "question": "The SOP says the Load control lead approves the preliminary "
                                 "load plan before release to Ramp. Does this approval happen in "
                                 "practice?"},
        {"ref": "q3", "question": "The SOP says special loads are checked against the acceptance "
                                 "checklist before loading. What happens when a special load "
                                 "can't be accepted?"},
        {"ref": "q4", "question": "The SOP asks Ramp to return the loading report within 10 "
                                 "minutes of loading completion. How long does it take in "
                                 "practice?"},
        {"ref": "q5", "question": "The SOP says the Load control lead decides on corrective action "
                                 "when weights deviate beyond the airline tolerance. Who decides "
                                 "in practice, and what happens next?"},
        {"ref": "q6", "question": "The SOP says the final load sheet is issued no later than T-10. "
                                 "When is it issued in practice?"},
    ]
}  # fmt: skip


def write_documents_only() -> None:
    """The later-stage answers for the documents-only sample (after the draft answers exist)."""
    with sample_app(sources=DOCUMENTS_ONLY) as (app, client, built):
        from app.pipeline import (
            s2_canonicalise,
            s3_calibrate,
            s3b_verify,
            s3c_sensemaking,
            s4_assemble,
        )

        version_id = draft_version(app, client, built)
        sessions = app.state.sessions
        write(MOCKS, "S2_canonicalise", s2_hash(sessions, version_id, built.engagement_id),
              DOCUMENTS_ONLY_S2)  # fmt: skip
        run_stage(app, s2_canonicalise.canonicalise, version_id)
        refs = step_ref_by_label(sessions, version_id)
        answers = documents_only_s3(refs)
        for key, digest in s3_hashes(sessions, version_id, built.sources).items():
            write(MOCKS, "S3_calibrate", digest, answers.get(key, S3_EMPTY))
        run_stage(app, s3_calibrate.calibrate, version_id)
        for _label, (digest, count) in s3b_hashes(sessions, version_id).items():
            write(MOCKS, "S3b_verify", digest, verdicts(count))
        run_stage(app, s3b_verify.verify, version_id)
        run_stage(app, s3_calibrate.ground_in_claims, version_id)
        run_stage(app, s3c_sensemaking.sense, version_id)  # nothing from interviews: the default
        write(MOCKS, "S4_assemble", s4_hash(sessions, version_id), documents_only_s4(refs))
        run_stage(app, s4_assemble.assemble, version_id)
        write(MOCKS, "S5_questions", s5_hash(sessions, version_id), DOCUMENTS_ONLY_S5)


# The diagram sample (2026-10-28, from Eric's cargo manual): `process_flow_diagram.pdf` alone, a
# process-flow page whose boxed stages each carry their team's label (passages p3-p7, each box
# with its label in front). Its engagement adds the role "Load control team" (the label). Each
# claim names the team or role printed on its box, so the role check (G5) finds it in the cited
# passage; one planted claim names "Airline ops", which no box says, and is rejected. The diagram
# never says where an out-of-tolerance deviation or a refused load sheet goes, so those exits are
# left out (L4, L5) for Eric to add.
DIAGRAM_SOURCES = ["process_flow_diagram.pdf"]
DIAGRAM_ROLE = {"name": "Load control team", "aliases": ["Load Control Team"]}
DIAGRAM_S1: dict[str, Any] = {
    "claims": [
        claim("activity", "The Load control team drafts the preliminary load plan by T-90.", ["p3"],
              "Draft the preliminary load plan by T-90", responsible="Load control team"),
        claim("approval", "The Load control lead approves the plan.", ["p3"],
              "Load Control Lead approves the plan", responsible="Load control lead"),
        claim("activity", "Ramp loads the ULDs as per the load plan.", ["p4"],
              "Load ULDs as per the load plan", responsible="Ramp"),
        claim("activity", "Ramp returns the loading report within 10 minutes.", ["p4"],
              "Return the loading report within 10 minutes", responsible="Ramp", duration="10 minutes"),
        claim("decision", "The Captain checks the deviation against tolerance.", ["p5"],
              "Check deviation against tolerance", decider="Captain", mechanism="judgment"),
        claim("approval", "The Captain accepts the final load sheet.", ["p5"],
              "Captain accepts the final load sheet", responsible="Captain"),
        # Planted: no box names Airline ops (G5, role not found in the cited passage).
        claim("activity", "Airline ops verify pieces, weight and dimensions.", ["p6"],
              "Verify pieces, weight and dimensions", responsible="Airline ops"),
        # Another flow on the same page (export: accept cargo, build ULDs). Both pass the checks;
        # this engagement maps load control only, so S2 sets them aside (DECISIONS 81).
        claim("activity", "Cargo acceptance verifies pieces, weight and dimensions.", ["p6"],
              "Verify pieces, weight and dimensions", responsible="Cargo acceptance"),
        claim("activity", "The Build-up team secures and nets the ULDs as required.", ["p7"],
              "Secure and net as required", responsible="Build-up team"),
    ],
    "unknowns": [{"question": "Where does a deviation outside tolerance go next?",
                  "segment_ids": ["p5"]}],
}  # fmt: skip
DIAGRAM_S2: dict[str, Any] = {
    "steps": [
        step("st1", "activity", "Draft load plan", "Load control team", [1]),
        step("st2", "approval", "Approve load plan", "Load control lead", [2]),
        step("st3", "activity", "Load ULDs", "Ramp", [3]),
        step("st4", "activity", "Return loading report", "Ramp", [4]),
        step("st5", "decision", "Deviation in limits?", "Captain", [5]),
        step("st6", "approval", "Accept final load sheet", "Captain", [6]),
    ],
    "new_roles": [],
    "merge_proposals": [],
    "outside_flow": ["c7", "c8"],
}
DIAGRAM_UNCOMPARED = "Return loading report"
DIAGRAM_QUOTES = {
    "Draft load plan": ("p3", "Draft the preliminary load plan by T-90"),
    "Approve load plan": ("p3", "Load Control Lead approves the plan"),
    "Load ULDs": ("p4", "Load ULDs as per the load plan"),
    "Return loading report": ("p4", "Return the loading report within 10 minutes"),
    "Deviation in limits?": ("p5", "Check deviation against tolerance"),
    "Accept final load sheet": ("p5", "Captain accepts the final load sheet"),
}


def diagram_s4(refs: dict[str, str]) -> dict[str, Any]:
    plan, approve = refs["Draft load plan"], refs["Approve load plan"]
    load, report = refs["Load ULDs"], refs["Return loading report"]
    deviation, accept = refs["Deviation in limits?"], refs["Accept final load sheet"]
    team = "Load control team"
    return {
        "phases": [
            {"name": "Plan", "time_window": "", "step_refs": [plan, approve]},
            {"name": "Load", "time_window": "", "step_refs": [load, report]},
            {"name": "Close out", "time_window": "", "step_refs": [deviation, accept]},
        ],
        "steps": [
            s4_step(plan, raci=raci((team, "R"), (team, "A")), duration_text="By T-90"),
            s4_step(approve, raci=raci((LEAD, "R"), (LEAD, "A")), decision_mechanism="judgment"),
            s4_step(load, raci=raci(("Ramp", "R"), ("Ramp", "A"))),
            s4_step(report, raci=raci(("Ramp", "R"), ("Ramp", "A")), work_min=10,
                    duration_text="Within 10 minutes"),
            s4_step(deviation, raci=raci(("Captain", "R"), ("Captain", "A")),
                    decision_mechanism="judgment", decider_role="Captain",
                    rule_or_threshold="Deviation against tolerance"),
            s4_step(accept, raci=raci(("Captain", "R"), ("Captain", "A")),
                    decision_mechanism="judgment"),
        ],
        "edges": [
            edge("start", plan),
            edge(plan, approve),
            edge(approve, load, "approve", "Approve"),
            edge(approve, plan, "reject", "Rework"),
            edge(load, report),
            edge(report, deviation),
            edge(deviation, accept, "yes", "Within tolerance"),
            edge(accept, "end", "approve", "Accept"),
        ],
    }  # fmt: skip


def diagram_app() -> Any:
    """The diagram sample's engagement: the PDF alone, plus the label's role."""
    return sample_app(sources=DIAGRAM_SOURCES)


def write_diagram() -> None:
    """Every answer for the diagram sample (its S1 answer first; the later stages run on it)."""
    with diagram_app() as (app, client, built):
        from app.pipeline import s2_canonicalise, s3_calibrate, s3b_verify, s4_assemble

        added = client.post(f"/api/engagements/{built.engagement_id}/roles", json=DIAGRAM_ROLE)
        assert added.status_code == 201, added.text
        for (name, _index), (stage, digest) in chunk_hashes(app.state.sessions, built).items():
            assert name in DIAGRAM_SOURCES and stage == "S1_extract_document", (name, stage)
            write(MOCKS, stage, digest, DIAGRAM_S1)
        version_id = draft_version(app, client, built)
        sessions = app.state.sessions
        write(MOCKS, "S2_canonicalise", s2_hash(sessions, version_id, built.engagement_id),
              DIAGRAM_S2)  # fmt: skip
        run_stage(app, s2_canonicalise.canonicalise, version_id)
        refs = step_ref_by_label(sessions, version_id)
        # As on Eric's cargo manual (2026-10-28), the comparison leaves one step out: its own
        # checked claims still ground it (S3 `ground_in_claims`).
        stances = [stance(refs[label], "supports", [seg], quote)
                   for label, (seg, quote) in DIAGRAM_QUOTES.items()
                   if label != DIAGRAM_UNCOMPARED]  # fmt: skip
        for _key, digest in s3_hashes(sessions, version_id, built.sources).items():
            write(MOCKS, "S3_calibrate", digest, {"stances": stances})
        run_stage(app, s3_calibrate.calibrate, version_id)
        for _label, (digest, count) in s3b_hashes(sessions, version_id).items():
            write(MOCKS, "S3b_verify", digest, verdicts(count))
        run_stage(app, s3b_verify.verify, version_id)
        run_stage(app, s3_calibrate.ground_in_claims, version_id)
        write(MOCKS, "S4_assemble", s4_hash(sessions, version_id), diagram_s4(refs))
        run_stage(app, s4_assemble.assemble, version_id)


# The Reality fixture (PRD Appendix A.12, P13a-2): S1 intent over the charter. ILLUSTRATIVE ONLY.
# The charter's passages are sent as p1 (its title) and p2-p5 (§1-§4). Four statements pass every
# check; two planted traps are turned down: RT1 (a quote that isn't in its passage, G4) and RT2
# ("within 5 minutes" where the charter says 10, G5).
CHARTER = "charter_load_control.docx"
REALITY_DIR = HERE / "reality"


def intent(kind: str, text: str, refs: list[str], quote: str, scope: str = "process",
           **target: Any) -> dict[str, Any]:  # fmt: skip
    return {
        "kind": kind, "text": text, "scope": scope, "step_key": target.pop("step_key", ""),
        "phase_name": target.pop("phase_name", ""), "metric": target.pop("metric", ""),
        "comparator": target.pop("comparator", ""), "target_value": target.pop("value", None),
        "unit": target.pop("unit", ""), "segment_ids": refs, "quote": quote,
    }  # fmt: skip


S1_INTENT_ANSWER: dict[str, Any] = {
    "statements": [
        intent("target", "Preliminary load plans are ready by T-120.", ["p2"],
               "Preliminary load plans are ready by T-120 so that widebody configurations can be "
               "checked.", "step", step_key="draft-load-plan", metric="lead_time_min",
               comparator="at_least", value=120, unit="min"),
        intent("control_objective", "Every load plan is approved before release to Ramp.", ["p3"],
               "Every load plan is approved before release to Ramp.", "step",
               step_key="approve-load-plan"),
        intent("target", "The loading report reaches Load Control within 10 minutes of loading "
               "completion.", ["p4"], "The loading report reaches Load Control within 10 minutes "
               "of loading completion.", "step", step_key="load-and-return-lir",
               metric="wait_min", comparator="at_most", value=10, unit="min"),
        intent("promise", "Load sheets are issued without delaying the departure slot.", ["p5"],
               "Load sheets are issued without delaying the departure slot."),
        # RT1: the quote is not in the cited passage.
        intent("promise", "Load sheets are issued at least 20 minutes before departure.", ["p5"],
               "Load sheets are issued at least 20 minutes before departure."),
        # RT2: the charter says 10 minutes, not 5.
        intent("target", "The loading report reaches Load Control within 5 minutes of loading "
               "completion.", ["p4"], "The loading report reaches Load Control within 10 minutes "
               "of loading completion.", "step", step_key="load-and-return-lir",
               metric="wait_min", comparator="at_most", value=5, unit="min"),
    ]
}  # fmt: skip
S1_INTENT_KEPT = 4


def intent_hashes(sessions: Any, engagement_id: str) -> tuple[str, str]:
    """The input hashes of the charter's S1 intent call and, with its answer as filed, of the
    IX_verify call over the statements that pass the checks."""
    from app.actions import intent_ai as actions
    from app.actions import redaction
    from app.db import session_scope
    from app.domain.ai_schemas import S1IntentOutput
    from app.pipeline import intent_ai as ai
    from app.pipeline.context import role_groups
    from app.services import ai_service

    with session_scope(sessions) as session:
        sources = actions._intent_sources(session, engagement_id)
        places = actions._places(session, engagement_id)
        groups = role_groups(session, engagement_id)
        terms = redaction.name_replacements(session, engagement_id)
    assert [s.source_name for s in sources] == [CHARTER], sources
    charter = sources[0]
    output = S1IntentOutput.model_validate(S1_INTENT_ANSWER)
    checked = [ai.check_statement(p, charter, places, groups, terms) for p in output.statements]
    assert [c.guardrail for c in checked] == [None, None, None, None, "G4", "G5"], [
        (c.guardrail, c.reason) for c in checked
    ]
    kinds = {s.segment_id: charter.kind for s in charter.segments}
    kept = [c for c in checked if c.kept]
    return (
        ai_service.input_hash(ai.EXTRACT_STAGE, ai.extract_blocks(charter, places)),
        ai_service.input_hash(ai.VERIFY_STAGE, ai.verify_blocks(kept, kinds)),
    )


def write_reality() -> None:
    """The S1 intent and IX_verify answers for the drafted sample with the A.12 charter."""
    for stage in ("S1_extract_intent", "IX_compare", "IX_verify"):
        shutil.rmtree(MOCKS / stage, ignore_errors=True)
    write(MOCKS, "S1_extract_intent", "default", {"statements": []})
    write(MOCKS, "IX_compare", "default", {"conflicts": []})
    write(MOCKS, "IX_verify", "default", {"verdicts": []})
    with sample_app() as (app, client, built):
        key = "sk-" + "ant-" + "Fixture" * 5
        assert client.put("/api/settings/key", json={"anthropic_api_key": key}).status_code == 200
        data = (REALITY_DIR / CHARTER).read_bytes()
        uploaded = client.post(
            f"/api/engagements/{built.engagement_id}/sources",
            files={"file": (CHARTER, data, "application/octet-stream")},
        )
        assert uploaded.status_code == 201, uploaded.text
        assert app.state.worker.drain(60)
        job_id = client.post(f"/api/engagements/{built.engagement_id}/draft").json()["job_id"]
        assert app.state.worker.drain(60)
        assert client.get(f"/api/jobs/{job_id}").json()["status"] == "done"
        extract, verification = intent_hashes(app.state.sessions, built.engagement_id)
    write(MOCKS, "S1_extract_intent", extract, S1_INTENT_ANSWER)
    write(MOCKS, "IX_verify", verification, {
        "verdicts": [{"item_ref": f"v{n}", "verdict": "supported",
                      "reason": "The charter states it in these words."}
                     for n in range(1, S1_INTENT_KEPT + 1)]
    })  # fmt: skip


def write(root: Path, stage: str, key: str, data: object) -> None:
    (root / stage).mkdir(parents=True, exist_ok=True)
    (root / stage / f"{key}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    hashes = current_hashes()
    for root in (MOCKS, TRAPS):
        for stage in (*S1_STAGES, "S0_ocr_page"):
            shutil.rmtree(root / stage, ignore_errors=True)
    for key, (stage, digest) in hashes.items():
        fill = as_interview if stage == "S1_extract_interview" else (lambda a: a)
        write(MOCKS, stage, digest, fill(ANSWERS.get(key, EMPTY)))
        if key in TRAPS_ANSWERS:
            write(TRAPS, stage, digest, fill(TRAPS_ANSWERS[key]))
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
            ("S3c_worktype", S3C_EMPTY),
            ("S4_assemble", S4_EMPTY),
            ("S5_questions", S5_EMPTY),
        ):
            shutil.rmtree(root / stage, ignore_errors=True)
            write(root, stage, "default", empty)
    from app.pipeline import (
        s2_canonicalise,
        s3_calibrate,
        s3b_verify,
        s3c_sensemaking,
        s4_assemble,
    )

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
        run_stage(app, s3_calibrate.ground_in_claims, version_id)
        digest, names, items = s3c_call(sessions, version_id)
        write(MOCKS, "S3c_worktype", digest, s3c_answer(names, items))
        run_stage(app, s3c_sensemaking.sense, version_id)
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
    write_interview_only()
    write_documents_only()
    write_diagram()
    write_gap()
    write_reality()
    print(
        f"Wrote {len(hashes)} chunk answers, the S2 answer and {len(TRAPS_ANSWERS)} trap answers."
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["gap"]:  # only the gap-analysis answers
        write_gap()
    elif sys.argv[1:] == ["interview"]:  # only the interview-only sample's answers
        write_interview_only()
    elif sys.argv[1:] == ["documents"]:  # only the documents-only sample's answers
        write_documents_only()
    elif sys.argv[1:] == ["diagram"]:  # only the diagram sample's answers (2026-10-28)
        write_diagram()
    elif sys.argv[1:] == ["reality"]:  # only the Reality fixture's intent answers (A.12)
        write_reality()
    else:
        main()
