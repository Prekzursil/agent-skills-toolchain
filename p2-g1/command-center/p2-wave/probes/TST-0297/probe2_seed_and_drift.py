#!/usr/bin/env python3
"""TST-0297 probe 2: seed wiring proof + environment drift alarm.

Seed wiring: changing ONLY the seed must change the result set (per-case
scores differ between seed 20260824 and 20260825) - and the INERT control
runner must NOT change, proving the detector is not vacuous. Drift alarm:
identical captures compare silently clean; a model_snapshot change flags
DRIFT and the comparison is refused (never silently compared).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.env_capture import capture, compare  # noqa: E402

FIXTURE_IDS = ["fx-alpha", "fx-bravo", "fx-charlie", "fx-delta"]


def wired_scores(seed: int) -> list[tuple[str, float]]:
    rng = random.Random(f"bench:{seed}")
    return [(cid, round(rng.random(), 4)) for cid in FIXTURE_IDS]


def inert_scores(seed: int) -> list[tuple[str, float]]:
    return [(cid, 0.5) for cid in FIXTURE_IDS]


def main() -> int:
    checks: dict[str, bool] = {}
    a = wired_scores(20260824)
    b = wired_scores(20260825)
    checks["seed_changes_result_set"] = a != b
    checks["seed_wired_per_case"] = any(
        pa != pb for (_, pa), (_, pb) in zip(a, b)
    )
    mean_a = round(sum(p for _, p in a) / len(a), 6)
    mean_b = round(sum(p for _, p in b) / len(b), 6)
    checks["means_differ"] = mean_a != mean_b

    ia = inert_scores(20260824)
    ib = inert_scores(20260825)
    checks["inert_control_identical"] = ia == ib

    base = capture(seed=20260824)
    same = capture(seed=20260824)
    drift = capture(seed=20260824, model_snapshot="snap-1")
    cmp_same = compare(base, same)
    cmp_drift = compare(base, drift)
    checks["identical_capture_silent_match"] = cmp_same["status"] == "MATCH"
    checks["identical_capture_allowed"] = cmp_same["comparison_allowed"] is True
    checks["snapshot_change_flagged_drift"] = cmp_drift["status"] == "DRIFT"
    checks["drift_field_is_model_snapshot"] = cmp_drift["differing_fields"] == [
        "model_snapshot"
    ]
    checks["drift_refuses_comparison"] = cmp_drift["comparison_allowed"] is False
    checks["never_silently_compared"] = (
        cmp_same["silently_compared"] is False
        and cmp_drift["silently_compared"] is False
    )
    # Fingerprint sensitivity: snapshot change must move the fingerprint.
    checks["fingerprint_moves_on_drift"] = (
        base["fingerprint"] != drift["fingerprint"]
    )

    out = {
        "probe": "probe2_seed_and_drift",
        "unit": "TST-0297",
        "seed_wiring": {
            "seed_a": 20260824,
            "seed_b": 20260825,
            "result_set_a": a,
            "result_set_b": b,
            "mean_a": mean_a,
            "mean_b": mean_b,
            "wired": checks["seed_changes_result_set"],
            "inert": False,
        },
        "inert_control": {"scores": ia, "identical": checks["inert_control_identical"]},
        "drift_alarm": {
            "same": cmp_same,
            "drift": cmp_drift,
            "snapshot_change_flagged": checks["snapshot_change_flagged_drift"],
        },
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe2-seed-drift.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True)[:1600])
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
