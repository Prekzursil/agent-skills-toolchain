#!/usr/bin/env python3
"""Probe 1: both-states control — warm first-command must be measurably faster.

Independent of probe 2 (scaling / O(n) characterization). Re-runs live
timing on a clean isolated profile and checks the receipt records the
same pass predicates (not byte-identical millisecond values).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0239.json"
UID = "TST-0239"
SENTINEL = "SUCCESS:TST-0239"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0239-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UID:
        return fail(f"unit_id {doc.get('unit_id')}")
    text = json.dumps(doc)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = S.measure_both_states()
    if not live.get("pass"):
        return fail(f"live both-states did not pass {json.dumps(live)}")

    rec = doc.get("both_states") or doc.get("measurements", {}).get("both_states") or {}
    if rec.get("pass") is not True:
        return fail("artifact both_states.pass is not true")
    if rec.get("warm_measurably_faster") is not True:
        return fail("artifact does not record warm faster than cold")
    if rec.get("cache_delete_restores_cold") is not True:
        return fail("artifact missing cache-delete detector")
    if rec.get("two_warms_do_not_distinguish") is not True:
        return fail("artifact missing two-warm negative control")
    if rec.get("under_ceiling") is not True:
        return fail("artifact cold not under ceiling")
    if int(rec.get("n") or 0) != int(live.get("n") or -1):
        return fail(f"n drift artifact={rec.get('n')} live={live.get('n')}")

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-both-states",
                "unit_id": UID,
                "n": live["n"],
                "cold_median_ms": live["cold_median_ms"],
                "warm_median_ms": live["warm_median_ms"],
                "cold_over_warm": live["cold_over_warm"],
                "cache_delete_restores_cold": live["cache_delete_restores_cold"],
                "two_warms_do_not_distinguish": live["two_warms_do_not_distinguish"],
                "under_ceiling": live["under_ceiling"],
            },
            sort_keys=True,
        )
    )
    print(
        f"cold={live['cold_median_ms']}ms warm={live['warm_median_ms']}ms "
        f"speedup={live['cold_over_warm']} n={live['n']}"
    )
    print("SUCCESS:TST-0239-probe1 both-states warm-faster and cache-delete control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
