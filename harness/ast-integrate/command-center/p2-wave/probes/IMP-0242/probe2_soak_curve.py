#!/usr/bin/env python3
"""Probe 2: concurrency-load-soak resource curve and planted leak.

Duration is a declared integer (ms), not an adjective. The resource curve is
a list of retained_bytes samples. A planted retainer is flagged; a stable
workload is not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
sys.path.insert(0, str(LIB))

from eng_blueprints_17_21.soak import (  # noqa: E402
    PerRunSoakTuneError,
    LeakyWorkload,
    StableWorkload,
    load_soak_spec,
    run_soak,
)

RAW = HERE / "probe2-soak.raw.json"


def main() -> int:
    spec = load_soak_spec()
    if not isinstance(spec["duration_ms"], int) or spec["duration_ms"] < 30:
        print("FAILED:IMP-0242-probe2 duration not a declared integer", spec)
        return 1

    leaky = run_soak(LeakyWorkload())
    honest = run_soak(StableWorkload())

    if leaky["verdict"] != "LEAK" or leaky["leak_detected"] is not True:
        print("FAILED:IMP-0242-probe2 planted leak not detected", json.dumps(leaky))
        return 1
    if honest["verdict"] != "NO-LEAK" or honest["leak_detected"] is not False:
        print("FAILED:IMP-0242-probe2 stable workload flagged", json.dumps(honest))
        return 1
    if leaky["adjective_verdict"] is not None or honest["adjective_verdict"] is not None:
        print("FAILED:IMP-0242-probe2 adjective verdict leaked")
        return 1
    if not isinstance(leaky["duration_declared_ms"], int):
        print("FAILED:IMP-0242-probe2 duration_declared_ms is not data")
        return 1
    curve = leaky.get("curve") or []
    if len(curve) < int(spec["min_samples"]):
        print("FAILED:IMP-0242-probe2 curve too short", leaky["sample_count"])
        return 1
    if not all(isinstance(pt.get("retained_bytes"), int) for pt in curve):
        print("FAILED:IMP-0242-probe2 curve is not numeric retained_bytes")
        return 1
    if not (leaky["leak_growth_bytes"] > leaky["leak_threshold_bytes"]):
        print("FAILED:IMP-0242-probe2 leak growth not above threshold", leaky)
        return 1
    if not (honest["leak_growth_bytes"] <= honest["leak_threshold_bytes"]):
        print("FAILED:IMP-0242-probe2 stable growth above threshold", honest)
        return 1

    refused = False
    try:
        load_soak_spec(spec_override={"duration_ms": 5})
    except PerRunSoakTuneError:
        refused = True
    if not refused:
        print("FAILED:IMP-0242-probe2 per-run soak spec override accepted")
        return 1

    doc = {
        "both_states": True,
        "duration_declared_ms": leaky["duration_declared_ms"],
        "duration_observed_ms": leaky["duration_observed_ms"],
        "honest_leak_detected": False,
        "honest_growth_bytes": honest["leak_growth_bytes"],
        "leaky_growth_bytes": leaky["leak_growth_bytes"],
        "leaky_leak_detected": True,
        "override_refused": True,
        "pass": True,
        "sample_count": leaky["sample_count"],
        "spec_id": spec["id"],
        "threshold_bytes": leaky["leak_threshold_bytes"],
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"leaky_leak_detected=True honest_leak_detected=False "
        f"duration_declared_ms={leaky['duration_declared_ms']} "
        f"leaky_growth_bytes={leaky['leak_growth_bytes']} "
        f"sample_count={leaky['sample_count']}"
    )
    print("SUCCESS:IMP-0242-probe2 soak curve recorded; planted leak detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
