"""G11 (PRD §6.2 item 4, §3.18; P13d): the Reality snapshot of fixture A.12 published with the
Reality views on (intent evaluations, discrepancies with their codes, deltas, impact classes and
verdicts, the seven view models with their geometry and copy) and the Reality pack in both
layouts. Claude is mocked; the version is published at a fixed time by "Owner".

Candidate stage (2026-10-16): G11 becomes a byte-for-byte baseline only once Eric has approved
the candidate. Until then this test proves the output is stable (no clock, no record ID left in
it) and writes the candidate with PMS_GOLDEN_CANDIDATES=<folder> (docs/review/ for Eric). On
approval, the approved `G11_reality.json` and two `G11_reality_pack_*.html` files are copied into
this folder, and from then on they are compared (and updated with PMS_UPDATE_GOLDEN=1) like G1-G10.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from app.actions import publish as publish_action
from tests.golden.test_golden_baselines import (
    FONT_DATA,
    HERE,
    PUBLISHED_AT,
    UUID,
    matches_baseline,
    matches_text_baseline,
    stable_ids,
    write_candidate,
)
from tests.unit.test_discrepancies_a12 import Reality
from tests.unit.test_discrepancies_a12 import reality as reality  # the shared fixture
from tests.unit.test_intent_api import engagement as engagement  # the shared fixture
from tests.unit.test_reality_api import publish, snapshot, switch

ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+00:00|Z)?")
NAMES = ("G11_reality.json", "G11_reality_pack_a3.html", "G11_reality_pack_slide.html")


def _ids(text: str) -> str:
    tokens: dict[str, str] = {}
    return UUID.sub(lambda m: tokens.setdefault(m.group(0), f"id-{len(tokens) + 1}"), text)


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
    stable = {**snap, "inputs_hash": "<inputs hash>"}
    if all((HERE / name).exists() for name in NAMES):  # approved: byte for byte, as G1-G10
        matches_baseline(NAMES[0], stable)
        matches_text_baseline(NAMES[1], packs["a3"])
        matches_text_baseline(NAMES[2], packs["slide"])
        return
    write_candidate(NAMES[0], json.dumps(stable_ids(stable), indent=2, ensure_ascii=False) + "\n")
    for name, layout in zip(NAMES[1:], ("a3", "slide"), strict=True):
        rendered = FONT_DATA.sub(
            lambda m: f"data:font/woff2;base64,<{len(m.group(1))} characters>", _ids(packs[layout])
        )
        write_candidate(name, rendered)
