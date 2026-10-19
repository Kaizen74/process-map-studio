"""How much of Claude's draft Eric kept (deep review item 4, 2026-10-19; API_CONTRACT.md →
Versions, `acceptance`): counted from each step's review status, with Eric's own steps told
apart even when he later rejects one. Illustrative Appendix A engagement, Claude mocked."""

from __future__ import annotations

from typing import Any

from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_review_add import add, passage
from tests.unit.test_review_edit import patch

__all__ = ["drafted"]


def acceptance(d: Drafted) -> dict[str, Any]:
    response = d.client.get(f"/api/versions/{d.version_id}")
    assert response.status_code == 200, response.text
    return dict(response.json()["acceptance"])


def test_a_fresh_draft_is_all_claude_s_and_unreviewed(drafted: Drafted) -> None:
    assert acceptance(drafted) == {"drafted": 10, "confirmed": 0, "edited": 0, "rejected": 0,
                                   "unreviewed": 10, "added": 0}  # fmt: skip


def test_each_decision_is_counted_once_and_eric_s_steps_stay_his(drafted: Drafted) -> None:
    d = drafted
    assert d.act("Draft load plan", "confirm").status_code == 200
    assert d.act("Approve load plan", "confirm").status_code == 200
    assert patch(d, "Special loads OK?", {"label": "Special loads acceptable?"}).status_code == 200
    assert d.act("Resolve or offload", "reject").status_code == 200
    mine = add(d, segment_ids=[passage(d)])
    assert mine.status_code == 201, mine.text
    second = add(d, label="Recheck fuel", segment_ids=[passage(d)],
                 after_element_id=mine.json()["id"])  # fmt: skip
    assert second.status_code == 201, second.text
    assert d.client.post(f"/api/elements/{second.json()['id']}/reject").status_code == 200
    assert acceptance(d) == {"drafted": 10, "confirmed": 2, "edited": 1, "rejected": 1,
                             "unreviewed": 6, "added": 2}  # fmt: skip
    # Changing his mind is counted as his last decision only.
    assert d.act("Resolve or offload", "restore").status_code == 200
    assert acceptance(d)["rejected"] == 0 and acceptance(d)["unreviewed"] == 7
