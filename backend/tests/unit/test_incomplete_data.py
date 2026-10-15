"""Incomplete data (Eric, 2026-10-14): the app must work with whatever an engagement has. Each
scenario below builds an engagement with part of the evidence through the real API (Claude mocked)
and then asks every screen's data: every GET route the app has, with the scenario's IDs, plus the
actions that start work. Nothing may fail with a server error; a refusal says what is missing in
plain words; no screen shows "None" or "nan" where a figure is missing.

Scenarios: nothing yet · documents only · interviews only · interviews and documents (no system
log) · interviews and a system log (no documents) · documents, interviews and a log not yet matched
to the map · a charter without SOPs · everything (A.12)."""

from __future__ import annotations

import re
import warnings
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import AppConfig
from app.domain.reality import Shape
from app.services.reality_shapes import collisions
from tests import fixture_engagement
from tests.unit.test_draft_api import make_client, run_draft, with_key
from tests.unit.test_log_alignment_api import EXPECTED, UNRECORDED, import_log
from tests.uploads import FIXTURES, wait_for_jobs

CHARTER = "charter_load_control.docx"
INTERVIEW = ["interview_transcript.txt"]
DOCUMENTS = ["sop_LC-07.docx", "sop_RP-02.docx", "jd_load_control_lead.docx"]
# Words that mean a missing value leaked into what a screen shows.
LEAKS = re.compile(r"\bNone\b|\bnan\b|\bNaN\b|\binf\b|\bundefined\b")
SKIP = {
    "/api/images/{image_id}/file",  # no picture in these scenarios
    "/api/{rest:path}",
}  # the "no such address" answer for anything else


# The same screens with their other options: the As documented view, every metrics scope and
# every export format.
VARIANTS = [
    *(f"/api/versions/{{version_id}}/{what}?view=documented"
      for what in ("graph", "layout", "exceptions", "value")),
    *(f"/api/event-logs/{{log_id}}/metrics?scope={scope}"
      for scope in ("activity", "transition", "case", "variant", "role")),
    *(f"/api/versions/{{version_id}}/export/{fmt}" for fmt in ("md", "json", "csv", "html")),
]  # fmt: skip


@dataclass
class Scenario:
    client: TestClient
    ids: dict[str, str] = field(default_factory=dict)  # path parameter → a real ID


