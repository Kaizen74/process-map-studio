"""The alignment matrix endpoint (API_CONTRACT.md → Views; PRD §5.4 Matrix) on the illustrative
Appendix A draft, Claude mocked: every step once, agreeing with its source state; rejected steps
left out; 404 for an unknown version. The full payload is the G4 golden baseline."""

from __future__ import annotations

from typing import Any

from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]

CELLS = {"supports", "contradicts", "silent", "not_applicable"}


def matrix(d: Drafted) -> list[dict[str, Any]]:
    response = d.client.get(f"/api/versions/{d.version_id}/alignment-matrix")
    assert response.status_code == 200, response.text
    return list(response.json())


def test_one_row_per_step_agreeing_with_its_source_state(drafted: Drafted) -> None:
    rows = matrix(drafted)
    graph = drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()
    steps = [e for e in graph["elements"] if e["kind"] in {"activity", "decision", "approval"}]
    assert [r["element_id"] for r in rows] == [e["id"] for e in steps]
    by_id = {e["id"]: e for e in steps}
    for row in rows:
        assert {row[c] for c in ("sop", "interview", "jd", "artefact")} <= CELLS
        element = by_id[row["element_id"]]
        assert (row["state"], row["divergence_types"]) == (
            element["source_state"],
            element["divergence_types"],
        )
        # The cells tell the same story as the state (PRD §3.7): classify, never reconcile.
        if row["state"] == "corroborated":
            assert (row["sop"], row["interview"]) == ("supports", "supports")
        if row["state"] == "practiced_only":
            assert row["interview"] == "supports" and row["sop"] in {"silent", "not_applicable"}
        if row["state"] == "documented_only":
            assert row["sop"] == "supports" and row["interview"] == "silent"
        if row["state"] == "contested":
            assert "contradicts" in {row["sop"], row["interview"]}
    # The sample has no executed artefacts: that column doesn't apply.
    assert {r["artefact"] for r in rows} == {"not_applicable"}


def test_rejected_steps_leave_the_matrix(drafted: Drafted) -> None:
    drafted.act("Resolve or offload", "reject")
    assert "Resolve or offload" not in {r["label"] for r in matrix(drafted)}
    drafted.act("Resolve or offload", "restore")
    assert "Resolve or offload" in {r["label"] for r in matrix(drafted)}


def test_names_are_hidden_and_unknown_versions_are_404(drafted: Drafted) -> None:
    assert "Priya" not in str(matrix(drafted))
    missing = drafted.client.get("/api/versions/nope/alignment-matrix")
    assert missing.status_code == 404
    assert missing.json()["error"]["message"] == "That version doesn't exist."
