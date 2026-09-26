"""The PRD Appendix A load-control engagement, set up through the real API (tests and fixtures).

Roles, the sample sources and the A.1 speaker mapping (Interviewer → interviewer, Priya Nair →
Load controller) are always the same, so the passages sent to Claude, and therefore the mock-answer
hashes, are the same in every test.
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
]


@dataclass
class FixtureEngagement:
    engagement_id: str
    roles: dict[str, str]  # role name → id
    sources: dict[str, str]  # file name → source id


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
    return FixtureEngagement(engagement_id=eid, roles=roles, sources=uploaded)
