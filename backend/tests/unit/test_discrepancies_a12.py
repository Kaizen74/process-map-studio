"""The discrepancy engine on fixture A.12 (PRD Appendix A.12; P13a-3a): the drafted Appendix A
engagement with the A.11 system log aligned as A.11 expects, the charter's four statements
confirmed and the owner-stated rule entered. Every expected discrepancy is found with its types,
delta and label; the expected negatives are not; nothing calls Claude while classifying (RT7);
and without the log, interview silence on the documented approval is no skipped step (RT3)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from app.actions import discrepancies
from app.config import AppConfig
from app.domain.reality import Detection
from app.domain.result import Err, Ok
from app.services import ai_service
from tests.unit.test_intent_api import Engagement, build
from tests.unit.test_intent_api import engagement as engagement  # the shared fixture
from tests.unit.test_log_alignment_api import EXPECTED, UNRECORDED, import_log
from tests.uploads import wait_for_jobs

OWNER_RULE = "Weight deviations outside tolerance are decided by the Load control lead."


@dataclass
class Reality:
    engagement: Engagement
    version_id: str
    labels: dict[str, str]  # element ID → label
    anchors: dict[str, str]  # intent ID → charter anchor, or "owner"

    def detect(self) -> Detection:
        sessions = self.engagement.client.app.state.sessions  # type: ignore[attr-defined]
        result = discrepancies.detect_for(sessions, self.version_id)
        assert isinstance(result, Ok), result
        return result.value

    def table(self, detection: Detection) -> list[tuple[str, str, str, str]]:
        """(type, where, delta, label) for each discrepancy shown."""
        return [(d.type, " + ".join(self.labels.get(e, e) for e in d.element_ids)
                 or ", ".join(d.keys), d.delta.text, d.delta.label)
                for d in detection.discrepancies if d.shown]  # fmt: skip


def a12(engagement: Engagement, with_log: bool) -> Reality:
    client, eid = engagement.client, engagement.eid
    version_id = engagement.graph["version"]["id"]
    ids = {e["label"]: e["id"] for e in engagement.graph["elements"]}
    if with_log:
        lid = import_log(client, eid)
        rows: list[dict[str, Any]] = [{"activity": a, "element_id": ids[s], "status": "confirmed"}
                                      for a, s in EXPECTED.items()]  # fmt: skip
        rows.append({"activity": "Manual weight override", "element_id": None,
                     "status": "hidden_work"})  # fmt: skip
        rows += [{"activity": "", "element_id": ids[s], "status": "no_system_record"}
                 for s in UNRECORDED]  # fmt: skip
        assert client.put(f"/api/event-logs/{lid}/alignment", json={"rows": rows}).is_success
    assert client.post(f"/api/engagements/{eid}/intent/extract").status_code == 202
    wait_for_jobs(client)
    for s in client.get(f"/api/engagements/{eid}/intent").json():
        if s["verification_status"] == "verified":
            assert client.patch(f"/api/intent/{s['id']}", json={"status": "confirmed"}).is_success
    assert engagement.add(text=OWNER_RULE).status_code == 201
    anchors = {s["id"]: s["anchor"] or "owner"
               for s in client.get(f"/api/engagements/{eid}/intent").json()
               if s["status"] == "confirmed"}  # fmt: skip
    return Reality(engagement, version_id, {v: k for k, v in ids.items()}, anchors)


@pytest.fixture()
def reality(engagement: Engagement) -> Reality:
    return a12(engagement, with_log=True)


@pytest.fixture()
def silent(settings_config: AppConfig) -> Iterator[Reality]:
    for built in build(settings_config):
        yield a12(built, with_log=False)


def test_a12_every_expected_discrepancy_with_its_delta(
    reality: Reality, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_ai(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the discrepancy engine called Claude")

    monkeypatch.setattr(ai_service, "call_claude", no_ai)  # RT7: classifying never calls AI
    detection = reality.detect()
    assert detection.rules_version == "2"
    assert reality.table(detection) == [
        ("D4", "Draft load plan", "rework in 20% of cases", "measured"),
        ("D1", "Approve load plan", "never recorded; 100% of cases", "measured"),
        ("D11", "Approve load plan", "Approve load plan: 100% of cases without a record",
         "measured"),
        ("D2", "Resolve or offload", "described in 1 of 1 interviews", "stated"),
        ("D8", "Load and return LIR", "wait 13 min median, 90th percentile 27", "measured"),
        ("D2", "Busy wave?", "described in 1 of 1 interviews", "stated"),
        ("D2", "Read report at aircraft", "described in 1 of 1 interviews", "stated"),
        ("D12", "Deviation in limits?", "Load control lead (documented) vs Captain (done)",
         "stated"),
        ("D2", "Approve deviation", "described in 1 of 1 interviews", "stated"),
        ("D2", "activity:Manual weight override", "12% of cases", "measured"),
        ("D6", "Busy wave? + Read report at aircraft",
         "described in 1 of 1 interviews; no system record; tool “sheet”", "stated"),
        ("D13", "Draft load plan", "target T-120 vs documented T-90", "target"),
        ("D14", "Load and return LIR", "target 10 vs actual 13; met in 21% of cases", "measured"),
        ("D9", "process", "3 routes: 70%, 18%, 10%, Other 2%", "measured"),
    ]  # fmt: skip
    found = {(d.type, tuple(d.keys)) for d in detection.discrepancies}
    # A.12 expected negatives: no D7 on the loading report (13.4 vs 10 is within 50%), no D10
    # (official ten minutes vs 13.4 is a factor of 1.3), no D3 anywhere, no D5 (the approval is
    # never recorded, so it can't be seen being routed around).
    assert not {t for t, _ in found} & {"D3", "D5", "D7", "D10"}
    # The Re-trim loop back to the loading report isn't in the log: found, but not drawn.
    [loop] = [d for d in detection.discrepancies if d.type == "D4" and not d.shown]
    assert (reality.labels[loop.element_ids[0]], loop.incidence) == ("Load and return LIR", 0.0)
    controls = {d.type for d in detection.discrepancies if d.control}
    assert controls == {"D1", "D11"}  # the added approval (Approve deviation) is no control


def test_a12_intent_evaluations(reality: Reality) -> None:
    evaluations = {reality.anchors[i.intent_id]: i for i in reality.detect().intents}
    assert {a: (e.result, e.label) for a, e in evaluations.items()} == {
        "§1": ("met", "stated"), "§2": ("not_met", "measured"), "§3": ("not_met", "measured"),
        "§4": ("unknown", None), "owner": ("unknown", None),
    }  # fmt: skip
    first, second, third = evaluations["§1"], evaluations["§2"], evaluations["§3"]
    assert (first.actual, first.documented, first.documented_meets) == (120, 90, False)
    assert (second.met_share, second.cases) == (0.0, 200)  # not met in 100% of cases
    assert (third.actual, third.cases, third.documented, third.documented_meets) == (
        13.4, 200, 10, True)  # fmt: skip
    assert third.met_share == 0.21


def test_rt3_without_the_log_silence_is_never_a_skipped_step(silent: Reality) -> None:
    detection = silent.detect()
    at_approval = [d.type for d in detection.discrepancies
                   if silent.labels.get(d.element_ids[0] if d.element_ids else "")
                   == "Approve load plan"]  # fmt: skip
    assert at_approval == []
    evaluations = {silent.anchors[i.intent_id]: i for i in detection.intents}
    assert evaluations["§2"].result == "unknown"  # honest, never "met"
    assert (evaluations["§3"].result, evaluations["§3"].label) == ("not_met", "stated")
    stated = {(d.type, d.delta.label) for d in detection.discrepancies}
    assert ("D8", "stated") in stated and ("D14", "stated") in stated
    assert not any(d.delta.label == "measured" for d in detection.discrepancies)


def test_unconfirmed_and_dismissed_intent_is_never_an_input(reality: Reality) -> None:
    client = reality.engagement.client
    for intent_id, anchor in reality.anchors.items():
        if anchor in ("§1", "§3"):
            assert client.patch(f"/api/intent/{intent_id}", json={"status": "dismissed"}).is_success
    types = {d.type for d in reality.detect().discrepancies}
    assert "D13" not in types and "D14" not in types


def test_an_unknown_version_is_refused(reality: Reality) -> None:
    sessions = reality.engagement.client.app.state.sessions  # type: ignore[attr-defined]
    assert isinstance(discrepancies.detect_for(sessions, "nope"), Err)
