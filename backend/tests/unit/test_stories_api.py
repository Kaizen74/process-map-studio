"""The stories of a map (API_CONTRACT.md → GET /versions/{vid}/stories; P9u, criterion 59):
every story the interviews told, kept when told once, with the steps it is about; names
hidden. Claude mocked."""

from __future__ import annotations

from tests.unit.test_review_actions import Drafted, drafted

__all__ = ["drafted"]


def test_the_sample_story_with_its_steps(drafted: Drafted) -> None:
    found = drafted.client.get(f"/api/versions/{drafted.version_id}/stories")
    assert found.status_code == 200
    [story] = found.json()
    assert (story["label"], story["fragment_type"], story["single_account"], story["steps"]) == (
        "Had to re-trim three flights in one night", "went_badly", True,
        ["Draft load plan", "Deviation in limits?"],
    )  # fmt: skip
    assert story["anchor"] == "24:10" and story["source_id"]
    # The same story the panel shows on each of its steps (one builder for both).
    element = next(e for e in drafted.client.get(
        f"/api/versions/{drafted.version_id}/graph").json()["elements"]
        if e["label"] == "Draft load plan")  # fmt: skip
    card = drafted.client.get(f"/api/elements/{element['id']}").json()["stories"][0]
    assert {k: v for k, v in story.items() if k != "steps"} == card


def test_names_stay_hidden_and_errors(drafted: Drafted) -> None:
    body = drafted.client.get(f"/api/versions/{drafted.version_id}/stories").text
    terms = drafted.client.get(f"/api/engagements/{drafted.engagement_id}/redaction-terms").json()
    assert terms and not any(t["term"] in body for t in terms)
    assert drafted.client.get("/api/versions/nope/stories").status_code == 404
