"""P10b so far, end to end (R1-R6; PRD §3.13, criteria 82-88): the system-records chain on the
drafted Appendix A sample with fixture A.11, Claude mocked, and the rest of the app checked for
unintended changes. A regression net for the phase: every existing read endpoint is compared
before and after the log is imported and matched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.unit.test_log_alignment_api import CODES, EXPECTED, UNRECORDED, import_log
from tests.unit.test_publish_api import confirm_all, publish
from tests.unit.test_review_actions import Drafted, drafted
from tests.uploads import wait_for_jobs

__all__ = ["drafted"]

VERSION_READS = [
    "graph", "graph?view=done", "graph?view=documented", "layout", "layout?view=done",
    "layout?view=documented", "alignment-matrix", "registers", "capability-notes", "coverage",
    "exceptions?view=done", "exceptions?view=documented", "lane-boundaries", "validation-pack",
    "stories", "glossary", "lint", "quality-card",
]  # fmt: skip
SYSTEM_TYPES = {"hidden_work", "offline_work", "sequence_drift", "estimate_gap", "measured_rework"}


def snapshot(d: Drafted) -> dict[str, Any]:
    """Every read the screens use for the draft, and every step's panel."""
    out: dict[str, Any] = {}
    for path in VERSION_READS:
        response = d.client.get(f"/api/versions/{d.version_id}/{path}")
        assert response.status_code == 200, (path, response.text[:200])
        is_json = response.headers["content-type"].startswith("application/json")
        out[path] = response.json() if is_json else response.content  # files compare as bytes
    for label, element_id in d.ids.items():
        out[f"panel: {label}"] = d.client.get(f"/api/elements/{element_id}").json()
    return out


def changes(a: Any, b: Any, path: str = "") -> list[str]:
    """Where two JSON values differ, as paths."""
    if isinstance(a, dict) and isinstance(b, dict):
        return [
            c for k in sorted(set(a) | set(b)) for c in changes(a.get(k), b.get(k), f"{path}.{k}")
        ]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [c for i, (x, y) in enumerate(zip(a, b, strict=True))
                for c in changes(x, y, f"{path}[{i}]")]  # fmt: skip
    return [] if a == b else [path]


def test_importing_and_matching_a_log_changes_only_what_it_should(drafted: Drafted) -> None:
    d = drafted
    before = snapshot(d)
    lid = import_log(d.client, d.engagement_id)
    assert snapshot(d) == before  # an imported log, matched by nobody yet, changes nothing
    rows = [
        {"activity": a, "element_id": d.ids[s], "status": "confirmed"} for a, s in EXPECTED.items()
    ]
    assert d.client.put(f"/api/event-logs/{lid}/alignment", json={"rows": rows}).status_code == 200
    after = snapshot(d)
    changed = {key: changes(before[key], after[key]) for key in before}
    changed = {key: paths for key, paths in changed.items() if paths}
    # Only the order basis of the lines the system records: the three graph reads, nothing else.
    assert set(changed) == {"graph", "graph?view=done", "graph?view=documented"}
    for paths in changed.values():
        assert paths and all(
            p.startswith(".edges[") and p.endswith(".sequence_basis") for p in paths
        )


