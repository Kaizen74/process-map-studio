"""Eric's own suggested probes (DECISIONS 113): typed or pasted before interviews, checked like
every text in a guide, offered beside the guide, never a question of it, a claim or a step."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.unit.test_compass_handoff import client as client  # the shared fixture
from tests.uploads import wait_for_jobs


def test_probes_are_pasted_kept_checked_and_offered_beside_a_guide(client: TestClient) -> None:
    eid = client.post("/api/engagements", json={"name": "Load control"}).json()["id"]
    url = f"/api/engagements/{eid}/probes"
    pasted = "Is it done the same way on every shift?\n\n  Where is the plan  really built?  \n"
    made = client.post(url, json={"text": pasted, "about": "Step 2, build-up planning"})
    assert made.status_code == 201, made.text
    assert [(p["text"], p["about"]) for p in made.json()] == [
        ("Is it done the same way on every shift?", "Step 2, build-up planning"),
        ("Where is the plan really built?", "Step 2, build-up planning"),
    ]
    first = made.json()[0]["id"]
    edited = client.patch(f"/api/probes/{first}", json={"text": "Is it the same on every shift?"})
    assert edited.status_code == 200 and edited.json()["text"] == "Is it the same on every shift?"
    # Checked like the guide's own wording: no banned word, no name to hide, one line.
    assert client.post(f"{url}", json={"text": "Was that a violation?"}).status_code == 422
    client.post(f"/api/engagements/{eid}/redaction-terms",
                json={"term": "Priya Nair", "replacement": "the load controller"})  # fmt: skip
    refused = client.post(url, json={"text": "Ask Priya Nair about it."})
    assert refused.status_code == 422 and "names to hide" in refused.json()["error"]["message"]
    assert client.post(url, json={"text": "   "}).status_code == 422
    assert client.post(url, json={"text": "x" * 301}).status_code == 422
    # All or nothing: one bad line keeps the rest out too.
    assert client.post(url, json={"text": "Fine line?\nA violation?"}).status_code == 422
    assert len(client.get(url).json()) == 2
    # Offered beside a guide, apart from the Compass prompts.
    body = {"stakeholder_group": "Ramp", "interview_type": "practice"}
    pid = client.post(f"/api/engagements/{eid}/profiles", json=body).json()["id"]
    assert client.post(f"/api/engagements/{eid}/interview-guide",
                       json={"profile_id": pid}).status_code == 202  # fmt: skip
    wait_for_jobs(client)
    guide = client.get(f"/api/engagements/{eid}/interview-guide", params={"profile_id": pid}).json()
    assert [p["text"] for p in guide["own_probes"]] == [
        "Is it the same on every shift?", "Where is the plan really built?",
    ]  # fmt: skip
    assert guide["suggested_probes"] == []  # no hand-off
    words = str(guide["document"])
    assert "Where is the plan really built?" not in words  # never part of the guide itself
    # Removed: gone from the list and from beside the guide.
    assert client.delete(f"/api/probes/{first}").status_code == 204
    assert client.delete(f"/api/probes/{first}").status_code == 404
    assert [p["text"] for p in client.get(url).json()] == ["Where is the plan really built?"]
    assert client.get("/api/engagements/nope/probes").status_code == 404
