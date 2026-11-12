"""Shared language with the other apps (2026-11-12, Eric's brief; DECISIONS 96): a step is shown as
S-01 and an intent statement as I1, the same in every version and never reused; a map made from a
hand-off shows its key and pilot; every discrepancy and gap finding carries the shared grade
(Confirmed, Indicated, Hypothesis), suggested by rule and Eric's to change. O / I / R, the
grounding checks and the map itself are untouched. Mocked: no key, no network."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.actions.quality import render_exports
from app.actions.versions import build_graph
from app.db import session_scope
from app.domain.exports import ExportInput
from app.repositories import codes, read_memo, versions
from app.repositories import engagements as engagements_repo
from app.services import grade
from tests.unit.test_compass_handoff import client as client  # the shared fixture
from tests.unit.test_compass_handoff import start
from tests.unit.test_discrepancies_a12 import Reality
from tests.unit.test_discrepancies_a12 import reality as reality  # the shared fixture
from tests.unit.test_discrepancies_api import items
from tests.unit.test_gap_decisions_api import decide_all_internal
from tests.unit.test_gap_system_findings_api import analyse
from tests.unit.test_intent_api import Engagement
from tests.unit.test_intent_api import engagement as engagement  # the shared fixture
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_roles_choose_remove import audit_actions
from tests.uploads import wait_for_jobs

__all__ = ["drafted"]


def step_codes(client: TestClient, version_id: str) -> dict[str, str | None]:
    graph = client.get(f"/api/versions/{version_id}/graph").json()
    return {e["stable_key"]: e["code"] for e in graph["elements"]}


# --- Step codes -----------------------------------------------------------------------------


def test_every_step_has_a_code_in_process_order_and_start_and_end_have_none(
    drafted: Drafted,
) -> None:
    graph = drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()
    steps = [e for e in graph["elements"] if e["kind"] not in ("start", "end")]
    assert [e["code"] for e in steps] == [f"S-{n:02d}" for n in range(1, len(steps) + 1)]
    assert {e["code"] for e in graph["elements"] if e["kind"] in ("start", "end")} == {None}
    # One view of the map shows the same codes as the whole map.
    done = drafted.client.get(f"/api/versions/{drafted.version_id}/graph?view=done").json()
    whole = {e["stable_key"]: e["code"] for e in graph["elements"]}
    assert all(whole[e["stable_key"]] == e["code"] for e in done["elements"])


def test_step_codes_survive_a_refresh_a_reopen_and_a_republish(drafted: Drafted) -> None:
    client = drafted.client
    first = step_codes(client, drafted.version_id)
    assert client.post(f"/api/versions/{drafted.version_id}/refresh").status_code == 202
    wait_for_jobs(client)
    refreshed = step_codes(client, drafted.version_id)
    assert {k: c for k, c in refreshed.items() if k in first} == {
        k: c for k, c in first.items() if k in refreshed
    }
    with session_scope(client.app.state.sessions) as session:  # type: ignore[attr-defined]
        fresh = versions.create(session, engagement_id=drafted.engagement_id, label="v2",
                                state="draft")  # fmt: skip
        versions.copy_content(session, drafted.version_id, fresh.id)
    assert step_codes(client, fresh.id) == refreshed


def test_a_code_is_never_reused_and_a_read_only_request_gives_none(sessions: Any) -> None:
    with session_scope(sessions) as s:
        eid = engagements_repo.create(s, {"name": "Load control"}).id
        assert codes.ensure(s, eid, codes.STEP, ["a", "b", "a"]) == {"a": "S-01", "b": "S-02"}
        # "a" has gone from the map; a new step takes the next number, never S-01.
        assert codes.ensure(s, eid, codes.STEP, ["b", "c"])["c"] == "S-03"
        assert codes.ensure(s, eid, codes.INTENT, ["x"]) == {"x": "I1"}  # its own numbering
        with read_memo.read_only(s):
            assert "d" not in codes.ensure(s, eid, codes.STEP, ["d"])
        assert codes.ensure(s, eid, codes.STEP, ["d"])["d"] == "S-04"


def test_the_quality_card_and_the_downloads_carry_the_codes(drafted: Drafted) -> None:
    client = drafted.client
    assert client.get(f"/api/versions/{drafted.version_id}/quality-card").status_code == 200
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    before = step_codes(client, drafted.version_id)

    def download(fmt: str) -> Any:
        response = client.get(f"/api/versions/{drafted.version_id}/export/{fmt}")
        assert response.status_code == 200, response.text
        return response

    elements = download("json").json()["elements"]
    assert {e["stable_key"]: e["code"] for e in elements} == before  # published: the same codes
    assert "| S-01 " in download("md").text
    assert download("csv").text.splitlines()[0].lstrip("\ufeff").startswith("Code,Step,Kind,")
    assert "] S-01 · " in download("html").text


# --- The hand-off's key and pilot -------------------------------------------------------------


def test_a_map_from_a_hand_off_shows_its_key_and_pilot_and_others_show_none(
    client: TestClient, drafted: Drafted
) -> None:
    made = start(client)
    assert made.status_code == 201, made.text
    sessions = client.app.state.sessions  # type: ignore[attr-defined]
    with session_scope(sessions) as session:
        version = versions.create(session, engagement_id=made.json()["id"], label="v1",
                                  state="draft")  # fmt: skip
    process = client.get(f"/api/versions/{version.id}/graph").json()["process"]
    compass = made.json()["compass"]
    assert (process["engagement_key"], process["pilot_ref"]) == (compass["key"], "VS-01")
    line = f"Engagement key {compass['key']} · pilot VS-01"
    with session_scope(sessions) as session:
        graph = build_graph(session, version.id)
        assert graph is not None
        data = ExportInput(graph=graph, sources=[], published_at="", validated_by="",
                           open_questions=[])  # fmt: skip
        files = render_exports(data)
    assert line in files["md"].splitlines()
    assert f'<p class="meta">{line}</p>' in files["html"]
    alone = drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()["process"]
    assert (alone["engagement_key"], alone["pilot_ref"]) == (None, None)
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    plain = drafted.client.get(f"/api/versions/{drafted.version_id}/export/md").text
    assert "Engagement key" not in plain


# --- Intent codes ---------------------------------------------------------------------------


def test_a_confirmed_intent_statement_gets_a_code_that_is_never_reused(
    engagement: Engagement,
) -> None:
    def listed() -> dict[str, str | None]:
        rows = engagement.client.get(f"/api/engagements/{engagement.eid}/intent").json()
        return {r["id"]: r["code"] for r in rows}

    one = engagement.add().json()
    two = engagement.add(text="Every deviation is logged the same day.").json()
    assert listed() == {one["id"]: "I1", two["id"]: "I2"}
    assert engagement.client.delete(f"/api/intent/{one['id']}").status_code == 204
    three = engagement.add(text="A second officer checks each release.").json()
    assert listed() == {two["id"]: "I2", three["id"]: "I3"}


# --- The shared grade -----------------------------------------------------------------------


def test_the_suggested_grade_follows_the_rule() -> None:
    d = grade.for_discrepancy
    assert d(documents=1, interviews=0, system_cases=12) == "confirmed"
    assert d(documents=0, interviews=2, system_cases=12) == "confirmed"
    assert d(documents=0, interviews=0, system_cases=12) == "indicated"  # one source
    assert d(documents=1, interviews=1, system_cases=None) == "indicated"  # no system record
    assert d(documents=0, interviews=0, system_cases=None) == "hypothesis"
    g = grade.for_gap_finding
    seen = {"provenance": "O", "verification_status": "verified", "needs_check": False}
    assert g(**seen, system=True, others=1) == "confirmed"  # type: ignore[arg-type]
    assert g(**seen, system=False, others=2) == "indicated"  # type: ignore[arg-type]
    assert g(**seen, system=True, others=0) == "indicated"  # type: ignore[arg-type]
    assert g(**seen, system=False, others=0) == "hypothesis"  # type: ignore[arg-type]
    for change in ({"provenance": "I"}, {"provenance": "R"}, {"needs_check": True},
                   {"verification_status": "rejected"}):  # fmt: skip
        assert g(**{**seen, **change}, system=True, others=3) == "hypothesis"  # type: ignore[arg-type]
    assert grade.GRADES == ("confirmed", "indicated", "hypothesis")


def test_every_discrepancy_carries_a_grade_and_erics_choice_wins(reality: Reality) -> None:
    client = reality.engagement.client
    seen = [i for i in items(reality) if i["status"] == "seen"]
    assert seen
    for i in seen:
        g, e = i["grade"], i["evidence"]
        counts = {k: e[k] for k in ("documents", "interviews", "system_cases")}
        assert g["suggested"] == grade.for_discrepancy(**counts)
        assert (g["grade"], g["chosen_by_owner"]) == (g["suggested"], False)
        assert g["rules_version"] == grade.GRADE_RULES_VERSION
    coded = next(i for i in seen if i["item_id"])
    other = next(g for g in grade.GRADES if g != coded["grade"]["suggested"])
    url = f"/api/discrepancy-items/{coded['item_id']}/grade"
    chosen = client.put(url, json={"grade": other})
    assert chosen.status_code == 200, chosen.text
    assert chosen.json() == {"item_id": coded["item_id"], "code": coded["code"],
                             "grade_chosen": other}  # fmt: skip
    after = next(i for i in items(reality) if i["item_id"] == coded["item_id"])
    assert after["grade"] == {**coded["grade"], "grade": other, "chosen_by_owner": True}
    # Nothing else about the discrepancy moved.
    assert {k: v for k, v in after.items() if k != "grade"} == {
        k: v for k, v in coded.items() if k != "grade"
    }
    assert "Set discrepancy grade" in [r["action"] for r in
                                       audit_actions(client, reality.engagement.eid)]  # fmt: skip
    assert client.put(url, json={"grade": None}).json()["grade_chosen"] is None
    back = next(i for i in items(reality) if i["item_id"] == coded["item_id"])
    assert back["grade"] == coded["grade"]
    bad = client.put(url, json={"grade": "certain"})
    assert bad.status_code == 422
    assert bad.json()["error"]["message"] == "Choose Confirmed, Indicated or Hypothesis."
    assert client.put("/api/discrepancy-items/nope/grade", json={"grade": other}).status_code == 404


def test_every_gap_finding_carries_a_grade_and_erics_choice_wins(drafted: Drafted) -> None:
    client = drafted.client
    report = analyse(drafted)
    findings = report["findings"]
    assert findings
    for f in findings:
        g = f["grade"]
        assert g["grade"] == g["suggested"] and not g["chosen_by_owner"]
        if f["provenance"] != "O" or f["verification_status"] != "verified":
            assert g["suggested"] == "hypothesis"
    target = findings[0]
    other = next(g for g in grade.GRADES if g != target["grade"]["suggested"])
    url = f"/api/gap-findings/{target['id']}/grade"
    chosen = client.put(url, json={"grade": other})
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["grade"] == {**target["grade"], "grade": other, "chosen_by_owner": True}
    # The grade is a label only: provenance, checks and disposition stay as they were.
    for kept in ("provenance", "verification_status", "disposition", "section", "evidence"):
        assert chosen.json()[kept] == target[kept]
    again = client.get(f"/api/gap-analyses/{report['analysis']['id']}").json()["findings"][0]
    assert again["grade"]["grade"] == other
    assert "Set gap finding grade" in [r["action"] for r in
                                       audit_actions(client, drafted.engagement_id)]  # fmt: skip
    assert client.put(url, json={"grade": None}).json()["grade"] == target["grade"]
    assert client.put(url, json={"grade": "sure"}).status_code == 422
    assert client.put("/api/gap-findings/nope/grade", json={"grade": other}).status_code == 404
    # A finalised report is a record: its grades no longer change.
    decide_all_internal(drafted, client.get(f"/api/gap-analyses/{report['analysis']['id']}").json())
    done = client.post(f"/api/gap-analyses/{report['analysis']['id']}/finalise")
    assert done.status_code == 200, done.text
    late = client.put(url, json={"grade": other})
    assert late.status_code == 409
    assert late.json()["error"]["message"] == "This report is finalised and can't be changed."