def _upload(client: TestClient, eid: str, name: str, folder: str = "") -> str:
    path = (FIXTURES.parent / folder / name) if folder else FIXTURES / name
    response = client.post(
        f"/api/engagements/{eid}/sources",
        files={"file": (name, path.read_bytes(), "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    wait_for_jobs(client)
    return str(response.json()["id"])


def _draft(s: Scenario) -> None:
    job = run_draft(s.client, s.ids["engagement_id"])
    assert job["status"] == "done", job
    s.ids["version_id"] = job["target_id"]
    s.ids["job_id"] = job["id"]
    graph = s.client.get(f"/api/versions/{job['target_id']}/graph").json()
    steps = [e for e in graph["elements"] if e["kind"] not in ("start", "end")]
    if steps:
        s.ids["element_id"] = steps[0]["id"]


def _align(s: Scenario, lid: str, *, confirm: bool) -> None:
    s.ids["log_id"] = lid
    if not confirm:
        return
    graph = s.client.get(f"/api/versions/{s.ids['version_id']}/graph").json()
    ids = {e["label"]: e["id"] for e in graph["elements"]}
    rows: list[dict[str, Any]] = [{"activity": a, "element_id": ids[step], "status": "confirmed"}
                                  for a, step in EXPECTED.items() if step in ids]  # fmt: skip
    rows.append({"activity": "Manual weight override", "element_id": None,
                 "status": "hidden_work"})  # fmt: skip
    rows += [{"activity": "", "element_id": ids[step], "status": "no_system_record"}
             for step in UNRECORDED if step in ids]  # fmt: skip
    response = s.client.put(f"/api/event-logs/{lid}/alignment", json={"rows": rows})
    assert response.status_code == 200, response.text


def _intent(s: Scenario) -> None:
    """Whatever the charter gives (if anything), confirmed, plus an owner-stated target."""
    eid = s.ids["engagement_id"]
    s.client.post(f"/api/engagements/{eid}/intent/extract")
    wait_for_jobs(s.client)
    for statement in s.client.get(f"/api/engagements/{eid}/intent").json():
        if statement["verification_status"] == "verified":
            s.client.patch(f"/api/intent/{statement['id']}", json={"status": "confirmed"})
    roles = {r["name"]: r["id"] for r in s.client.get(f"/api/engagements/{eid}/roles").json()}
    target = {"scope": "process", "kind": "target", "text": "A flight is closed out in 60 minutes.",
              "metric": "cycle_time_min", "comparator": "at_most", "target_value": 60,
              "unit": "min", "owner_role_id": roles["Load control lead"],
              "stated_on": "2026-10-01"}  # fmt: skip
    response = s.client.post(f"/api/engagements/{eid}/intent", json=target)
    assert response.status_code == 201, response.text
    s.ids["intent_id"] = response.json()["id"]


def _publish(s: Scenario) -> None:
    """Every step confirmed, every merge proposal decided, then published (as Eric would)."""
    vid = s.ids["version_id"]
    graph = s.client.get(f"/api/versions/{vid}/graph").json()
    for e in graph["elements"]:
        if e["kind"] not in ("start", "end"):
            assert s.client.post(f"/api/elements/{e['id']}/confirm").status_code == 200
    for m in s.client.get(f"/api/versions/{vid}/merge-proposals").json():
        if m.get("decision") == "pending":
            decided = s.client.post(
                f"/api/merge-proposals/{m['id']}/decision", json={"decision": "split"}
            )  # keep them apart
            assert decided.status_code == 200, decided.text
    response = s.client.post(f"/api/versions/{vid}/publish")
    assert response.status_code == 200, response.text


def nothing(s: Scenario) -> None:
    pass


def documents_only(s: Scenario) -> None:
    for name in DOCUMENTS:
        s.ids["source_id"] = _upload(s.client, s.ids["engagement_id"], name)


def interviews_only(s: Scenario) -> None:
    built = fixture_engagement.build(s.client, INTERVIEW)
    s.ids |= {"engagement_id": built.engagement_id,
              "source_id": built.sources["interview_transcript.txt"]}  # fmt: skip
    _draft(s)
    _intent(s)


def interviews_and_documents(s: Scenario) -> None:
    built = fixture_engagement.build(s.client)
    s.ids |= {"engagement_id": built.engagement_id,
              "source_id": built.sources["sop_LC-07.docx"]}  # fmt: skip
    _draft(s)
    _intent(s)


def interviews_and_log(s: Scenario) -> None:
    interviews_only(s)
    _align(s, import_log(s.client, s.ids["engagement_id"]), confirm=True)


def log_not_matched(s: Scenario) -> None:
    interviews_and_documents(s)
    _align(s, import_log(s.client, s.ids["engagement_id"]), confirm=False)


def charter_without_sops(s: Scenario) -> None:
    built = fixture_engagement.build(s.client, INTERVIEW)
    s.ids["engagement_id"] = built.engagement_id
    s.ids["source_id"] = _upload(s.client, built.engagement_id, CHARTER, "reality")
    _draft(s)
    _intent(s)


def everything(s: Scenario) -> None:
    built = fixture_engagement.build(s.client)
    s.ids["engagement_id"] = built.engagement_id
    s.ids["source_id"] = _upload(s.client, built.engagement_id, CHARTER, "reality")
    _draft(s)
    _align(s, import_log(s.client, built.engagement_id), confirm=True)
    _intent(s)


def published_interviews_only(s: Scenario) -> None:
    interviews_only(s)
    _publish(s)


def published_interviews_and_documents(s: Scenario) -> None:
    interviews_and_documents(s)
    _publish(s)


def published_everything(s: Scenario) -> None:
    everything(s)
    _publish(s)


SCENARIOS: dict[str, Callable[[Scenario], None]] = {
    "nothing": nothing, "documents_only": documents_only, "interviews_only": interviews_only,
    "interviews_and_documents": interviews_and_documents,
    "interviews_and_log": interviews_and_log, "log_not_matched": log_not_matched,
    "charter_without_sops": charter_without_sops, "everything": everything,
    "published_interviews_only": published_interviews_only,
    "published_interviews_and_documents": published_interviews_and_documents,
    "published_everything": published_everything,
}  # fmt: skip
NEW_ENGAGEMENT = ("nothing", "documents_only")


@pytest.fixture(params=list(SCENARIOS), ids=list(SCENARIOS))
def scenario(request: pytest.FixtureRequest, settings_config: AppConfig) -> Iterator[Scenario]:
    for client in make_client(settings_config):
        with_key(client)
        s = Scenario(client)
        if request.param in NEW_ENGAGEMENT:
            s.ids["engagement_id"] = client.post(
                "/api/engagements", json={"name": "Load control"}).json()["id"]  # fmt: skip
            for name in ("Load controller", "Load control lead"):
                client.post(f"/api/engagements/{s.ids['engagement_id']}/roles",
                            json={"name": name})  # fmt: skip
        SCENARIOS[request.param](s)
        yield s


def _get_routes(client: TestClient) -> list[str]:
    """Every GET address the app documents (its OpenAPI description lists them all)."""
    with warnings.catch_warnings():  # the catch-all "no such address" answer repeats its name
        warnings.simplefilter("ignore", UserWarning)
        paths = client.app.openapi()["paths"]  # type: ignore[attr-defined]
    return sorted(p for p, methods in paths.items() if "get" in methods and p.startswith("/api/"))


def _leak(response: Any) -> str:
    """A missing value shown as text, with what's around it ("" when there is none)."""
    if "json" not in response.headers.get("content-type", ""):
        return ""
    found = LEAKS.search(response.text)
    if found is None:
        return ""
    return repr(response.text[max(0, found.start() - 80) : found.end() + 40])


def _plain(response: Any) -> str:
    return str(response.json().get("error", {}).get("message", ""))


def test_every_screen_answers_with_incomplete_data(scenario: Scenario) -> None:
    client, ids = scenario.client, scenario.ids | {"fmt": "md"}
    problems: list[str] = []
    asked = 0
    for path in [*_get_routes(client), *VARIANTS]:
        names = re.findall(r"{(\w+)}", path.split("?")[0])
        if path in SKIP or any(n not in ids for n in names):
            continue
        url = path.format(**{n: ids[n] for n in names})
        response = client.get(url)
        asked += 1
        if response.status_code >= 500:
            problems.append(f"{path}: {response.status_code} {response.text[:200]}")
        elif response.status_code >= 400 and not _plain(response):
            problems.append(f"{path}: {response.status_code} without a plain message")
        elif response.status_code == 200 and (leak := _leak(response)):
            problems.append(f"{path}: shows {leak}")
    assert asked >= 20
    assert problems == []


def test_starting_work_explains_what_is_missing(scenario: Scenario) -> None:
    """Starting a draft, intent extraction, the design-gap comparison or gap analysis A either
    starts a job that ends with a plain message, or is refused with one."""
    client, ids = scenario.client, scenario.ids
    eid = ids["engagement_id"]
    starts = [f"/api/engagements/{eid}/intent/extract"]
    if "version_id" not in ids:
        starts.append(f"/api/engagements/{eid}/draft")
    else:
        vid = ids["version_id"]
        starts += [f"/api/versions/{vid}/intent/compare",
                   f"/api/versions/{vid}/gap-analyses/internal"]  # fmt: skip
    problems, jobs = [], []
    for url in starts:
        response = client.post(url)
        if response.status_code >= 500:
            problems.append(f"{url}: {response.status_code} {response.text[:200]}")
        elif response.status_code >= 400 and not _plain(response):
            problems.append(f"{url}: {response.status_code} without a plain message")
        elif response.status_code == 202:
            jobs.append((url, response.json()["job_id"]))
    wait_for_jobs(client)
    for url, job_id in jobs:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] == "failed" and not job["error"]:
            problems.append(f"{url}: the job failed without saying why")
        elif job["status"] == "done" and not job["message"] and "draft" not in url:
            problems.append(f"{url}: the job ended without a message")
        if LEAKS.search(f"{job['message']} {job['error']}"):
            problems.append(
                f"{url}: job text shows a missing value: {job['message']}{job['error']}"
            )
    assert problems == []


FIGURE_LABELS = {"measured", "stated", "documented", "target", "mixed"}
VALUE_LABELS = {"measured", "estimated", "assumed", "mixed"}


def test_every_figure_says_where_it_comes_from(scenario: Scenario) -> None:
    """With whatever evidence there is, a figure is labelled by where it comes from; where there
    is none, the screen says what is missing instead of showing a number; nothing is "measured"
    without a system log."""
    client, ids = scenario.client, scenario.ids
    if "version_id" not in ids:
        return
    vid, has_log = ids["version_id"], "log_id" in ids
    problems = []
    for view in ("done", "documented"):
        value = client.get(f"/api/versions/{vid}/value?view={view}").json()
        for step in value["steps"]:
            if step["hours_per_month"] is None and not step["missing"]:
                problems.append(f"value {view}: {step['label']} has no hours and no reason")
            if step["hours_per_month"] is not None and step["evidence"] not in VALUE_LABELS:
                problems.append(f"value {view}: {step['label']} hours without a label")
            if step["evidence"] == "measured" and not has_log:
                problems.append(f"value {view}: {step['label']} measured without a log")
    found = client.get(f"/api/versions/{vid}/discrepancies").json()
    for item in found["items"]:
        for delta in item["deltas"]:
            if delta["kind"] not in FIGURE_LABELS or not delta["label"]:
                problems.append(f"discrepancy {item['code']}: {delta} unlabelled")
            if delta["kind"] == "measured" and not has_log:
                problems.append(f"discrepancy {item['code']}: measured without a log")
        if item["code"] and item["verdict"] and not item["verdict"]["reason"]:
            problems.append(f"discrepancy {item['code']}: a verdict without a reason")
    snapshot = client.get(f"/api/versions/{vid}/reality").json()  # P13b
    stack = [snapshot]
    while stack:  # every figure anywhere in the Reality snapshot
        value = stack.pop()
        if isinstance(value, dict):
            if {"id", "value", "unit", "text", "label"} <= set(value):
                if value["label"] not in FIGURE_LABELS | VALUE_LABELS:
                    problems.append(f"reality {value['id']}: unlabelled")
                if value["label"] == "measured" and not has_log:
                    problems.append(f"reality {value['id']}: measured without a log")
            stack += list(value.values())
        elif isinstance(value, list):
            stack += value
    for view in snapshot["views"].values():
        if not view["headline"]:
            problems.append(f"reality {view['id']}: no headline")
        if view["availability"]["state"] != "ready" and not view["availability"]["message"]:
            problems.append(f"reality {view['id']}: missing data without a message")  # P13c
        shapes = view["geometry"].get("shapes")
        if shapes is not None and collisions([Shape.model_validate(x) for x in shapes]):
            problems.append(f"reality {view['id']}: labels collide (RQ7)")
    if snapshot["views"]["rv7"]["case"]["events"] and not has_log:
        problems.append("reality rv7: a typical case without system records")
    for evaluation in found["intents"]:
        if evaluation["result"] != "unknown" and evaluation["label"] not in FIGURE_LABELS:
            problems.append(f"intent {evaluation['intent_id']}: a result without a label")
        if evaluation["label"] == "measured" and not has_log:
            problems.append(f"intent {evaluation['intent_id']}: measured without a log")
    assert problems == []


SIGNAL = {"nothing": None, "documents_only": None, "interviews_only": "limited",
          "interviews_and_log": "limited", "charter_without_sops": "moderate",
          "published_interviews_only": "limited"}  # fmt: skip


def test_the_evidence_behind_a_map_is_stated(
    scenario: Scenario, request: pytest.FixtureRequest
) -> None:
    """The readiness screen says how much independent evidence there is (signal strength), from
    nothing at all to interviews with a written procedure; a log never raises it (it shows what
    is recorded, not what is intended)."""
    name = request.node.callspec.id
    readiness = scenario.client.get(f"/api/engagements/{scenario.ids['engagement_id']}/readiness")
    assert readiness.status_code == 200, readiness.text
    found = readiness.json()["signal"]
    assert (found or {}).get("level") == SIGNAL.get(name, "strong")
    if found and found["level"] == "limited":
        assert "interviews only" in found["detail"]
