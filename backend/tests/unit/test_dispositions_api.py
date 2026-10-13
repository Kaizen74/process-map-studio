"""Step disposition (API_CONTRACT.md → Step disposition; PRD §3.15; criterion 91; R9a): the
drafted Appendix A sample, with fixture A.11 for the dead-control Delete."""

from __future__ import annotations

from typing import Any

from tests.unit.test_log_alignment_api import EXPECTED, UNRECORDED, import_log
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted
from tests.unit.test_review_refresh import ids_by_label, refresh

__all__ = ["drafted"]

SUGGESTED = {
    "Draft load plan": "ai_assisted",  # complicated
    "Approve load plan": "human_approves",
    "Special loads OK?": "automate_rules",  # clear and rule-based
    "Resolve or offload": "keep_human",
    "Load and return LIR": "keep_human",  # work type not confirmed
    "Busy wave?": "keep_human",
    "Read report at aircraft": "keep_human",
    "Deviation in limits?": "keep_human",  # complex
    "Approve deviation": "human_approves",
    "Issue load sheet": "automate_rules",
}


def rows(d: Drafted, version_id: str | None = None) -> dict[str, dict[str, Any]]:
    response = d.client.get(f"/api/versions/{version_id or d.version_id}/dispositions")
    assert response.status_code == 200, response.text
    return {r["label"]: r for r in response.json()}


def choose(d: Drafted, label: str, **body: Any) -> Any:
    return d.client.put(f"/api/elements/{d.ids[label]}/disposition", json={"note": ""} | body)


def test_every_step_has_a_suggestion_with_its_reason(drafted: Drafted) -> None:
    found = rows(drafted)
    assert {k: v["suggested"] for k, v in found.items()} == SUGGESTED
    assert found["Deviation in limits?"]["reason"] == "Complex work: it needs human judgment."
    assert found["Draft load plan"]["reason"].endswith(
        "Needs a complete AI flag before you can choose it.")  # fmt: skip
    assert all(r["disposition"] is None and r["risk_flag"] == "none" for r in found.values())
    assert found["Deviation in limits?"]["allowed"] == ["delete", "human_approves", "keep_human"]
    # R10b: every other disposition says why it is refused, so the panel can explain it.
    complex_work = "Complex work can't be automated or AI-assisted."
    assert found["Deviation in limits?"]["not_allowed"] == [
        {"disposition": "automate_rules", "reason": complex_work},
        {"disposition": "ai_assisted", "reason": complex_work},
    ]
    for row in found.values():
        assert sorted(row["allowed"] + [n["disposition"] for n in row["not_allowed"]]) == sorted(
            ["delete", "automate_rules", "ai_assisted", "human_approves", "keep_human"]
        )


def test_a11_suggests_deleting_the_documented_control_with_no_record(drafted: Drafted) -> None:
    lid = import_log(drafted.client, drafted.engagement_id)
    decided = [{"activity": a, "element_id": drafted.ids[s], "status": "confirmed"}
               for a, s in EXPECTED.items()]  # fmt: skip
    decided += [{"activity": "", "element_id": drafted.ids[s], "status": "no_system_record"}
                for s in UNRECORDED]  # fmt: skip
    drafted.client.put(f"/api/event-logs/{lid}/alignment", json={"rows": decided})
    approve = rows(drafted)["Approve load plan"]
    assert approve["suggested"] == "delete"
    assert approve["reason"] == (
        "The documents describe it, no interview mentions it, the DCS extract log has no record "
        "of it and no purpose is stated."
    )
    # Practiced steps with no record are offline work, never Delete.
    assert rows(drafted)["Read report at aircraft"]["suggested"] == "keep_human"


def test_eric_chooses_and_it_is_audited(drafted: Drafted) -> None:
    response = choose(drafted, "Approve load plan", disposition="keep_human",
                      note="The airline asks for it.")  # fmt: skip
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["disposition"], body["suggested"], body["note"]) == (
        "keep_human", "human_approves", "The airline asks for it.")  # fmt: skip
    assert rows(drafted)["Approve load plan"]["disposition"] == "keep_human"
    [row] = [a for a in drafted.audit() if a["action"] == "Chose disposition"]
    assert row["before"] == {"disposition": None, "note": "", "risk_flag": "none"}
    assert row["after"]["suggested"] == "human_approves"
    # The same choice again changes nothing and writes no second row.
    choose(drafted, "Approve load plan", disposition="keep_human", note="The airline asks for it.")
    assert len([a for a in drafted.audit() if a["action"] == "Chose disposition"]) == 1
    # Cleared.
    assert choose(drafted, "Approve load plan", disposition=None).json()["disposition"] is None


