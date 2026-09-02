#!/usr/bin/env python3
"""Probe 2: race amplification (100 trials, randomized start skew).

Independent of probe 1. Every trial must yield exactly one EXECUTED, one
DUPLICATE-SUPPRESSED, and one on-disk receipt. Flake > 1-in-20 is a DEFECT.
Mutation: dropping O_EXCL (check-then-act) must produce a double grant.
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import work_claim as wc  # noqa: E402

UID = "TST-0157"
TRIALS = 100
MAX_SKEW_S = 0.015


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def mutation_double_grant(root: Path) -> dict:
    """TOCTOU acquire must admit two EXECUTED (detector is not vacuous)."""
    last = None
    for i in range(12):
        trial = root / f"mut-{i}"
        results = wc.concurrent_pair(
            trial,
            "UNIT-MUT",
            "UNIT-MUT",
            f"mut-a-{i}",
            f"mut-b-{i}",
            skew_a=0.0,
            skew_b=0.0,
            atomic=False,
            race_window_s=0.05,
        )
        executed = [r for r in results if r.get("status") == wc.EXECUTED]
        last = {
            "attempt": i,
            "executed": len(executed),
            "statuses": [r.get("status") for r in results],
            "executions_on_disk": wc.count_executions(trial, "UNIT-MUT"),
        }
        if len(executed) >= 2 and last["executions_on_disk"] >= 2:
            last["double_grant"] = True
            return last
    last = last or {}
    last["double_grant"] = False
    return last


def main() -> int:
    rng = random.Random(1570157)
    failures = []
    with tempfile.TemporaryDirectory(prefix="tst0157-p2-") as tmp:
        root = Path(tmp)
        for i in range(TRIALS):
            trial = root / f"race-{i:03d}"
            skew_a = rng.uniform(0.0, MAX_SKEW_S)
            skew_b = rng.uniform(0.0, MAX_SKEW_S)
            results = wc.concurrent_pair(
                trial,
                "UNIT-RACE",
                "UNIT-RACE",
                f"racer-a-{i}",
                f"racer-b-{i}",
                skew_a=skew_a,
                skew_b=skew_b,
            )
            check = wc.contested_ok(results, trial, "UNIT-RACE")
            if not check["ok"]:
                failures.append({"trial": i, "check": check, "skew": [skew_a, skew_b]})
                if len(failures) >= 3:
                    break
        mut = mutation_double_grant(root / "mutation")

    flake = len(failures) / TRIALS
    payload = {
        "probe": "probe2-race-amplification",
        "unit_id": UID,
        "trials": TRIALS,
        "failures": len(failures),
        "flake_rate": flake,
        "max_allowed_flake": 0.05,
        "mutation_double_grant": mut.get("double_grant"),
        "mutation": mut,
        "failure_samples": failures[:3],
        "pass": len(failures) == 0 and bool(mut.get("double_grant")),
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if failures:
        return fail(f"race failures={len(failures)} flake={flake:.3f} sample={failures[0]}")
    if flake > 0.05:
        return fail(f"flake {flake:.3f} exceeds 1-in-20")
    if not mut.get("double_grant"):
        return fail(f"mutation did not double-grant (vacuous detector) {mut}")
    print(
        f"trials={TRIALS} failures=0 flake=0.000 mutation_double_grant=True"
    )
    print(f"SUCCESS:{UID}-probe2 100-trial race + TOCTOU mutation control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
