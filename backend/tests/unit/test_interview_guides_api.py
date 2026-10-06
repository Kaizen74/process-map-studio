"""Tailored interview guides (API_CONTRACT.md → Tailored interview guides; PRD Appendix F.8 to F.9,
criterion 80): made from a profile on the illustrative Appendix A engagement (Claude mocked),
versioned, audited and exported to Word and Markdown in the template layout."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import docx
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import load_config
from app.db import session_scope
from app.domain.result import Err
from app.main import create_app
from app.repositories.tables import AuditRow
from app.services import interview_templates as templates
from app.services import wording
from tests.unit.test_review_actions import Drafted, drafted
from tests.uploads import wait_for_jobs

__all__ = ["drafted"]


def guide_url(d: Drafted) -> str:
    return f"/api/engagements/{d.engagement_id}/interview-guide"


def profile(d: Drafted, **body: Any) -> str:
    response = d.client.post(f"/api/engagements/{d.engagement_id}/profiles", json=body)
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def role(d: Drafted, name: str) -> str:
    roles = d.client.get(f"/api/engagements/{d.engagement_id}/roles").json()
    return str(next(r["id"] for r in roles if r["name"] == name))


def start(d: Drafted, pid: str) -> dict[str, Any]:
    """POST the guide (a job since C5b) and wait for it; the finished job."""
    started = d.client.post(guide_url(d), json={"profile_id": pid})
    assert started.status_code == 202, started.text
    assert started.json()["profile_id"] == pid
    wait_for_jobs(d.client)
    return dict(d.client.get(f"/api/jobs/{started.json()['job_id']}").json())


def make(d: Drafted, pid: str) -> dict[str, Any]:
    """Make a guide and return the new version."""
    job = start(d, pid)
    assert job["status"] == "done", job
    guide = d.client.get(guide_url(d), params={"profile_id": pid})
    assert guide.status_code == 200, guide.text
    return dict(guide.json())


def guide_audit(d: Drafted) -> list[dict[str, Any]]:
    with session_scope(d.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        rows = session.scalars(
            select(AuditRow)
            .where(AuditRow.engagement_id == d.engagement_id,
                   AuditRow.target_type == "interview_guide")
            .order_by(AuditRow.created_at)
        )  # fmt: skip
        return [{"action": r.action, "after": r.after} for r in rows]


def test_a_practice_guide_is_filled_in_from_the_profile_and_the_map(drafted: Drafted) -> None:
    pid = profile(drafted, role_id=role(drafted, "Ramp"), stakeholder_group="Ramp agents",
                  interview_type="practice", referred_by_role="Load controller")  # fmt: skip
    guide = make(drafted, pid)
    assert (guide["version"], guide["interview_type"], guide["edited"]) == (1, "practice", False)
    doc = guide["document"]
    assert doc["title"] == "Practice interview guide: Ramp · Ramp agents"
    assert doc["header_values"] == {"Engagement / process": "Load control",
                                    "Interviewee role": "Ramp",
                                    "Stakeholder group": "Ramp agents",
                                    "Referred by (role)": "Load controller"}  # fmt: skip
    assert doc["opener"][0].startswith(
        "We're mapping the Load control process, from Flight scheduled to Final load sheet issued "
        "for Load control. I understand your team plays a key role in Ramp agents, so Load "
        "controller suggested")  # fmt: skip
    # Rule 5: the one step only the documents describe becomes an M6.5 probe, and only there.
    m6 = next(t for t in doc["tables"] if t["label"].startswith("M6 "))
    probe = templates.SOP_PROBE.format(step="Approve load plan")
    m6_5 = next(r for r in m6["rows"] if r["id"] == "M6.5")
    assert m6_5["held_back"] == [probe]  # parked in M6, apart from the bank's probes
    assert probe not in m6_5["probes"]
    md = drafted.client.get(guide_url(drafted) + f"/export?profile_id={pid}&format=md").text
    assert md.count(probe) == 1 and wording.banned_words(md) == []
    # A second guide is a new version; the latest is what GET returns.
    again = make(drafted, pid)
    assert again["version"] == 2
    latest = drafted.client.get(guide_url(drafted), params={"profile_id": pid}).json()
    assert latest["id"] == again["id"]
    assert guide_audit(drafted) == [
        {"action": "Made interview guide",
         "after": {"profile_id": pid, "version": n, "interview_type": "practice",
                   "role_module": "not asked"}}
        for n in (1, 2)
    ]  # fmt: skip


def test_a_follow_up_guide_plays_back_the_sme_s_words(drafted: Drafted) -> None:
    first = profile(drafted, stakeholder_group="Load control", interview_type="practice")
    pid = profile(drafted, role_id=role(drafted, "Load controller"), interview_type="follow_up",
                  previous_profile_id=first)  # fmt: skip
    doc = make(drafted, pid)["document"]
    coverage = drafted.client.get(f"/api/versions/{drafted.version_id}/coverage").json()
    covered = [k.replace("_", " ") for k, v in coverage["dimensions"].items()
               if v["status"] == "covered"]  # fmt: skip
    assert doc["opener"][1] == f"Last time we covered {', '.join(covered)}; today I'd like to " \
        "pick up where we left off."  # fmt: skip
    f_series = next(t for t in doc["tables"] if t["label"].startswith("F-series"))
    filled = f_series["rows"][6:]  # after F1 to F6, the five blank reflective-probe rows
    assert [r["id"] for r in filled] == ["F2"] * 5
    assert [r["wording"] for r in filled] == [p["question"] for p in coverage["probes"][:5]]
    assert all(r["minutes"] for r in filled)
    # No earlier interview named: [topics] stays for the interviewer to fill.
    alone = profile(drafted, stakeholder_group="Airline ops", interview_type="follow_up")
    doc = make(drafted, alone)["document"]
    assert "[topics]" in doc["opener"][1]


def test_word_and_markdown_exports(drafted: Drafted) -> None:
    pid = profile(drafted, role_id=role(drafted, "Ramp"), interview_type="practice")
    guide = make(drafted, pid)
    word = drafted.client.get(guide_url(drafted) + "/export",
                              params={"profile_id": pid, "format": "docx"})  # fmt: skip
    assert word.status_code == 200, word.text
    assert word.headers["content-disposition"] == (
        'attachment; filename="interview-guide-practice-ramp.docx"')  # fmt: skip
    reopened = docx.Document(BytesIO(word.content))
    assert reopened.paragraphs[0].text == guide["document"]["title"]
    entries = {r.cells[0].text: r.cells[1].text for r in reopened.tables[0].rows[1:]}
    assert entries["Interviewee role"] == "Ramp" and entries["Date"] == ""
    md = drafted.client.get(guide_url(drafted) + "/export",
                            params={"profile_id": pid, "format": "md"})  # fmt: skip
    assert md.headers["content-type"].startswith("text/markdown")
    assert md.text.startswith("# Practice interview guide: Ramp\n")


def test_hidden_names_never_reach_the_guide(drafted: Drafted) -> None:
    pid = profile(drafted, role_id=role(drafted, "Ramp"), stakeholder_group="Kestrel bay team",
                  interview_type="practice")  # fmt: skip
    # Names added to the list after the profile was made, one of them inside a step label.
    terms = f"/api/engagements/{drafted.engagement_id}/redaction-terms"
    for term in ("Kestrel", "Approve"):
        assert drafted.client.post(terms, json={"term": term}).status_code == 201
    doc = make(drafted, pid)["document"]
    assert "Stakeholder group" not in doc["header_values"]
    assert doc["title"] == "Practice interview guide"
    for fmt in ("md", "docx"):
        file = drafted.client.get(guide_url(drafted) + "/export",
                                  params={"profile_id": pid, "format": fmt})  # fmt: skip
        text = file.text if fmt == "md" else "\n".join(
            c.text for t in docx.Document(BytesIO(file.content)).tables
            for r in t.rows for c in r.cells)  # fmt: skip
        assert "Kestrel" not in text and "Approve load plan" not in text


def test_errors(drafted: Drafted) -> None:
    client = drafted.client
    other = client.post("/api/engagements", json={"name": "Other"}).json()
    theirs = client.post(
        f"/api/engagements/{other['id']}/profiles",
        json={"stakeholder_group": "Ramp", "interview_type": "practice"},
    ).json()
    for body in ({"profile_id": theirs["id"]}, {"profile_id": "nope"}):
        response = client.post(guide_url(drafted), json=body)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["details"]["field"] == "profile_id"
    assert client.post(guide_url(drafted), json={"profile_id": "x", "who": "y"}).status_code == 422
    missing = client.post("/api/engagements/nope/interview-guide", json={"profile_id": "x"})
    assert missing.status_code == 404
    pid = profile(drafted, stakeholder_group="Ramp", interview_type="landscape")
    none_yet = client.get(guide_url(drafted), params={"profile_id": pid})
    assert none_yet.status_code == 404
    assert none_yet.json()["error"]["message"] == "No guide yet for this interviewee."
    assert (
        client.get(
            guide_url(drafted) + "/export", params={"profile_id": pid, "format": "md"}
        ).status_code
        == 404
    )
    make(drafted, pid)
    pdf = client.get(guide_url(drafted) + "/export", params={"profile_id": pid, "format": "pdf"})
    assert pdf.status_code == 422 and pdf.json()["error"]["message"] == "Choose docx or md."
    # Another engagement's URL never shows this engagement's guide.
    assert client.get(f"/api/engagements/{other['id']}/interview-guide",
                      params={"profile_id": pid}).status_code == 404  # fmt: skip
    assert guide_audit(drafted) == [
        {"action": "Made interview guide",
         "after": {"profile_id": pid, "version": 1, "interview_type": "landscape",
                   "role_module": "drafted"}}
    ]  # fmt: skip


def test_the_list_shows_each_interviewee_s_latest_guide(drafted: Drafted) -> None:
    url = f"/api/engagements/{drafted.engagement_id}/interview-guides"
    assert drafted.client.get(url).json() == []
    ramp = profile(drafted, role_id=role(drafted, "Ramp"), interview_type="practice")
    lead = profile(drafted, stakeholder_group="Load control", interview_type="landscape")
    for pid in (ramp, lead, ramp):
        make(drafted, pid)
    listed = drafted.client.get(url).json()
    assert [(g["profile_id"], g["version"], g["interview_type"]) for g in listed] == [
        (ramp, 2, "practice"), (lead, 1, "landscape")]  # fmt: skip
    assert "document" not in listed[0]
    assert drafted.client.get("/api/engagements/nope/interview-guides").status_code == 404


MOCK_KEPT = [  # tests/fixtures/mock_responses/IG_generate/default.json without its SOP question
    ("L3", "When the Ramp team hands the loading report back to the Load controller, what passes "
           "across and how?"),
    ("L4", "When a special load turns up at the aircraft, who on the Ramp side decides what "
           "happens next, and who is told?"),
    ("L5", "Which activities around loading does the Ramp team manage, and which belong to Load "
           "control? Where do they overlap?"),
    ("L4", "Who on the Ramp side can stop loading if something looks wrong, and how do they let "
           "the others know?"),
]  # fmt: skip


def module(doc: dict[str, Any]) -> list[dict[str, Any]]:
    table = next(t for t in doc["tables"] if t["label"].startswith(templates.ROLE_MODULE))
    return list(table["rows"])


def test_a_landscape_guide_gets_a_checked_role_module(drafted: Drafted) -> None:
    """F.4 and F.8 rule 3, criteria 61 and 69: Claude drafts the role module (mocked: five
    questions, one quoting the SOP); the app keeps the four that pass, with targets and minutes."""
    pid = profile(drafted, role_id=role(drafted, "Ramp"), stakeholder_group="Ramp",
                  interview_type="landscape", referred_by_role="Load controller")  # fmt: skip
    job = start(drafted, pid)
    assert job["status"] == "done", job
    assert job["message"] == "Guide version 1 made. 4 role-module questions drafted and checked."
    assert [s["status"] for s in job["stages"]] == ["done"] * 4
    assert job["usage"]["calls"] == 1  # one IG_generate call, recorded against the job
    doc = drafted.client.get(guide_url(drafted), params={"profile_id": pid}).json()["document"]
    rows = module(doc)
    assert [(r["id"], r["wording"]) for r in rows] == [
        (f"RM{n}", wording) for n, (_, wording) in enumerate(MOCK_KEPT, start=1)]  # fmt: skip
    bank = templates.load_bank()
    assert not isinstance(bank, Err)
    for row, (base, _) in zip(rows, MOCK_KEPT, strict=True):
        assert row["targets"] == bank.value.question(base).targets
        assert 1 <= len(row["probes"]) <= 3 and row["minutes"] == "2"
    assert doc["generation_note"] == ""
    md = drafted.client.get(guide_url(drafted) + "/export",
                            params={"profile_id": pid, "format": "md"}).text  # fmt: skip
    assert "| RM1 | When the Ramp team hands" in md and "The SOP says" not in md
    asked = " ".join(f"{r['wording']} {' '.join(r['probes'])}" for t in doc["tables"]
                     for r in t["rows"])  # fmt: skip
    assert wording.sop_claims(asked) == []  # a Landscape guide has no M6: no SOP claim anywhere
    assert guide_audit(drafted)[-1]["after"]["role_module"] == "drafted"


def test_role_questions_naming_a_hidden_name_are_left_out(drafted: Drafted) -> None:
    """The group's name is on the hidden-names list: it is replaced before anything is sent, and
    Claude's questions that still contain it (the mock's all do) are left out, rows blank."""
    pid = profile(drafted, role_id=role(drafted, "Load controller"), interview_type="landscape")
    terms = f"/api/engagements/{drafted.engagement_id}/redaction-terms"
    assert drafted.client.post(terms, json={"term": "Ramp"}).status_code == 201
    job = start(drafted, pid)
    assert job["status"] == "done", job
    doc = drafted.client.get(guide_url(drafted), params={"profile_id": pid}).json()["document"]
    assert [r["id"] for r in module(doc)] == ["", "", "", ""]
    assert doc["generation_note"] == (
        "The role-module rows are left blank for you: none of Claude's questions passed the "
        "app's checks.")  # fmt: skip
    assert job["message"] == "Guide version 1 made. " + doc["generation_note"]
    assert guide_audit(drafted)[-1]["after"]["role_module"] == "left blank"


def test_without_a_key_the_guide_is_still_made_with_blank_role_rows(env_file: Path) -> None:
    config = load_config({"PMS_ENV_FILE": str(env_file), "MOCK_CLAUDE": "0",
                          "DATA_DIR": str(env_file.parent / "data")})  # fmt: skip
    with TestClient(create_app(config)) as client:
        eid = client.post("/api/engagements", json={"name": "Load control"}).json()["id"]
        body = {"stakeholder_group": "Ramp", "interview_type": "landscape"}
        pid = client.post(f"/api/engagements/{eid}/profiles", json=body).json()["id"]
        started = client.post(f"/api/engagements/{eid}/interview-guide", json={"profile_id": pid})
        assert started.status_code == 202
        wait_for_jobs(client)
        job = client.get(f"/api/jobs/{started.json()['job_id']}").json()
        assert job["status"] == "done", job
        assert [s["status"] for s in job["stages"]] == ["done", "failed", "done", "done"]
        guide = client.get(f"/api/engagements/{eid}/interview-guide",
                           params={"profile_id": pid}).json()  # fmt: skip
        assert guide["document"]["generation_note"] == (
            "The role-module rows are left blank for you: Add your Claude API key in Settings "
            "first.")  # fmt: skip
        assert job["usage"]["calls"] == 0


def test_only_landscape_guides_ask_claude(drafted: Drafted) -> None:
    for kind in ("practice", "follow_up"):
        pid = profile(drafted, stakeholder_group="Ramp", interview_type=kind)
        job = start(drafted, pid)
        assert job["usage"]["calls"] == 0 and job["message"] == "Guide version 1 made."