def test_a_risk_flag_makes_a_person_authorise_it(drafted: Drafted) -> None:
    body = choose(drafted, "Load and return LIR", disposition=None, risk_flag="financial").json()
    assert (body["risk_flag"], body["suggested"]) == ("financial", "human_approves")
    assert body["reason"] == "Carries a financial risk: a person authorises it."
    # Left out, the risk flag keeps its value.
    kept = choose(drafted, "Load and return LIR", disposition=None).json()
    assert kept["risk_flag"] == "financial"


def test_the_rules_refuse_what_the_step_cant_be(drafted: Drafted) -> None:
    def refused(label: str, **body: Any) -> tuple[int, str, str]:
        r = choose(drafted, label, **body)
        error = r.json()["error"]
        return r.status_code, error["details"].get("field", ""), error["message"]

    assert refused("Deviation in limits?", disposition="automate_rules") == (
        422, "disposition", "Complex work can't be automated or AI-assisted.")  # fmt: skip
    assert refused("Draft load plan", disposition="ai_assisted")[2] == (
        "Add a complete AI flag first: component, input, output, handoff and basis.")  # fmt: skip
    assert refused("Approve deviation", disposition="automate_rules")[2] == (
        "A judgment step can't be automated by rules.")  # fmt: skip
    assert refused("Issue load sheet", disposition="outsource")[2] == (
        "Choose one of the five dispositions.")  # fmt: skip
    assert refused("Issue load sheet", disposition=None, risk_flag="fire")[1] == "risk_flag"
    assert refused("Issue load sheet", disposition=None, note="x" * 301)[1] == "note"
    assert refused("Issue load sheet", disposition=None, note="a\nb")[1] == "note"
    start = next(
        e["id"]
        for e in drafted.client.get(f"/api/versions/{drafted.version_id}/graph").json()["elements"]
        if e["kind"] == "start"
    )
    assert drafted.client.put(f"/api/elements/{start}/disposition",
                              json={"disposition": "delete"}).status_code == 422  # fmt: skip
    assert drafted.client.put("/api/elements/nope/disposition",
                              json={"disposition": None}).status_code == 404  # fmt: skip
    assert drafted.client.get("/api/versions/nope/dispositions").status_code == 404


def test_a_hidden_name_is_refused_in_the_note(drafted: Drafted) -> None:
    drafted.client.post(f"/api/engagements/{drafted.engagement_id}/redaction-terms",
                        json={"term": "Priya Nair", "kind": "name"})  # fmt: skip
    r = choose(drafted, "Issue load sheet", disposition=None, note="Ask Priya Nair")
    assert r.status_code == 422 and r.json()["error"]["details"]["field"] == "note"


def test_lint_l10_and_complex_work_undo_automation(drafted: Drafted) -> None:
    assert choose(drafted, "Issue load sheet", disposition="automate_rules").status_code == 200
    lint = drafted.client.get(f"/api/versions/{drafted.version_id}/lint").json()
    assert not [f for f in lint["failures"] if f["rule"] == "L10"]
    # Eric confirms the step as complex work: the automation choice is undone and audited.
    drafted.client.put(f"/api/elements/{drafted.ids['Issue load sheet']}/work-type",
                       json={"work_type": "complex", "confirm": True})  # fmt: skip
    assert rows(drafted)["Issue load sheet"]["disposition"] is None
    changed = [a for a in drafted.audit() if a["action"] == "Changed work type"][-1]
    assert (changed["before"]["disposition"], changed["after"]["disposition"]) == (
        "automate_rules", None)  # fmt: skip


def test_the_choice_survives_reopen_and_refresh(drafted: Drafted) -> None:
    choose(drafted, "Issue load sheet", disposition="automate_rules", note="Rules exist.")
    # Refresh: the step is unreviewed, so it is redrafted; Eric's choice goes to its successor.
    refresh(drafted)
    assert ids_by_label(drafted)["Issue load sheet"] != drafted.ids["Issue load sheet"]
    kept = rows(drafted)["Issue load sheet"]
    assert (kept["disposition"], kept["note"]) == ("automate_rules", "Rules exist.")
    # Reopen copies it into the new draft; the published version keeps it too.
    drafted.ids.update(ids_by_label(drafted))
    confirm_all(drafted)
    assert publish(drafted).status_code == 200
    assert drafted.client.put(f"/api/elements/{drafted.ids['Issue load sheet']}/disposition",
                              json={"disposition": None}).status_code == 409  # fmt: skip
    draft = drafted.client.post(f"/api/versions/{drafted.version_id}/reopen").json()
    assert rows(drafted, draft["id"])["Issue load sheet"]["disposition"] == "automate_rules"
