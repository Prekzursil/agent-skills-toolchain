#!/usr/bin/env python3
"""Named probe 1: synthetic 429 storm accounting sums to 100%.

Both-states: naive drop-on-429 loses units. Quota-aware admission, feeding
measured remaining and observed arrival rate back into the scheduler, emits a
typed terminal record for every submitted unit (completed + rate-limited).
Throughput degrades versus a healthy rail (virtual elapsed is larger).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _lib import N_STORM, load_receipt, run_accounting_pair  # noqa: E402


def main() -> int:
    load_receipt()
    units, healthy, storm, naive = run_accounting_pair()
    n = N_STORM

    if storm.lost != 0 or storm.accounted != n or storm.accounting_pct != 100.0:
        print("FAILED:IMP-0221-probe1 storm accounting is not 100%")
        print(json.dumps(storm.as_dict(), indent=2))
        return 1
    if storm.submitted != n:
        print("FAILED:IMP-0221-probe1 submitted mismatch")
        return 1
    if storm.completed + storm.rate_limited + storm.overload + storm.error != n:
        print("FAILED:IMP-0221-probe1 completed+typed != submitted")
        return 1
    if naive.lost <= 0:
        print("FAILED:IMP-0221-probe1 naive control did not lose units")
        print(json.dumps(naive.as_dict(), indent=2))
        return 1
    if naive.completed + naive.lost != n:
        print("FAILED:IMP-0221-probe1 naive submitted split broken")
        return 1
    if healthy.lost != 0 or healthy.completed != n:
        print("FAILED:IMP-0221-probe1 healthy rail lost work")
        return 1
    if not (storm.virtual_elapsed_s > healthy.virtual_elapsed_s):
        print("FAILED:IMP-0221-probe1 storm did not degrade throughput")
        print(storm.virtual_elapsed_s, healthy.virtual_elapsed_s)
        return 1
    if not storm.concurrency_unchanged:
        print("FAILED:IMP-0221-probe1 storm reduced max_concurrency")
        return 1
    seen = {r.unit_id for r in storm.records}
    missing = [uid for uid in units if uid not in seen]
    if missing:
        print("FAILED:IMP-0221-probe1 missing terminal records", missing)
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-accounting",
        "unit_id": "IMP-0221",
        "storm": storm.as_dict(),
        "naive": naive.as_dict(),
        "healthy": healthy.as_dict(),
        "naive_lost": naive.lost,
        "storm_lost": storm.lost,
        "throughput_degraded": storm.virtual_elapsed_s > healthy.virtual_elapsed_s,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "SUCCESS:IMP-0221-probe1 synthetic 429 storm accounting "
        f"{storm.accounted}/{n} naive_lost={naive.lost}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
