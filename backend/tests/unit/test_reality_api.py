"""The Reality snapshot end to end on fixture A.12 (P13b; API_CONTRACT.md → Reality snapshot; PRD
§3.18): the codes and figures match the discrepancy engine's, a draft's snapshot is kept while
its inputs are unchanged and follows Eric's decisions, publishing freezes it (also under later
decisions), the first request for a version published with the switch off freezes it, and no
AI call is made (constraint 26)."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db import session_scope
from app.repositories import reality_snapshots
from app.services import ai_service, wording
from tests.unit.test_discrepancies_a12 import Reality
from tests.unit.test_discrepancies_a12 import reality as reality  # the shared fixture
from tests.unit.test_intent_api import engagement as engagement  # the shared fixture


def snapshot(client: TestClient, version_id: str) -> dict[str, Any]:
    response = client.get(f"/api/versions/{version_id}/reality")
    assert response.status_code == 200, response.text
    return dict(response.json())


def switch(client: TestClient, on: bool) -> None:
    response = client.put("/api/settings/modules", json={"reality_views_enabled": on})
    assert response.status_code == 200, response.text


def publish(client: TestClient, version_id: str) -> None:
    """Every step confirmed, every merge proposal decided, then published (as Eric would)."""
    graph = client.get(f"/api/versions/{version_id}/graph").json()
    for e in graph["elements"]:
        if e["kind"] not in ("start", "end"):
            assert client.post(f"/api/elements/{e['id']}/confirm").status_code == 200
    for m in client.get(f"/api/versions/{version_id}/merge-proposals").json():
        if m.get("decision") == "pending":
            body = {"decision": "split"}
            assert client.post(f"/api/merge-proposals/{m['id']}/decision", json=body).is_success
    response = client.post(f"/api/versions/{version_id}/publish")
    assert response.status_code == 200, response.text


def stored(client: TestClient, version_id: str) -> reality_snapshots.Stored | None:
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        return reality_snapshots.get(session, version_id)


def test_a12_snapshot(reality: Reality, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_ai(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the Reality snapshot called Claude")

    monkeypatch.setattr(ai_service, "call_claude", no_ai)
    client = reality.engagement.client
    s = snapshot(client, reality.version_id)
    assert (s["frozen"], s["draft"], s["data_label"]) == (False, True, "Draft: figures may change")
    assert s["evidence"]["text"] == "2 documents · 2 interviews · 200 cases"
    assert [(t["figure"]["text"], t["caption"]) for t in s["tiles"]] == [
        ("70%", "of cases follow the manual"),
        ("100%", "of cases without a record (X1)"),
        ("21%", "of cases meet a confirmed target"),
        ("6 h a month", "beyond the designed time"),
    ]
    rv1, rv2, rv3 = (s["views"][v] for v in ("rv1", "rv2", "rv3"))
    assert rv1["headline"] == (
        "Only 70% of cases follow the manual. 100% of cases leave no record of Approve load plan."
    )
    assert rv2["headline"] == (
        "Check and load is the hotspot: 53 extra minutes a case and 24 hours a month."
    )
    assert rv3["headline"] == (
        "2 gaps put the intent at risk; none is yet clearly a practice to keep.")  # fmt: skip
    assert rv2["stack"]["lens"]["label"] == "Largest loss: Check and load"
    assert [r["name"] for r in rv1["glance"]["routes"]] == [
        "As documented", "Repeats Draft load plan", "Adds Manual weight override",
        "Other: 1 rarer route"]  # fmt: skip
    assert [r["codes"] for r in rv1["glance"]["routes"]] == [[], ["X4"], ["X5"], []]
    assert [(p["code"], p["zone"]) for p in rv3["fix"]["circles"]][:3] == [
        ("X1", "correct"), ("X2", "correct"), ("X3", "rewrite")]  # fmt: skip
    text = json.dumps(s, ensure_ascii=False)
    assert wording.banned_words(text) == []


def test_codes_match_the_discrepancy_engine(reality: Reality) -> None:
    """G17: the snapshot's codes, titles, types, impact, hours and suggestions are the ones
    `GET /discrepancies` gives."""
    client = reality.engagement.client
    s = snapshot(client, reality.version_id)
    found = client.get(f"/api/versions/{reality.version_id}/discrepancies").json()["items"]
    engine = {i["code"]: (i["title"], i["types"], i["impact_class"], i["hours_per_month"],
                          i["verdict"]["suggested"], i["delta"]["label"])
              for i in found if i["code"] and i["status"] == "seen"}  # fmt: skip
    ours = {c["code"]: (c["title"], c["types"], c["impact_class"], c["hours"]["value"],
                        c["verdict"]["suggested"], c["delta"]["text"])
            for c in s["codes"]}  # fmt: skip
    assert set(ours) == set(engine)
    for code, (title, types, impact, hours, suggested, _) in ours.items():
        assert (title, types, impact, hours, suggested) == engine[code][:5]


def test_a_draft_snapshot_is_kept_and_follows_erics_decisions(reality: Reality) -> None:
    client = reality.engagement.client
    first = client.get(f"/api/versions/{reality.version_id}/reality").content
    again = client.get(f"/api/versions/{reality.version_id}/reality").content
    assert first == again  # byte-identical while the inputs are unchanged
    kept = stored(client, reality.version_id)
    assert kept is not None and not kept.frozen
    x2 = next(c for c in json.loads(first)["codes"] if c["code"] == "X2")
    body = {"verdict": "codify", "note": "The report reaches us in time."}
    assert client.put(f"/api/discrepancy-items/{x2['item_id']}/verdict", json=body).is_success
    after = snapshot(client, reality.version_id)
    y2 = next(c for c in after["codes"] if c["code"] == "X2")
    assert (y2["verdict"]["shown"], y2["verdict"]["status"]) == ("codify", "confirmed")
    assert next(p["zone"] for p in after["views"]["rv3"]["fix"]["circles"]
                if p["code"] == "X2") == "codify"  # fmt: skip
    assert after["inputs_hash"] != json.loads(first)["inputs_hash"]


def test_publishing_freezes_the_snapshot(reality: Reality) -> None:
    client = reality.engagement.client
    switch(client, True)
    publish(client, reality.version_id)
    frozen = stored(client, reality.version_id)
    assert frozen is not None and frozen.frozen
    s = snapshot(client, reality.version_id)
    assert s["frozen"] and not s["draft"]
    assert s["data_label"].startswith("Version v1.0, validated by ")
    assert s["views"]["rv1"]["headline"].startswith("Only 70% of cases follow the manual.")
    # A later decision changes nothing on the published version's snapshot.
    x1 = next(c for c in s["codes"] if c["code"] == "X1")
    body = {"verdict": "codify", "note": "Changed after publishing."}
    assert client.put(f"/api/discrepancy-items/{x1['item_id']}/verdict", json=body).is_success
    assert snapshot(client, reality.version_id) == s


def test_published_with_the_switch_off_freezes_on_first_request(reality: Reality) -> None:
    client = reality.engagement.client
    switch(client, False)
    publish(client, reality.version_id)
    assert stored(client, reality.version_id) is None  # nothing worked out at publishing
    s = snapshot(client, reality.version_id)
    assert s["frozen"] and s["data_label"].startswith("Version v1.0")
    kept = stored(client, reality.version_id)
    assert kept is not None and kept.frozen


def test_an_unknown_version(reality: Reality) -> None:
    response = reality.engagement.client.get("/api/versions/nope/reality")
    assert (response.status_code, response.json()["error"]["message"]) == (
        404, "That version doesn't exist.")  # fmt: skip


def test_leadership_reads_the_snapshot(reality: Reality) -> None:
    """RQ9 across screens: Leadership's shared figures are the frozen snapshot's tiles, the same
    IDs, values and texts; with the switch off there are none."""
    client = reality.engagement.client
    switch(client, True)
    publish(client, reality.version_id)
    s = snapshot(client, reality.version_id)
    view = client.get(f"/api/versions/{reality.version_id}/leadership").json()
    assert view["reality"] == {"data_label": s["data_label"], "tiles": s["tiles"]}
    switch(client, False)
    view = client.get(f"/api/versions/{reality.version_id}/leadership").json()
    assert view["reality"] is None


def _normalised(data: Any) -> Any:
    """Run-to-run values made fixed: hashes, timestamps and publication dates."""
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if k == "inputs_hash":
                out[k] = "0" * 64
            elif k in ("created_at", "stated_on") and isinstance(v, str) and v:
                out[k] = "2026-10-14T00:00:00+00:00" if k == "created_at" else "2026-10-14"
            else:
                out[k] = _normalised(v)
        return out
    if isinstance(data, list):
        return [_normalised(v) for v in data]
    if isinstance(data, str):
        return re.sub(r"\bon \d{4}-\d{2}-\d{2}\b", "on 2026-10-14", data)
    return data


def test_the_frontend_reality_sample_matches_the_backend(reality: Reality) -> None:
    """frontend/tests/fixtures/reality.json: the A.12 snapshot, intent statements and a verdict
    as the backend sends them, and Leadership's Reality figures once published, for the
    frontend's field-by-field type check. Rewritten with PMS_UPDATE_GOLDEN=1."""
    from tests.golden.test_golden_baselines import FRONTEND_FIXTURES, matches_baseline

    client = reality.engagement.client
    eid, vid = reality.engagement.eid, reality.version_id
    snap = snapshot(client, vid)
    x7 = next(c for c in snap["codes"] if c["code"] == "X7")
    verdict = client.put(f"/api/discrepancy-items/{x7['item_id']}/verdict",
                         json={"verdict": "codify", "note": "Keeps the slot."}).json()  # fmt: skip
    decided = snapshot(client, vid)
    switch(client, True)
    publish(client, vid)
    bundle = {
        "snapshot": snap,
        "decided": decided,
        "intent": client.get(f"/api/engagements/{eid}/intent").json(),
        "verdict": verdict,
        "leadership_reality": client.get(f"/api/versions/{vid}/leadership").json()["reality"],
    }
    matches_baseline("reality.json", _normalised(bundle), FRONTEND_FIXTURES)
