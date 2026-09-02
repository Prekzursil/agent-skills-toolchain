#!/usr/bin/env python3
"""Probe 1: detector control — stagger OFF must report a ceiling breach.

A meter that cannot see a 256-at-t=0 burst is not measuring arrival rate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import CEILING_PER_SEC, N_UNITS, compact, release  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0137-probe1 {msg}")
    return 1


def main() -> int:
    result = release(stagger=False)
    meter = result["meter"]
    agree = result["agreement"]
    peak = meter["peak_per_1s"]
    if result["n_units"] != N_UNITS:
        return fail(f"n_units={result['n_units']} want={N_UNITS}")
    if meter["n_dispatch"] != N_UNITS:
        return fail(f"dispatch_n={meter['n_dispatch']} want={N_UNITS}")
    if result["server_arrival_count"] != N_UNITS:
        return fail(f"server_n={result['server_arrival_count']} want={N_UNITS}")
    if not agree["agree"]:
        return fail(f"count disagreement rel={agree['relative_error']}")
    if peak <= CEILING_PER_SEC:
        return fail(
            f"detector silent on burst: peak_per_1s={peak} ceiling={CEILING_PER_SEC}"
        )
    if not meter["breach"]:
        return fail("meter.breach is false on stagger-disabled burst")
    if peak != N_UNITS:
        return fail(f"burst peak_per_1s={peak} want={N_UNITS} (all at t=0)")
    if meter["source"] != "dispatch_timestamps_binned_1s":
        return fail("rate was not taken from dispatch timestamps")
    if peak == CEILING_PER_SEC and N_UNITS != CEILING_PER_SEC:
        return fail("measured peak equals config ceiling — read-back, not a meter")

    payload = {
        "pass": True,
        "probe": "probe1-detector-control",
        "unit_id": "TST-0137",
        **compact(result),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:TST-0137-probe1 detector control: stagger-off "
        f"peak_per_1s={peak} > ceiling={CEILING_PER_SEC} (n={N_UNITS})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
