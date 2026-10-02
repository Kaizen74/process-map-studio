"""The PRD Appendix A load-control engagement, set up through the real API (tests and fixtures).

Roles, the sample sources and the speaker mappings (A.1: Interviewer → interviewer, Priya Nair →
Load controller; A.10: Ramp duty manager → Ramp) are always the same, so the passages sent to
Claude, and therefore the mock-answer hashes, are the same in every test.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from tests.uploads import FIXTURES, wait_for_jobs

ROLES: list[tuple[str, list[str]]] = [
    ("Load controller", ["LC", "Load Controller"]),
    ("Load control lead", ["Load Control Lead"]),
    ("Ramp", ["Ramp Supervisor", "Ramp agent"]),
    ("Airline ops", ["airline"]),
    ("Captain", []),
]
SOURCES = [
    "interview_transcript.txt",
    "sop_LC-07.docx",
    "sop_RP-02.docx",
    "jd_load_control_lead.docx",
    "jd_load_controller.docx",
    # A.10 (P4c, C3): the landscape interview with the Ramp duty manager, part of the same
    # engagement from P4c onward.
    "landscape_ramp_lead.txt",
]


@dataclass
class FixtureEngagement:
    engagement_id: str
    roles: dict[str, str]  # role name → id
    sources: dict[str, str]  # file name → source id


# The engagement Setup for the gap-analysis fixtures (PRD Appendix A.7), set with PATCH
# /engagements/{id} where a test needs it (the other baselines don't use these fields).
GAP_SETUP = {
    "industry": "Aviation ground handling",
    "adjacent_industries": ["Air cargo", "Airport operations"],
    "confidential_terms": ["Acme Ground Services", "LC-07", "RP-02"],
}


def build(client: TestClient, sources: list[str] = SOURCES) -> FixtureEngagement:
    eid = client.post(
        "/api/engagements",
        json={
            "name": "Load control",
            "trigger": "Flight scheduled",
            "end_point": "Final load sheet issued",
        },
    ).json()["id"]
    roles = {}
    for name, aliases in ROLES:
        body = {"name": name, "aliases": aliases}
        roles[name] = client.post(f"/api/engagements/{eid}/roles", json=body).json()["id"]
    uploaded = {}
    for name in sources:
        response = client.post(
            f"/api/engagements/{eid}/sources",
            files={"file": (name, (FIXTURES / name).read_bytes(), "application/octet-stream")},
        )
        assert response.status_code == 201, response.text
        uploaded[name] = response.json()["id"]
    wait_for_jobs(client)
    if "interview_transcript.txt" in uploaded:
        client.put(
            f"/api/sources/{uploaded['interview_transcript.txt']}/speakers",
            json={"Interviewer": "interviewer", "Priya Nair": roles["Load controller"]},
        )
    if "landscape_ramp_lead.txt" in uploaded:
        # Its name doesn't say "interview", so it is read as a document until Eric sets the kind.
        changed = client.patch(f"/api/sources/{uploaded['landscape_ramp_lead.txt']}",
                               json={"kind": "interview_transcript"})  # fmt: skip
        assert changed.status_code == 200, changed.text
        wait_for_jobs(client)
        client.put(
            f"/api/sources/{uploaded['landscape_ramp_lead.txt']}/speakers",
            json={"Interviewer": "interviewer", "Ramp duty manager": roles["Ramp"]},
        )
    return FixtureEngagement(engagement_id=eid, roles=roles, sources=uploaded)
