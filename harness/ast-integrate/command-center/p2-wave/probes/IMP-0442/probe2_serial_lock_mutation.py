#!/usr/bin/env python3
"""Probe 2: mutation that drops the serial lock must go red.

Same 40-unit mixed catalog as probe 1. With serial_lock=False the
local-serialized concurrent count must exceed one, and the same
flat-at-one predicate probe 1 uses must fail. The probe itself exits 0
only because that both-states control fired.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dispatcher import (  # noqa: E402
    DispatchOpts,
    compact_series,
    dispatch,
    mixed_dry_run_units,
)


def main() -> int:
    units = mixed_dry_run_units(n_per_substrate=10, duration_ticks=8)
    locked = dispatch(units, DispatchOpts(serial_lock=True))
    unlocked = dispatch(units, DispatchOpts(serial_lock=False))
    errors: list[str] = []

    if not locked.serial_flat_at_one():
        errors.append("locked-state-not-flat-at-one")
    if locked.peak("local-serialized") != 1:
        errors.append(f"locked-peak:{locked.peak('local-serialized')}")

    unlocked_peak = unlocked.peak("local-serialized")
    unlocked_flat = unlocked.serial_flat_at_one()
    unlocked_never = unlocked.serial_never_exceeds_one()
    if unlocked_peak <= 1:
        errors.append(
            f"mutation-did-not-raise-serial-peak peak={unlocked_peak}"
        )
    if unlocked_flat:
        errors.append("flat-at-one-stayed-true-without-lock")
    if unlocked_never:
        errors.append("never-exceeds-one-stayed-true-without-lock")
    if unlocked_peak < 2:
        errors.append("mutation-peak-not-above-one")

    # Same mix, same durations: without the lock all ten serialized units
    # start together, so peak must be the cohort size.
    if unlocked_peak != 10:
        errors.append(f"expected-serial-peak-10-got-{unlocked_peak}")

    payload = {
        "probe": "probe2-serial-lock-mutation",
        "unit_id": "IMP-0442",
        "locked": {
            "serial_lock": True,
            "peak_local_serialized": locked.peak("local-serialized"),
            "flat_at_one": locked.serial_flat_at_one(),
            "never_exceeds_one": locked.serial_never_exceeds_one(),
        },
        "unlocked": {
            "serial_lock": False,
            "peak_local_serialized": unlocked_peak,
            "flat_at_one": unlocked_flat,
            "never_exceeds_one": unlocked_never,
            "compact_series": compact_series(unlocked),
        },
        "predicate_turns_red_without_lock": (not unlocked_flat) and unlocked_peak > 1,
        "errors": errors,
        "pass": not errors,
    }
    print(json.dumps(payload, sort_keys=True))
    if errors:
        print("FAILED:IMP-0442-probe2", ",".join(errors))
        return 1
    print(
        f"locked_peak={locked.peak('local-serialized')} "
        f"unlocked_peak={unlocked_peak} "
        "flat_at_one_locked=True flat_at_one_unlocked=False"
    )
    print("SUCCESS:IMP-0442-probe2 serial-lock-mutation turns-red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
