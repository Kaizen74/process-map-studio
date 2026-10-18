"""G11 (PRD §6.2 item 4, §3.18; P13d): the Reality snapshot of fixture A.12 published with the
Reality views on (intent evaluations, discrepancies with their codes, deltas, impact classes and
verdicts, the seven view models with their geometry and copy) and the Reality pack in both
layouts. Claude is mocked; the version is published at a fixed time by "Owner".

Times that change on every run are fixed and record IDs numbered in order of first appearance, as
for G1-G10; the snapshot's `inputs_hash` (a hash over record IDs) is masked. Eric approved the
candidate on 2026-10-18 (DECISIONS 61). To accept a legitimate change: PMS_UPDATE_GOLDEN=1,
review the diff, log it in DECISIONS.md; to show Eric first: PMS_GOLDEN_CANDIDATES=<folder>.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from app.actions import publish as publish_action
from tests.golden.test_golden_baselines import (
    PUBLISHED_AT,
    matches_baseline,
    matches_text_baseline,
)
from tests.unit.test_discrepancies_a12 import Reality
from tests.unit.test_discrepancies_a12 import reality as reality  # the shared fixture
from tests.unit.test_intent_api import engagement as engagement  # the shared fixture
from tests.unit.test_reality_api import publish, snapshot, switch

ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+00:00|Z)?")


def test_g11_reality_snapshot_and_pack_of_fixture_a12(
    reality: Reality, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(publish_action, "now", lambda: PUBLISHED_AT)
    client, vid = reality.engagement.client, reality.version_id
    assert client.put("/api/settings/profile", json={"owner_name": "Owner"}).is_success
    switch(client, True)
    publish(client, vid)
    snap: dict[str, Any] = snapshot(client, vid)
    packs = {}
    for layout in ("a3", "slide"):
        response = client.get(f"/api/versions/{vid}/reality/export", params={"layout": layout})
        assert response.status_code == 200, response.text
        packs[layout] = response.text
    # Stable: no clock time but the fixed publication, the same answer when asked again.
    stamps = {m.group(0) for m in ISO.finditer(json.dumps(snap) + "".join(packs.values()))}
    assert stamps <= {PUBLISHED_AT}, stamps
    assert snapshot(client, vid) == snap
    for layout, html in packs.items():
        again = client.get(f"/api/versions/{vid}/reality/export", params={"layout": layout}).text
        assert again == html
    # The inputs hash covers record IDs, which change on every run.
    matches_baseline("G11_reality.json", {**snap, "inputs_hash": "<inputs hash>"})
    matches_text_baseline("G11_reality_pack_a3.html", packs["a3"])
    matches_text_baseline("G11_reality_pack_slide.html", packs["slide"])
