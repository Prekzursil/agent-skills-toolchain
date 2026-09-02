#!/usr/bin/env python3
"""Probe 1: 40-unit mixed dry run + per-substrate isolation.

Live dispatcher over ten catalog units from each of the four substrates.
local-serialized must stay flat at one. The other three substrates must
peak above one, so the readout is measured concurrency, not a constant.
A mutant that ignores declared substrate must fail isolation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dispatcher import (  # noqa: E402
    FOUR_SUBSTRATES,
    DispatchOpts,
    compact_series,
    dispatch,
    isolation_per_substrate,
    mixed_dry_run_units,
    summary,
)


def main() -> int:
    units = mixed_dry_run_units(n_per_substrate=10, duration_ticks=8)
    by_sub: dict[str, int] = {s: 0 for s in FOUR_SUBSTRATES}
    for u in units:
        by_sub[u.execution_substrate] += 1
    errors: list[str] = []
    if len(units) != 40:
        errors.append(f"unit-count:{len(units)}")
    if any(by_sub[s] != 10 for s in FOUR_SUBSTRATES):
        errors.append(f"mix:{by_sub}")

    locked = dispatch(units, DispatchOpts(serial_lock=True, honor_declared_substrate=True))
    iso = isolation_per_substrate(locked)
    if not locked.isolation_ok():
        errors.append(f"isolation-violations:{locked.isolation_violations}")
    for sub, row in iso.items():
        if not row["isolated"]:
            errors.append(f"isolation-{sub}:{row}")
    if not locked.serial_flat_at_one():
        errors.append(
            f"serial-not-flat-at-one peak={locked.peak('local-serialized')} "
            f"series={locked.concurrent_series('local-serialized')}"
        )
    if locked.peak("local-serialized") != 1:
        errors.append(f"serial-peak:{locked.peak('local-serialized')}")
    for sub in ("local-parallel", "worktree-isolated", "cloud-batch"):
        if locked.peak(sub) <= 1:
            errors.append(f"{sub}-not-parallel peak={locked.peak(sub)}")
    if locked.worktree_slot_collisions != 0:
        errors.append(f"worktree-slot-collisions:{locked.worktree_slot_collisions}")
    if len(locked.completed_ids) != 40:
        errors.append(f"incomplete:{len(locked.completed_ids)}")

    dumped = dispatch(
        units,
        DispatchOpts(serial_lock=True, honor_declared_substrate=False),
    )
    if dumped.isolation_ok():
        errors.append("isolation-mutant-stayed-green")
    if not dumped.isolation_violations:
        errors.append("isolation-mutant-no-violations")
    dumped_iso = isolation_per_substrate(dumped)
    if dumped_iso["local-parallel"]["isolated"]:
        errors.append("isolation-mutant-local-parallel-still-isolated")

    payload = {
        "probe": "probe1-mixed-dry-run",
        "unit_id": "IMP-0442",
        "unit_count": len(units),
        "per_substrate": by_sub,
        "locked": {
            "peaks": dict(locked.peaks),
            "serial_flat_at_one": locked.serial_flat_at_one(),
            "isolation_ok": locked.isolation_ok(),
            "isolation_per_substrate": iso,
            "worktree_slot_collisions": locked.worktree_slot_collisions,
            "ticks": locked.ticks,
            "compact_series": compact_series(locked),
        },
        "isolation_mutant": {
            "honor_declared_substrate": False,
            "isolation_ok": dumped.isolation_ok(),
            "violation_count": len(dumped.isolation_violations),
            "peaks": dict(dumped.peaks),
            "isolation_per_substrate": dumped_iso,
        },
        "errors": errors,
        "pass": not errors,
    }
    print(json.dumps(payload, sort_keys=True))
    if errors:
        print("FAILED:IMP-0442-probe1", ",".join(errors))
        return 1
    print(
        "peaks="
        + json.dumps(locked.peaks, sort_keys=True)
        + f" serial_flat_at_one=True isolation_ok=True mutant_violations={len(dumped.isolation_violations)}"
    )
    print("SUCCESS:IMP-0442-probe1 mixed-dry-run serial-flat-at-one isolation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