def test_the_system_records_chain_end_to_end(drafted: Drafted) -> None:
    d, client = drafted, drafted.client
    seen: list[str] = []  # every answer, for the user-ID scan at the end

    def get(url: str, **params: Any) -> Any:
        response = client.get(url, params=params)
        assert response.status_code == 200, (url, response.text)
        seen.append(response.text)
        return response.json()

    # R1: the data request template, no engagement needed.
    for fmt in ("docx", "md", "csv"):
        assert client.get("/api/templates/data-request", params={"format": fmt}).status_code == 200
    # R2-R3: upload, map, approve, import (the approval gate first).
    lid = import_log(client, d.engagement_id)
    log = get(f"/api/event-logs/{lid}")
    assert (log["status"], log["file_held"]) == ("imported", False)
    assert log["validation_report"]["cases"] == 200
    # R4: every metric scope, nothing under 5 cases.
    for scope in ("activity", "transition", "case", "variant", "role"):
        body = get(f"/api/event-logs/{lid}/metrics", scope=scope)
        assert all(g["case_count"] >= 5 for g in body["groups"])
    # R5a: proposals as A.11 expects; Claude's planted suggestions are left out.
    table = get(f"/api/event-logs/{lid}/alignment")
    proposed = {r["activity"]: r["element_label"] for r in table["rows"] if r["activity"]}
    assert {a: s for a, s in proposed.items() if s} == EXPECTED
    started = client.post(f"/api/event-logs/{lid}/alignment/suggest").json()
    wait_for_jobs(client)
    assert get(f"/api/jobs/{started['job_id']}")["message"].startswith(
        "Claude suggested 0 matches."
    )
    # Eric confirms everything.
    rows = [
        {"activity": a, "element_id": d.ids[s], "status": "confirmed"} for a, s in EXPECTED.items()
    ]
    rows.append({"activity": "Manual weight override", "element_id": None, "status": "hidden_work"})
    rows += [
        {"activity": "", "element_id": d.ids[s], "status": "no_system_record"} for s in UNRECORDED
    ]
    assert client.put(f"/api/event-logs/{lid}/alignment", json={"rows": rows}).status_code == 200
    assert get(f"/api/event-logs/{lid}/alignment")["summary"]["waiting"] == 0
    # R5b: the map shows the system trace.
    graph = get(f"/api/versions/{d.version_id}/graph")
    assert sum(e["sequence_basis"] == "system_trace" for e in graph["edges"]) == 5
    traces = get(f"/api/versions/{d.version_id}/system-traces")
    assert (traces[0]["label"], traces[0]["rework_share"]) == ("Draft load plan", 0.2)
    # R6: Analysis A lists the system findings.
    started = client.post(f"/api/versions/{d.version_id}/gap-analyses/internal").json()
    wait_for_jobs(client)
    report = get(f"/api/gap-analyses/{started['analysis_id']}")
    kinds = {f["finding_type"] for f in report["findings"]}
    assert {"hidden_work", "offline_work", "measured_rework"} <= kinds
    assert not {"estimate_gap", "sequence_drift"} & kinds
    # Publishing freezes the trace; the published exports carry no user ID.
    confirm_all(d)
    shown = get(f"/api/versions/{d.version_id}/graph")
    assert publish(d).status_code == 200
    assert get(f"/api/versions/{d.version_id}/graph")["edges"] == shown["edges"]
    for fmt in ("md", "json", "csv", "html"):
        exported = client.get(f"/api/versions/{d.version_id}/export/{fmt}")
        assert exported.status_code == 200, (fmt, exported.text[:200])
        seen.append(exported.text)
    get(f"/api/versions/{d.version_id}/leadership")
    get(f"/api/engagements/{d.engagement_id}/event-logs")
    # Constraint 24, criterion 84: no user ID anywhere the app answers or stores.
    answers = "\n".join(seen)
    data_dir = Path(client.app.state.config.data_dir)  # type: ignore[attr-defined]
    stored = b"".join(p.read_bytes() for p in data_dir.rglob("*") if p.is_file())
    for code in CODES:
        assert code not in answers, code
        assert code.encode() not in stored, code
    assert json.loads(json.dumps(report))  # the report is plain JSON


# --- The frontend's view of the system-records shapes (like the X4 sample) --------------------

TIMESTAMP_KEYS = {"created_at", "approved_at", "completed_at", "finalised_at"}


def _fixed_times(data: Any) -> Any:
    """Creation and approval times vary per run; the log's own dates stay as they are."""
    if isinstance(data, dict):
        return {k: ("2026-10-08T00:00:00+00:00" if k in TIMESTAMP_KEYS and v else _fixed_times(v))
                for k, v in data.items()}  # fmt: skip
    if isinstance(data, list):
        return [_fixed_times(v) for v in data]
    return data


