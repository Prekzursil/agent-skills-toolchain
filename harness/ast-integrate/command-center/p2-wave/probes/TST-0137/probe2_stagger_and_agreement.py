#!/usr/bin/env python3
"""Probe 2: stagger ON stays under the ceiling; two signals agree within 1%.

When the catalog receipt exists, independently re-bin the published dispatch
timestamps and check they match the live run (same seed, deterministic).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    CEILING_PER_SEC,
    N_UNITS,
    RECEIPT,
    compact,
    meter_from_dispatch,
    release,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0137-probe2 {msg}")
    return 1


def main() -> int:
    result = release(stagger=True)
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
        return fail(
            f"signals disagree rel={agree['relative_error']} "
            f"dispatch={agree['dispatch_n']} server={agree['server_n']}"
        )
    if meter["breach"]:
        return fail(f"stagger-on reported breach peak_per_1s={peak}")
    if peak > CEILING_PER_SEC:
        return fail(f"peak_per_1s={peak} exceeds ceiling={CEILING_PER_SEC}")
    if result["unique_dispatch_timestamps"] < N_UNITS:
        return fail("stagger produced colliding dispatch timestamps")
    if meter["source"] != "dispatch_timestamps_binned_1s":
        return fail("rate was not taken from dispatch timestamps")

    published_ok = None
    if RECEIPT.is_file():
        rec = json.loads(RECEIPT.read_text(encoding="utf-8"))
        published = rec.get("measurements") or {}
        stag = published.get("stagger_enabled") or {}
        ticks = [int(t) for t in (stag.get("dispatch_times_ticks") or [])]
        if len(ticks) != N_UNITS:
            return fail(f"receipt dispatch ticks n={len(ticks)} want={N_UNITS}")
        recomputed = meter_from_dispatch(ticks, CEILING_PER_SEC)
        if recomputed["peak_per_1s"] != stag.get("peak_per_1s"):
            return fail("receipt peak_per_1s does not match re-binned timestamps")
        if recomputed["peak_per_1s"] != peak:
            return fail(
                f"receipt re-bin peak={recomputed['peak_per_1s']} live peak={peak}"
            )
        if recomputed["breach"] is True:
            return fail("receipt timestamps re-bin as a breach")
        server_n = int(stag.get("server_arrival_count") or -1)
        if server_n != N_UNITS:
            return fail(f"receipt server_n={server_n} want={N_UNITS}")
        published_ok = True

    payload = {
        "pass": True,
        "probe": "probe2-stagger-and-agreement",
        "unit_id": "TST-0137",
        "published_timestamps_rebinned": published_ok,
        **compact(result),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:TST-0137-probe2 stagger-on silent "
        f"peak_per_1s={peak}<={CEILING_PER_SEC} "
        f"dispatch_n={agree['dispatch_n']} server_n={agree['server_n']} "
        f"rel={agree['relative_error']} published_ok={published_ok}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
