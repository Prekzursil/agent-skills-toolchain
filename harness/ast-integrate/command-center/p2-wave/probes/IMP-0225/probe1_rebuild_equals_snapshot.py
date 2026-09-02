#!/usr/bin/env python3
"""Probe 1: reconstructed state == pre-kill snapshot (field equality)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import scenario_kill_mid_run  # noqa: E402


def main() -> int:
    result = scenario_kill_mid_run()
    snap = result["snapshot"]
    rebuilt = result["rebuilt"]
    want_completed = ["U1"]
    want_inflight = ["U2", "U3"]
    want_open = ["U4"]
    fail = False
    reasons: list[str] = []

    if not result["equal"]:
        fail = True
        reasons.append(f"field diffs: {result['diffs']}")
    if snap.get("completed_ids") != want_completed:
        fail = True
        reasons.append(f"completed {snap.get('completed_ids')} != {want_completed}")
    if snap.get("in_flight_ids") != want_inflight:
        fail = True
        reasons.append(f"in_flight {snap.get('in_flight_ids')} != {want_inflight}")
    if snap.get("open_ids") != want_open:
        fail = True
        reasons.append(f"open {snap.get('open_ids')} != {want_open}")
    if snap.get("dispatch_count") != 3:
        fail = True
        reasons.append(f"dispatch_count {snap.get('dispatch_count')} != 3")
    if snap.get("harvest_count") != 1:
        fail = True
        reasons.append(f"harvest_count {snap.get('harvest_count')} != 1")
    if rebuilt.get("run_id") != snap.get("run_id"):
        fail = True
        reasons.append("run_id mismatch")
    if not result["negative_empty_diverges"]:
        fail = True
        reasons.append("empty ledger equalled snapshot (vacuous rebuild)")
    if not result["negative_truncated_still_equal"]:
        fail = True
        reasons.append("truncated tail changed rebuilt state (partial record was guessed)")

    payload = {
        "probe": "probe1-rebuild-equals-snapshot",
        "unit_id": "IMP-0225",
        "pass": not fail,
        "equal": result["equal"],
        "diffs": result["diffs"],
        "fields_compared": result["fields_compared"],
        "dispatch_count": snap.get("dispatch_count"),
        "harvest_count": snap.get("harvest_count"),
        "completed_ids": snap.get("completed_ids"),
        "in_flight_ids": snap.get("in_flight_ids"),
        "open_ids": snap.get("open_ids"),
        "negative_empty_diverges": result["negative_empty_diverges"],
        "negative_truncated_still_equal": result["negative_truncated_still_equal"],
        "reasons": reasons,
    }
    print(json.dumps(payload, sort_keys=True))
    if fail:
        print("FAILED:IMP-0225-probe1 reconstructed state != pre-kill snapshot")
        return 1
    print(
        "SUCCESS:IMP-0225-probe1 reconstructed state equals pre-kill snapshot "
        f"fields={len(result['fields_compared'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
