"""Fixture A.11 (PRD Appendix A.11): a departure-control system log of the load-control process.

Run `python tests/fixtures/system/generate_log.py` from `backend/` to rewrite `dcs_log.csv`; the
fixed seed makes the file identical on every run (it drives G10). Fictional throughout: the
resource codes are made up and map to roles only through `role_map.json`.

- 200 cases (flights) over 8 weeks, 25 a week, Monday 2 March 2026 onwards, local time.
- Plan created → Special load checked → Loading report received → Weight deviation checked →
  Load sheet issued; Plan revised in about 18% of cases (after Special load checked); Manual
  weight override in about 12% (before Load sheet issued); no Plan approved event, ever.
- Loading report received runs from loading completion to the report's arrival: median about
  14 minutes, 90th percentile about 25.
"""

from __future__ import annotations

import csv
import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 11
CASES = 200
START = datetime(2026, 3, 2, 6, 0)
FORMAT = "%Y-%m-%d %H:%M:%S"
CONTROLLERS = ["LC07", "LC12", "LC19", "LC23"]
RAMP = ["RP31", "RP44", "RP52"]
ROLE_MAP = {**{code: "Load controller" for code in CONTROLLERS},
            **{code: "Ramp" for code in RAMP}}  # fmt: skip


def lognormal(rng: random.Random, median: float, p90: float) -> float:
    """Minutes drawn so that the median and the 90th percentile are about as given."""
    sigma = math.log(p90 / median) / 1.2816
    return median * math.exp(rng.gauss(0, sigma))


def rows() -> list[dict[str, str]]:
    rng = random.Random(SEED)
    out: list[dict[str, str]] = []
    for n in range(CASES):
        flight = f"FL{1000 + n}"
        day = START + timedelta(days=(n // 25) * 7 + (n % 25) % 5, hours=(n % 25) // 5 * 2)
        controller, ramp = rng.choice(CONTROLLERS), rng.choice(RAMP)
        t = day + timedelta(minutes=rng.randint(0, 50))

        def event(
            activity: str, minutes: float, who: str, gap: float = 3.0, case: str = flight
        ) -> None:
            nonlocal t
            start = t + timedelta(minutes=gap)
            end = start + timedelta(minutes=minutes)
            out.append({"case_id": case, "activity": activity,
                        "timestamp": start.strftime(FORMAT), "end_timestamp": end.strftime(FORMAT),
                        "resource": who, "system": "DCS"})  # fmt: skip
            t = end

        event("Plan created", lognormal(rng, 20, 28), controller, gap=0)
        event("Special load checked", lognormal(rng, 6, 10), controller)
        if rng.random() < 0.18:
            event("Plan revised", lognormal(rng, 15, 30), controller)
        loading = lognormal(rng, 40, 50)  # loading itself is not recorded in the system
        event("Loading report received", lognormal(rng, 14, 25), ramp, gap=loading)
        event("Weight deviation checked", lognormal(rng, 4, 7), controller)
        if rng.random() < 0.12:
            event("Manual weight override", lognormal(rng, 5, 9), controller)
        event("Load sheet issued", lognormal(rng, 3, 5), controller)
    return out


def main() -> None:
    with (HERE / "dcs_log.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "activity", "timestamp",
                                               "end_timestamp", "resource", "system"])  # fmt: skip
        writer.writeheader()
        writer.writerows(rows())
    (HERE / "role_map.json").write_text(json.dumps(ROLE_MAP, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