def test_the_frontend_system_records_sample_matches_the_backend(drafted: Drafted) -> None:
    """frontend/tests/fixtures/system_records.json: every P10b shape as the backend sends it, for
    the frontend's field-by-field type check. Not a PRD baseline (no user ID in it: the held log
    is a small file whose user IDs are `U1` and `U2`). Rewritten with PMS_UPDATE_GOLDEN=1."""
    from tests.golden.test_golden_baselines import FRONTEND_FIXTURES, matches_baseline

    d, client = drafted, drafted.client
    held = client.post(
        f"/api/engagements/{d.engagement_id}/event-logs",
        files={"file": ("small.csv", b"Case ID,Event Name,Start Time,Performed by,Team\n"
                        b"C1,Opened,2026-03-02 09:00,U1,Load controller\n"
                        b"C1,Closed,2026-03-02 10:00,U2,\n", "text/csv")},
        data={"name": "Small extract", "system": "DCS", "window_start": "2026-03-02",
              "window_end": "2026-03-31"},
    ).json()  # fmt: skip
    lid = import_log(client, d.engagement_id)
    rows = [
        {"activity": a, "element_id": d.ids[s], "status": "confirmed"}
        for a, s in EXPECTED.items()
        if a != "Plan revised"
    ]  # one left as the app's proposal
    rows.append({"activity": "Manual weight override", "element_id": None, "status": "hidden_work"})
    rows.append({"activity": "", "element_id": d.ids["Read report at aircraft"],
                 "status": "no_system_record"})  # fmt: skip
    client.put(f"/api/event-logs/{lid}/alignment", json={"rows": rows})
    started = client.post(f"/api/versions/{d.version_id}/gap-analyses/internal").json()
    wait_for_jobs(client)
    report = client.get(f"/api/gap-analyses/{started['analysis_id']}").json()
    # R9: one role cost and one choice, so every value and disposition field has a value.
    lc = next(r["id"] for r in client.get(f"/api/engagements/{d.engagement_id}/roles").json()
              if r["name"] == "Load controller")  # fmt: skip
    cost = {"role_id": lc, "hourly_cost": 48, "note": "Loaded rate"}
    client.put(f"/api/engagements/{d.engagement_id}/role-costs", json={"rows": [cost]})
    client.put(f"/api/elements/{d.ids['Issue load sheet']}/disposition",
               json={"disposition": "automate_rules", "note": "Rules exist."})  # fmt: skip
    client.put(f"/api/elements/{d.ids['Resolve or offload']}/value-override",
               json={"volume_month": 30, "note": "Shift log"})  # fmt: skip
    bundle = {
        "held_log": held,
        "imported_log": client.get(f"/api/event-logs/{lid}").json(),
        "metrics": {s: client.get(f"/api/event-logs/{lid}/metrics", params={"scope": s}).json()
                    for s in ("activity", "transition", "case", "variant", "role")},
        "alignment": client.get(f"/api/event-logs/{lid}/alignment").json(),
        "system_traces": client.get(f"/api/versions/{d.version_id}/system-traces").json(),
        "system_variants": client.get(f"/api/versions/{d.version_id}/system-variants").json(),
        "dispositions": client.get(f"/api/versions/{d.version_id}/dispositions").json(),
        "role_costs": client.get(f"/api/engagements/{d.engagement_id}/role-costs").json(),
        "value_assumptions":
            client.get(f"/api/engagements/{d.engagement_id}/value-assumptions").json(),
        "value": client.get(f"/api/versions/{d.version_id}/value").json(),
        "system_findings": [f for f in report["findings"]
                            if any(e["side"] == "system" for e in f["evidence"])],
    }  # fmt: skip
    text = json.dumps(bundle)
    assert not any(code in text for code in CODES)  # constraint 24: the fixture has no user ID
    matches_baseline("system_records.json", _fixed_times(bundle), FRONTEND_FIXTURES)
