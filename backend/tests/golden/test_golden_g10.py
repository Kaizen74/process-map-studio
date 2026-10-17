"""G10 (PRD §6.2 item 4, §3.13; P10b R12): the system-records outputs from fixture A.11 on the
drafted Appendix A sample, byte for byte: the column map the app suggests, the final validation
report, every metric scope, the alignment as Eric confirms it (A.11's expected matches, the hidden
work and the steps with no system record), the system findings of Analysis A, and the
dispositions and value worked out from them. Claude is mocked (it suggests no further match).
No role cost is entered, so value shows hours, with "No hourly cost" where a cost would be.

Times that change on every run are fixed and record IDs replaced in order of first appearance,
as for G1-G9. To accept a legitimate change: PMS_UPDATE_GOLDEN=1, review the diff, log it in
DECISIONS.md; to show Eric first: PMS_GOLDEN_CANDIDATES=<folder>.
"""

from __future__ import annotations

from typing import Any

from tests.golden.test_golden_baselines import matches_baseline
from tests.unit.test_acceptance_p10b import SYSTEM_TYPES, _fixed_times
from tests.unit.test_log_alignment_api import CODES, EXPECTED, UNRECORDED, import_log
from tests.unit.test_review_actions import Drafted
from tests.unit.test_review_actions import drafted as drafted  # the shared fixture
from tests.uploads import wait_for_jobs

SCOPES = ("activity", "transition", "case", "variant", "role")


def test_g10_system_records_of_fixture_a11(drafted: Drafted) -> None:
    d, client = drafted, drafted.client

    def get(url: str, **params: Any) -> Any:
        response = client.get(url, params=params)
        assert response.status_code == 200, (url, response.text[:200])
        return response.json()

    lid = import_log(client, d.engagement_id)
    log = get(f"/api/event-logs/{lid}")
    started = client.post(f"/api/event-logs/{lid}/alignment/suggest").json()
    wait_for_jobs(client)
    assert get(f"/api/jobs/{started['job_id']}")["status"] == "done"
    rows = [
        {"activity": a, "element_id": d.ids[s], "status": "confirmed"} for a, s in EXPECTED.items()
    ]
    rows.append({"activity": "Manual weight override", "element_id": None, "status": "hidden_work"})
    rows += [
        {"activity": "", "element_id": d.ids[s], "status": "no_system_record"} for s in UNRECORDED
    ]
    assert client.put(f"/api/event-logs/{lid}/alignment", json={"rows": rows}).status_code == 200
    analysis = client.post(f"/api/versions/{d.version_id}/gap-analyses/internal").json()
    wait_for_jobs(client)
    report = get(f"/api/gap-analyses/{analysis['analysis_id']}")
    baseline = {
        "column_map": log["column_map"],
        "validation_report": log["validation_report"],
        "metrics": {scope: get(f"/api/event-logs/{lid}/metrics", scope=scope) for scope in SCOPES},
        "alignment": get(f"/api/event-logs/{lid}/alignment"),
        "system_findings": [f for f in report["findings"] if f["finding_type"] in SYSTEM_TYPES],
        "dispositions": get(f"/api/versions/{d.version_id}/dispositions"),
        "value": {
            view: get(f"/api/versions/{d.version_id}/value", view=view)
            for view in ("done", "documented")
        },
    }
    text = str(baseline)
    assert not any(code in text for code in CODES)  # constraint 24: no user ID in the baseline
    matches_baseline("G10_system_records.json", _fixed_times(baseline))
