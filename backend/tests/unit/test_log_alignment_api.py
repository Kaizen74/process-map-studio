"""Alignment of log activities to map steps (API_CONTRACT.md; PRD §3.13.4; criterion 86; R5a):
fixture A.11 imported into the drafted Appendix A sample, Claude mocked."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.actions import log_alignment as actions
from app.config import AppConfig
from app.db import session_scope
from app.domain.result import Ok, Result
from app.main import create_app
from app.pipeline import sr_align
from app.repositories import audit
from app.services.log_alignment import Suggestion
from tests import fixture_engagement
from tests.unit.test_review_actions import Drafted, drafted
from tests.uploads import wait_for_jobs

__all__ = ["drafted"]

SYSTEM = Path(__file__).resolve().parents[1] / "fixtures" / "system"
CODES: dict[str, str] = json.loads((SYSTEM / "role_map.json").read_text("utf-8"))
EXPECTED = {
    "Plan created": "Draft load plan",
    "Special load checked": "Special loads OK?",
    "Loading report received": "Load and return LIR",
    "Weight deviation checked": "Deviation in limits?",
    "Load sheet issued": "Issue load sheet",
    "Plan revised": "Draft load plan",
}
UNRECORDED = ["Approve load plan", "Resolve or offload", "Busy wave?", "Read report at aircraft",
              "Approve deviation"]  # fmt: skip


def import_log(client: TestClient, engagement_id: str) -> str:
    """Fixture A.11 uploaded, mapped and imported into the engagement: the log ID."""
    log = client.post(
        f"/api/engagements/{engagement_id}/event-logs",
        files={"file": ("dcs_log.csv", (SYSTEM / "dcs_log.csv").read_bytes(), "text/csv")},
        data={"name": "DCS extract", "system": "DCS"},
    ).json()
    roles = {
        r["name"]: r["id"] for r in client.get(f"/api/engagements/{engagement_id}/roles").json()
    }
    client.put(f"/api/event-logs/{log['id']}/column-map", json={"columns": log["column_map"]})
    client.put(f"/api/event-logs/{log['id']}/role-map",
               json={"roles": {code: roles[role] for code, role in CODES.items()}})  # fmt: skip
    approval = {"approved_by_role": "Head of operations", "confirm_approval": True}
    started = client.post(f"/api/event-logs/{log['id']}/import", json=approval)
    assert started.status_code == 202, started.text
    wait_for_jobs(client)
    return str(log["id"])


@pytest.fixture()
def aligned(drafted: Drafted) -> tuple[Drafted, str]:
    return drafted, import_log(drafted.client, drafted.engagement_id)


def table(d: Drafted, lid: str) -> dict[str, Any]:
    response = d.client.get(f"/api/event-logs/{lid}/alignment")
    assert response.status_code == 200, response.text
    return dict(response.json())


def put(d: Drafted, lid: str, *rows: dict[str, Any]) -> Any:
    return d.client.put(f"/api/event-logs/{lid}/alignment", json={"rows": list(rows)})


def _error(response: Any) -> tuple[int, str, str]:
    error = response.json()["error"]
    return response.status_code, error["code"], error["message"]


def test_the_app_proposes_what_appendix_a11_expects_and_applies_nothing(
    aligned: tuple[Drafted, str],
) -> None:
    d, lid = aligned
    body = table(d, lid)
    assert body["version_id"] == d.version_id
    rows = body["rows"]
    activity_rows = {r["activity"]: r for r in rows if r["activity"]}
    assert {a: r["element_label"] for a, r in activity_rows.items() if r["element_id"]} == EXPECTED
    assert all(r["element_id"] == d.ids[r["element_label"]] for r in rows if r["element_id"])
    hidden = activity_rows["Manual weight override"]
    assert (hidden["status"], hidden["element_id"], hidden["reason"]) == (
        "hidden_work", None, actions.NO_MATCH,
    )  # fmt: skip
    assert [r["element_label"] for r in rows if not r["activity"]] == UNRECORDED
    assert all(r["status"] == "no_system_record" for r in rows if not r["activity"])
    assert all(not r["confirmed"] and r["proposed_by"] == "app" for r in rows)
    big = sorted(a for a in EXPECTED if a != "Plan revised")  # 200 events each, then by name
    assert [r["activity"] for r in rows if r["activity"]] == [*big, "Plan revised",
                                                              "Manual weight override"]  # fmt: skip
    assert activity_rows["Plan revised"]["events"] == 40
    assert activity_rows["Loading report received"]["reason"] == (
        "Same words: loading. Same role: Ramp."
    )
    assert body["summary"] == {"activities": 7, "matched": 6, "hidden_work": 1,
                               "no_system_record": 5, "waiting": 12}  # fmt: skip
    assert not any(code in json.dumps(body) for code in CODES)


def test_eric_confirms_and_the_decisions_are_audited(aligned: tuple[Drafted, str]) -> None:
    d, lid = aligned
    rows = [
        {"activity": a, "element_id": d.ids[s], "status": "confirmed"} for a, s in EXPECTED.items()
    ]
    rows.append({"activity": "Manual weight override", "element_id": None, "status": "hidden_work"})
    rows += [{"activity": "", "element_id": d.ids[s], "status": "no_system_record"}
             for s in UNRECORDED]  # fmt: skip
    response = put(d, lid, *rows)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["waiting"] == 0
    assert all(r["confirmed"] and r["proposed_by"] == "eric" for r in body["rows"])
    confirmed = {r["activity"]: r for r in body["rows"] if r["activity"]}
    assert confirmed["Plan created"]["status"] == "confirmed"
    assert confirmed["Plan created"]["reason"] == "Same words: plan. Same role: Load controller."
    assert confirmed["Manual weight override"]["status"] == "hidden_work"
    with session_scope(d.client.app.state.sessions) as session:  # type: ignore[attr-defined]
        trail = audit.list_recent(session, engagement_id=d.engagement_id)
    [row] = [r for r in trail if r["action"] == "Confirmed system alignment"]
    assert "Plan revised → Draft load plan" in row["after"]["rows"]
    assert "Manual weight override → hidden work" in row["after"]["rows"]
    assert "Approve load plan → no system record" in row["after"]["rows"]
    # Read back unchanged; nothing else waits.
    assert table(d, lid)["rows"] == body["rows"]


def test_a_new_decision_replaces_the_earlier_one(aligned: tuple[Drafted, str]) -> None:
    d, lid = aligned
    step = d.ids["Read report at aircraft"]
    assert (
        put(d, lid, {"activity": "", "element_id": step, "status": "no_system_record"}).status_code
        == 200
    )
    # Matching an activity to that step removes its "no system record" decision.
    moved = put(d, lid, {"activity": "Manual weight override", "element_id": step,
                         "status": "confirmed"})  # fmt: skip
    assert moved.status_code == 200, moved.text
    rows = moved.json()["rows"]
    assert "Read report at aircraft" not in [r["element_label"] for r in rows if not r["activity"]]
    [override] = [r for r in rows if r["activity"] == "Manual weight override"]
    assert (override["element_label"], override["confirmed"], override["reason"]) == (
        "Read report at aircraft", True, "",
    )  # fmt: skip
    # A step with a confirmed match can't be marked as having no system record.
    refused = put(d, lid, {"activity": "", "element_id": step, "status": "no_system_record"})
    assert _error(refused) == (422, "VALIDATION", actions.HAS_RECORD.format(
        step="Read report at aircraft", activity="Manual weight override"))  # fmt: skip


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ({"activity": "Plan created", "element_id": None, "status": "proposed"},
         actions.BAD_STATUS),
        ({"activity": "Plan approved", "element_id": None, "status": "hidden_work"},
         actions.NOT_IN_LOG),
        ({"activity": "Plan created", "element_id": "nope", "status": "confirmed"},
         actions.NOT_A_STEP),
        ({"activity": "Plan created", "element_id": None, "status": "confirmed"},
         actions.SHAPE["confirmed"]),
        ({"activity": "", "element_id": None, "status": "no_system_record"},
         actions.SHAPE["no_system_record"]),
    ],
)  # fmt: skip
def test_a_decision_with_a_problem_is_refused(
    aligned: tuple[Drafted, str], row: dict[str, Any], message: str
) -> None:
    d, lid = aligned
    response = put(d, lid, row)
    assert _error(response) == (422, "VALIDATION", message)
    assert response.json()["error"]["details"]["field"] == "rows"
    assert table(d, lid)["summary"]["waiting"] == 12  # nothing was saved


def test_claudes_suggestions_naming_what_doesnt_exist_are_left_out(
    aligned: tuple[Drafted, str],
) -> None:
    d, lid = aligned
    started = d.client.post(f"/api/event-logs/{lid}/alignment/suggest")
    assert started.status_code == 202, started.text
    wait_for_jobs(d.client)
    job = d.client.get(f"/api/jobs/{started.json()['job_id']}").json()
    assert job["status"] == "done", job
    assert job["message"] == (
        "Claude suggested 0 matches. 2 suggestions were left out: they named an activity or step "
        "that isn't in the log or on the map."
    )
    assert job["usage"]["calls"] == 1
    [row] = [r for r in table(d, lid)["rows"] if r["activity"] == "Manual weight override"]
    assert (row["status"], row["proposed_by"]) == ("hidden_work", "app")


def test_a_kept_suggestion_is_a_proposal_until_eric_decides(
    aligned: tuple[Drafted, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    d, lid = aligned
    seen: list[sr_align.AlignInput] = []

    def answer(_s: Any, _c: Any, data: sr_align.AlignInput, _j: str) -> Result[list[Suggestion]]:
        seen.append(data)
        return Ok([Suggestion("Manual weight override", "deviation-in-limits",
                              "The override handles a weight outside the limits.")])  # fmt: skip

    monkeypatch.setattr(sr_align, "suggest", answer)
    d.client.post(f"/api/event-logs/{lid}/alignment/suggest")
    wait_for_jobs(d.client)
    [sent] = seen
    assert [a.name for a in sent.activities] == ["Manual weight override"]  # only the unmatched
    assert {s.key for s in sent.steps} >= {"draft-load-plan", "issue-load-sheet"}
    assert sent.activities[0].role == "Load controller"
    [row] = [r for r in table(d, lid)["rows"] if r["activity"] == "Manual weight override"]
    assert (row["status"], row["proposed_by"], row["element_label"], row["confirmed"]) == (
        "proposed", "claude", "Deviation in limits?", False,
    )  # fmt: skip
    # Claude may be asked again while its suggestion waits; once Eric decides, there is nothing.
    assert d.client.post(f"/api/event-logs/{lid}/alignment/suggest").status_code == 202
    wait_for_jobs(d.client)
    put(d, lid, {"activity": "Manual weight override", "element_id": None, "status": "hidden_work"})
    again = d.client.post(f"/api/event-logs/{lid}/alignment/suggest")
    assert _error(again) == (409, "NOTHING_TO_SUGGEST", actions.NOTHING_TO_SUGGEST)


def test_a_decision_whose_step_has_gone_drops_back_to_a_proposal(
    aligned: tuple[Drafted, str],
) -> None:
    d, lid = aligned
    put(d, lid, {"activity": "Plan created", "element_id": d.ids["Draft load plan"],
                 "status": "confirmed"})  # fmt: skip
    m = actions._load(d.client.app.state.sessions, lid)  # type: ignore[attr-defined]
    assert isinstance(m, Ok)
    gone = m.value
    gone.ids = {k: v for k, v in gone.ids.items() if k != "draft-load-plan"}
    gone.steps = [s for s in gone.steps if s.key != "draft-load-plan"]
    [row] = [r for r in actions._table(gone).rows if r.activity == "Plan created"]
    assert (row.confirmed, row.proposed_by) == (False, "app")


def test_alignment_needs_an_imported_log_and_a_map(settings_config: AppConfig) -> None:
    with TestClient(create_app(settings_config)) as client:
        built = fixture_engagement.build(client, sources=[])
        lid = import_log(client, built.engagement_id)
        url = f"/api/event-logs/{lid}/alignment"
        for call in (client.get(url), client.post(f"{url}/suggest"),
                     client.put(url, json={"rows": []})):  # fmt: skip
            assert _error(call) == (409, "NO_MAP", actions.NO_MAP)
        log = client.post(
            f"/api/engagements/{built.engagement_id}/event-logs",
            files={"file": ("x.csv", b"case_id,activity,timestamp\nC1,Open,2026-03-02 09:00\n",
                            "text/csv")},
            data={"name": "Second"},
        ).json()  # fmt: skip
        assert _error(client.get(f"/api/event-logs/{log['id']}/alignment"))[:2] == (
            409, "NOT_IMPORTED",
        )  # fmt: skip
        assert client.get("/api/event-logs/nope/alignment").status_code == 404


def test_erics_decisions_survive_a_refresh(aligned: tuple[Drafted, str]) -> None:
    """A refresh gives the steps Eric hasn't reviewed fresh IDs; his confirmed alignment follows
    each step to its fresh successor with the same key (constraint 8: his decisions are never
    lost to a re-run)."""
    d, lid = aligned
    rows = [{"activity": a, "element_id": d.ids[s], "status": "confirmed"}
            for a, s in EXPECTED.items()]  # fmt: skip
    rows.append({"activity": "Manual weight override", "element_id": None, "status": "hidden_work"})
    rows += [{"activity": "", "element_id": d.ids[s], "status": "no_system_record"}
             for s in UNRECORDED]  # fmt: skip
    assert put(d, lid, *rows).status_code == 200

    def decisions() -> list[tuple[str, str | None, str, bool]]:
        return sorted((r["activity"], r["element_label"], r["status"], r["confirmed"])
                      for r in table(d, lid)["rows"])  # fmt: skip

    before = decisions()
    assert d.client.post(f"/api/versions/{d.version_id}/refresh").status_code == 202
    wait_for_jobs(d.client)
    after = decisions()
    assert after == before
    assert table(d, lid)["summary"]["waiting"] == 0
