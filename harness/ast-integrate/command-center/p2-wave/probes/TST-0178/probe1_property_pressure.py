#!/usr/bin/env python3
"""Named probe 1: randomized pressure with concurrent holders, pinning ON.

Signal (a): eviction log cross-referenced against the pin table at each eviction.
Signal (b): holder re-read outcomes after the pressure dump.
PASS: zero pinned evictions and zero holder misses, with real (non-vacuous) eviction.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import run_property_suite  # noqa: E402

ART = REPO / "command-center/receipts/TST-0178.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0178-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "TST-0178":
        print("FAILED:TST-0178-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0178" not in text:
        print("FAILED:TST-0178-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0178-probe1 self-declared", doc.get("state"))
        return 1

    live = run_property_suite()
    if not live.get("ok"):
        print("FAILED:TST-0178-probe1 property does not hold")
        print(json.dumps({k: live[k] for k in ("fail_count", "vacuous_count", "fails", "vacuous")}, indent=2)[:4000])
        return 1
    if live["total_evictions"] <= 0:
        print("FAILED:TST-0178-probe1 vacuous: no evictions")
        return 1
    if live["total_pinned_conflicts"] != 0:
        print("FAILED:TST-0178-probe1 pin-table/eviction-log conflict")
        return 1
    if live["total_reader_misses"] != 0:
        print("FAILED:TST-0178-probe1 holder miss while pinned")
        return 1

    recorded = doc.get("property_suite") or {}
    if not recorded.get("ok"):
        print("FAILED:TST-0178-probe1 artifact property_suite not ok")
        return 1
    if int(recorded.get("total_pinned_conflicts", -1)) != 0:
        print("FAILED:TST-0178-probe1 artifact recorded pin conflicts")
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-property-pressure",
        "unit_id": "TST-0178",
        "n_trials": live["n_trials"],
        "total_evictions": live["total_evictions"],
        "total_pinned_conflicts": live["total_pinned_conflicts"],
        "total_reader_misses": live["total_reader_misses"],
        "vacuous_count": live["vacuous_count"],
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"trials={live['n_trials']} evictions={live['total_evictions']} "
        f"pinned_conflicts=0 reader_misses=0 pressure_real=True"
    )
    print("SUCCESS:TST-0178-probe1 randomized pressure no pinned eviction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
