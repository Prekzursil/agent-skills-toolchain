#!/usr/bin/env python3
"""Probe 2: exhaustive/symbolic bound + unjittered negative control (signal b).

Mechanically different from probe 1:
  * no 50-run sampling of the live jittered function for the PASS
  * cartesian property test over supported (base, cap, attempts, timeout)
  * symbolic clip proof that worst-case sum stays below timeout
  * negative control: a fixed-interval (unjittered) implementation MUST fail
    the non-determinism assertion that probe 1 uses
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import backoff as B  # noqa: E402

ART = REPO / "command-center/receipts/TST-0138.json"
DETERMINISM_SEEDS = (1, 1)  # same seed, same call shape — jittered would still
# differ across SystemRandom, but unjittered ignores rng entirely.


def check_artifact() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "catalog output_path missing or empty"
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0138" not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if str(report.get("kind") or "") != "scheduler_report":
        return "report.kind is not scheduler_report"
    return None


def property_grid() -> list[dict]:
    rows = []
    for base in B.SUPPORTED_BASES:
        for cap in B.SUPPORTED_CAPS:
            if cap < base:
                continue
            for attempts in B.SUPPORTED_ATTEMPTS:
                for timeout in B.SUPPORTED_TIMEOUTS:
                    rows.append(
                        {
                            "base": base,
                            "cap": cap,
                            "max_attempts": attempts,
                            "timeout_seconds": timeout,
                        }
                    )
    return rows


def non_determinism_assertion(a: list[float], b: list[float]) -> bool:
    """The assertion probe 1 requires of two live runs."""
    return a != b


def main() -> int:
    art_err = check_artifact()
    if art_err:
        print(f"FAILED:TST-0138-probe2 {art_err}")
        return 1

    grid = property_grid()
    if len(grid) < 100:
        print(f"FAILED:TST-0138-probe2 property grid too small ({len(grid)})")
        return 1

    bound_failures = []
    sample_failures = []
    clipping_cases = 0
    rng = random.Random(20260824)
    for spec in grid:
        proof = B.symbolic_bound_holds(
            spec["max_attempts"], spec["base"], spec["cap"], spec["timeout_seconds"]
        )
        if not proof["bound_holds"]:
            bound_failures.append({"spec": spec, "proof": proof})
            continue
        if proof["clipping_load_bearing"]:
            clipping_cases += 1
        for _ in range(3):
            sched = B.retry_schedule(rng=rng, **spec)
            if not B.bound_holds(sched, spec["timeout_seconds"]):
                sample_failures.append({"spec": spec, "schedule": sched})
                break
            if B.schedule_sum(sched) > proof["clipped_worst_case"] + 1e-6:
                sample_failures.append(
                    {
                        "spec": spec,
                        "schedule": sched,
                        "why": "sample exceeded symbolic clipped worst case",
                    }
                )
                break
    if bound_failures:
        print("FAILED:TST-0138-probe2 symbolic bound failed")
        print(json.dumps(bound_failures[:5], sort_keys=True))
        return 1
    if sample_failures:
        print("FAILED:TST-0138-probe2 sampled schedule exceeded timeout or proof")
        print(json.dumps(sample_failures[:5], sort_keys=True))
        return 1
    if clipping_cases < 1:
        print("FAILED:TST-0138-probe2 no grid cell makes unclipped worst-case exceed timeout")
        return 1

    # Negative control: unjittered schedules from two "runs" are identical, so
    # the non-determinism assertion fails. A detector that cannot see this is
    # itself broken.
    ctrl_spec = dict(
        max_attempts=B.CATALOG_ATTEMPTS,
        base=B.CATALOG_BASE,
        cap=B.CATALOG_CAP,
        timeout_seconds=B.CATALOG_TIMEOUT,
    )
    u1 = B.unjittered_schedule(rng=random.Random(DETERMINISM_SEEDS[0]), **ctrl_spec)
    u2 = B.unjittered_schedule(rng=random.Random(DETERMINISM_SEEDS[1]), **ctrl_spec)
    if u1 != u2:
        print("FAILED:TST-0138-probe2 unjittered control was non-deterministic")
        print(json.dumps({"u1": u1, "u2": u2}))
        return 1
    if non_determinism_assertion(u1, u2):
        print("FAILED:TST-0138-probe2 non-determinism assertion passed on unjittered")
        return 1
    unjittered_fails_nondeterminism = not non_determinism_assertion(u1, u2)
    if not unjittered_fails_nondeterminism:
        print("FAILED:TST-0138-probe2 control did not fail the assertion")
        return 1
    if len(u1) != B.CATALOG_ATTEMPTS - 1:
        print("FAILED:TST-0138-probe2 unjittered catalog length")
        return 1
    expected_unjittered = [
        B.attempt_ceiling(0, B.CATALOG_BASE, B.CATALOG_CAP),
        B.attempt_ceiling(1, B.CATALOG_BASE, B.CATALOG_CAP),
    ]
    if u1 != expected_unjittered:
        print("FAILED:TST-0138-probe2 unjittered catalog is not the exponential ceiling")
        print(json.dumps({"got": u1, "want": expected_unjittered}))
        return 1

    # Both-states: the LIVE jittered function, given two SystemRandom draws,
    # must still satisfy the same assertion the control fails.
    j1 = B.retry_schedule(**ctrl_spec)
    j2 = B.retry_schedule(**ctrl_spec)
    tries = 1
    while not non_determinism_assertion(j1, j2) and tries < 8:
        j2 = B.retry_schedule(**ctrl_spec)
        tries += 1
    if not non_determinism_assertion(j1, j2):
        print("FAILED:TST-0138-probe2 jittered function failed non-determinism assertion")
        return 1

    summary = {
        "grid_cells": len(grid),
        "symbolic_bound_failures": 0,
        "sampled_bound_failures": 0,
        "clipping_load_bearing_cells": clipping_cases,
        "unjittered_runs_identical": True,
        "unjittered_fails_nondeterminism_assertion": True,
        "jittered_passes_nondeterminism_assertion": True,
        "unjittered_catalog": u1,
        "pass": True,
        "probe": "probe2-property-and-unjittered-control",
        "unit_id": "TST-0138",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"grid={len(grid)} clipping_cells={clipping_cases} "
        f"unjittered_fails_nondeterminism=True jittered_differs=True"
    )
    print("SUCCESS:TST-0138-probe2 property bound and unjittered negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
