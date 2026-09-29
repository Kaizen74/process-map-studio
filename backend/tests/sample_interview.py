"""Eric's sample interview: Pei Fen, exported from Otter.ai, used exactly as exported.

An exception to "fixtures are illustrative only" (Eric's decision, DECISIONS.md 2026-09-29): it is
a real conversation, kept in the private repository to test an interview-only engagement (P12).
The engagement is set up through the real API: Pei Fen ("Speaker 3") is the SME; every other
speaker is treated as an interviewer, and the people named in the conversation are on the
redaction list, so no name reaches the map, the AI answers or an export.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from tests.paths import BACKEND_ROOT
from tests.uploads import wait_for_jobs

FOLDER = BACKEND_ROOT / "tests" / "fixtures" / "interview_pei_fen"
FILE = "Interview_with_Pei_Fen_otter_ai_transcript.txt"
SME = "Speaker 3"
SME_ROLE = "Finance capability SME"
OTHERS = ["Speaker 1", "Speaker 2", "Speaker 4", "Speaker 5", "Speaker 6", "Unknown Speaker"]
# Everyone named in the conversation, with the spellings Otter produced.
NAMES = [
    "Pei Fen", "Peifen", "Payfan", "Payfant", "Payfront", "Payphon", "Payphone", "Python",
    "Steve", "Stephen", "Eric", "Ruel", "Roel", "Vinay", "Nick", "Yan Petre", "Ian", "David",
    "Ritu", "Tavika", "Taviga", "Willamine", "Yoron", "Liang Chu", "Liangshu",
    "Christopher Stevens",
]  # fmt: skip
SETUP = {
    "name": "Competency assessment (sample interview)",
    "trigger": "Competency review cycle starts",
    "end_point": "Development actions agreed",
}


@dataclass
class SampleInterview:
    engagement_id: str
    source_id: str
    role_id: str


def build(client: TestClient) -> SampleInterview:
    """The engagement with only the interview: read, speakers mapped, names on the list."""
    eid = client.post("/api/engagements", json=SETUP).json()["id"]
    role = client.post(f"/api/engagements/{eid}/roles", json={"name": SME_ROLE, "aliases": []})
    rid = role.json()["id"]
    for name in NAMES:
        added = client.post(f"/api/engagements/{eid}/redaction-terms", json={"term": name})
        assert added.status_code == 201, added.text
    uploaded = client.post(
        f"/api/engagements/{eid}/sources",
        files={"file": (FILE, (FOLDER / FILE).read_bytes(), "application/octet-stream")},
        data={"kind": "interview_transcript"},
    )
    assert uploaded.status_code == 201, uploaded.text
    sid = uploaded.json()["id"]
    wait_for_jobs(client)
    mapping = {SME: rid} | {label: "interviewer" for label in OTHERS}
    mapped = client.put(f"/api/sources/{sid}/speakers", json=mapping)
    assert mapped.status_code == 200, mapped.text
    return SampleInterview(engagement_id=eid, source_id=sid, role_id=rid)
