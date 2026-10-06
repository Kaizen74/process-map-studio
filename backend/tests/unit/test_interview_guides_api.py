"""Tailored interview guides (API_CONTRACT.md → Tailored interview guides; PRD Appendix F.8 to F.9,
criterion 80): made from a profile on the illustrative Appendix A engagement (Claude mocked),
versioned, audited and exported to Word and Markdown in the template layout."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import docx
from sqlalchemy import select

from app.db import session_scope
from app.repositories.tables import AuditRow
from app.services import interview_templates as templates
from app.services import wording
from tests.unit.test_review_actions import Drafted, drafted

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
    made = drafted.client.post(guide_url(drafted), json={"profile_id": pid})
    assert made.status_code == 201, made.text
    guide = made.json()
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
    assert next(r for r in m6["rows"] if r["id"] == "M6.5")["probes"][-1] == probe
    md = drafted.client.get(guide_url(drafted) + f"/export?profile_id={pid}&format=md").text
    assert md.count(probe) == 1 and wording.banned_words(md) == []
    # A second guide is a new version; the latest is what GET returns.
    again = drafted.client.post(guide_url(drafted), json={"profile_id": pid}).json()
    assert again["version"] == 2
    latest = drafted.client.get(guide_url(drafted), params={"profile_id": pid}).json()
    assert latest["id"] == again["id"]
    assert guide_audit(drafted) == [
        {"action": "Made interview guide",
         "after": {"profile_id": pid, "version": n, "interview_type": "practice"}}
        for n in (1, 2)
    ]  # fmt: skip


def test_a_follow_up_guide_plays_back_the_sme_s_words(drafted: Drafted) -> None:
    first = profile(drafted, stakeholder_group="Load control", interview_type="practice")
    pid = profile(drafted, role_id=role(drafted, "Load controller"), interview_type="follow_up",
                  previous_profile_id=first)  # fmt: skip
    doc = drafted.client.post(guide_url(drafted), json={"profile_id": pid}).json()["document"]
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
    doc = drafted.client.post(guide_url(drafted), json={"profile_id": alone}).json()["document"]
    assert "[topics]" in doc["opener"][1]


def test_word_and_markdown_exports(drafted: Drafted) -> None:
    pid = profile(drafted, role_id=role(drafted, "Ramp"), interview_type="practice")
    guide = drafted.client.post(guide_url(drafted), json={"profile_id": pid}).json()
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
    doc = drafted.client.post(guide_url(drafted), json={"profile_id": pid}).json()["document"]
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
    client.post(guide_url(drafted), json={"profile_id": pid})
    pdf = client.get(guide_url(drafted) + "/export", params={"profile_id": pid, "format": "pdf"})
    assert pdf.status_code == 422 and pdf.json()["error"]["message"] == "Choose docx or md."
    # Another engagement's URL never shows this engagement's guide.
    assert client.get(f"/api/engagements/{other['id']}/interview-guide",
                      params={"profile_id": pid}).status_code == 404  # fmt: skip
    assert guide_audit(drafted) == [
        {"action": "Made interview guide",
         "after": {"profile_id": pid, "version": 1, "interview_type": "landscape"}}
    ]  # fmt: skip


def test_the_list_shows_each_interviewee_s_latest_guide(drafted: Drafted) -> None:
    url = f"/api/engagements/{drafted.engagement_id}/interview-guides"
    assert drafted.client.get(url).json() == []
    ramp = profile(drafted, role_id=role(drafted, "Ramp"), interview_type="practice")
    lead = profile(drafted, stakeholder_group="Load control", interview_type="landscape")
    for pid in (ramp, lead, ramp):
        drafted.client.post(guide_url(drafted), json={"profile_id": pid})
    listed = drafted.client.get(url).json()
    assert [(g["profile_id"], g["version"], g["interview_type"]) for g in listed] == [
        (ramp, 2, "practice"), (lead, 1, "landscape")]  # fmt: skip
    assert "document" not in listed[0]
    assert drafted.client.get("/api/engagements/nope/interview-guides").status_code == 404
