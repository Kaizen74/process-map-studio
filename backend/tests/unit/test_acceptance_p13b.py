"""P13b regression on fixture A.12 (Eric's request 2026-10-14: no regression or unintended effect
on the other features): switching the Reality views on changes no other screen's answer and no
export, Leadership gains only its `reality` part, and the whole chain holds from intent to a
reopened draft (snapshot, verdict, publish, freeze, codes kept). Claude mocked throughout."""

from __future__ import annotations

import re
from typing import Any

from fastapi.testclient import TestClient

from tests.unit.test_discrepancies_a12 import Reality
from tests.unit.test_discrepancies_a12 import reality as reality  # the shared fixture
from tests.unit.test_incomplete_data import SKIP, VARIANTS, _get_routes
from tests.unit.test_intent_api import engagement as engagement  # the shared fixture
from tests.unit.test_reality_api import publish, snapshot, switch
from tests.uploads import wait_for_jobs

REALITY_ROUTES = ("/reality", "/discrepancies")  # their own answers (P13a, P13b)
EXPORTS = ("md", "json", "csv", "html")


def _ids(r: Reality) -> dict[str, str]:
    client, eid, vid = r.engagement.client, r.engagement.eid, r.version_id
    graph = client.get(f"/api/versions/{vid}/graph").json()
    step = next(e["id"] for e in graph["elements"] if e["kind"] == "activity")
    logs = client.get(f"/api/engagements/{eid}/event-logs").json()
    intent = client.get(f"/api/engagements/{eid}/intent").json()
    return {"engagement_id": eid, "version_id": vid, "element_id": step,
            "source_id": r.engagement.charter_id, "log_id": logs[0]["id"],
            "intent_id": intent[0]["id"], "fmt": "md"}  # fmt: skip


def _answers(client: TestClient, ids: dict[str, str]) -> dict[str, tuple[int, Any]]:
    """Every documented GET address the ids reach, with its status and body."""
    out: dict[str, tuple[int, Any]] = {}
    for path in [*_get_routes(client), *VARIANTS]:
        names = re.findall(r"{(\w+)}", path.split("?")[0])
        if path in SKIP or any(n not in ids for n in names) or path.endswith(REALITY_ROUTES):
            continue
        response = client.get(path.format(**{n: ids[n] for n in names}))
        json = "json" in response.headers.get("content-type", "")
        out[path] = (response.status_code, response.json() if json else response.content)
    return out


def test_switching_reality_on_changes_no_other_answer(reality: Reality) -> None:
    client = reality.engagement.client
    ids = _ids(reality)
    switch(client, False)
    before = _answers(client, ids)
    again = _answers(client, ids)
    steady = {p for p in before if before[p] == again[p]}  # leave out answers that move anyway
    assert len(steady) >= 40, sorted(set(before) - steady)
    switch(client, True)
    snapshot(client, reality.version_id)  # the snapshot is worked out (and codes given)
    after = _answers(client, ids)
    changed = sorted(p for p in steady if after.get(p) != before[p])
    assert changed in ([], ["/api/settings"]), changed  # only the switch itself
    assert after["/api/settings"][1]["reality_views_enabled"] is True


def test_exports_and_leadership_with_the_switch_on_and_off(reality: Reality) -> None:
    """A published version's exports are the same with Reality on or off (the Reality pack is
    separate, P13d); Leadership gains only `reality`, equal to the frozen snapshot's tiles."""
    client, vid = reality.engagement.client, reality.version_id
    switch(client, True)
    publish(client, vid)
    on = {f: client.get(f"/api/versions/{vid}/export/{f}").content for f in EXPORTS}
    leadership_on = client.get(f"/api/versions/{vid}/leadership").json()
    switch(client, False)
    off = {f: client.get(f"/api/versions/{vid}/export/{f}").content for f in EXPORTS}
    leadership_off = client.get(f"/api/versions/{vid}/leadership").json()
    assert on == off
    assert {k: v for k, v in leadership_on.items() if k != "reality"} == {
        k: v for k, v in leadership_off.items() if k != "reality"}  # fmt: skip
    assert leadership_off["reality"] is None
    assert leadership_on["reality"]["tiles"] == snapshot(client, vid)["tiles"]
    for fmt in ("md", "json", "csv"):  # (the HTML file embeds fonts, so it is compared above)
        text = on[fmt].decode("utf-8")
        assert not re.search(r"\bX\d+\b|control exposure|Fix or keep", text, re.I), fmt


def test_the_chain_from_intent_to_a_reopened_draft(reality: Reality) -> None:
    client, eid, vid = reality.engagement.client, reality.engagement.eid, reality.version_id
    switch(client, True)
    first = snapshot(client, vid)
    codes = {c["code"]: c["title"] for c in first["codes"]}
    assert first["draft"] and codes
    # A new owner-stated target changes the draft's snapshot (and nothing frozen yet).
    roles = reality.engagement.roles
    target = {"scope": "process", "kind": "target", "text": "A flight is closed out in 60 minutes.",
              "metric": "cycle_time_min", "comparator": "at_most", "target_value": 60,
              "unit": "min", "owner_role_id": roles["Load control lead"],
              "stated_on": "2026-10-01"}  # fmt: skip
    assert client.post(f"/api/engagements/{eid}/intent", json=target).status_code == 201
    second = snapshot(client, vid)
    assert second["inputs_hash"] != first["inputs_hash"]
    assert any(i["text"] == target["text"] for i in second["intents"])
    # Eric's verdict, then publishing freezes the lot.
    x2 = next(c for c in second["codes"] if c["code"] == "X2")
    body = {"verdict": "codify", "note": "Ramp texts the figures."}
    assert client.put(f"/api/discrepancy-items/{x2['item_id']}/verdict", json=body).is_success
    publish(client, vid)
    frozen = snapshot(client, vid)
    assert frozen["frozen"] and not frozen["draft"]
    assert next(c for c in frozen["codes"] if c["code"] == "X2")["verdict"]["status"] == "confirmed"
    # Reopen: a new draft with its own snapshot; known locations keep their codes and Eric's
    # verdict travels with the code (codes belong to the engagement).
    reopened = client.post(f"/api/versions/{vid}/reopen")
    assert reopened.status_code == 201, reopened.text
    draft_id = reopened.json()["id"]
    wait_for_jobs(client)
    draft = snapshot(client, draft_id)
    assert draft["draft"] and not draft["frozen"]
    titles = {c["code"]: c["title"] for c in draft["codes"]}
    assert {c: t for c, t in titles.items() if c in codes} == codes
    # The process-wide cycle-time target found one more gap: named in words, never by its key.
    assert {t for c, t in titles.items() if c not in codes} == {"The whole process"}
    assert next(c for c in draft["codes"] if c["code"] == "X2")["verdict"]["shown"] == "codify"
    assert snapshot(client, vid) == frozen  # the published one never moves
