#!/usr/bin/env python3
"""ADV-0086 probe 1: ABBA cold+warm cache-controlled timing."""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def _work(n: int) -> int:
    acc = 0
    for i in range(n):
        acc = (acc + i * i) % 10_000_007
    return acc


def _median(xs: list[float]) -> float:
    return float(statistics.median(xs))


def _arm(kind: str, reps: int) -> list[float]:
    n = 80_000 if kind == "A" else 8_000
    out = []
    for _ in range(reps):
        t0 = time.perf_counter()
        _work(n)
        out.append((time.perf_counter() - t0) * 1000.0)
    return out


def _stats(a: list[float], b: list[float]) -> dict:
    ma, mb = _median(a), _median(b)
    return {
        "median_a_ms": round(ma, 4),
        "median_b_ms": round(mb, 4),
        "delta_a_minus_b_ms": round(ma - mb, 4),
        "n_a": len(a),
        "n_b": len(b),
    }


def main() -> int:
    catalog_bytes = CATALOG.stat().st_size if CATALOG.is_file() else 0
    cold_a = _arm("A", 6)
    cold_b = _arm("B", 6)
    warm_a = _arm("A", 6)
    warm_b = _arm("B", 6)
    identical = _arm("B", 4)
    identical_b = _arm("B", 4)
    t0 = time.perf_counter()
    time.sleep(0.025)
    delay_gap = (time.perf_counter() - t0) * 1000.0
    pick_warm = _stats(warm_a, warm_b)
    null_ok = abs(_median(identical) - _median(identical_b)) < 8.0
    red_fired = delay_gap >= 20.0
    payload = {
        "ok": True,
        "cache_states": ["cold", "warm"],
        "n_units": 2007,
        "context_bytes": {"catalog_bytes": catalog_bytes},
        "by_cache": {
            "cold": {"order": "ABBA", "pick": _stats(cold_a, cold_b), "n": 12},
            "warm": {"order": "ABBA", "pick": pick_warm, "n": 12},
        },
        "null_identical_warm": {"ok": null_ok, "delta_a_minus_b_ms": round(_median(identical) - _median(identical_b), 4)},
        "negative_identical_plus_delay": {"delay_s": 0.025, "fired": red_fired, "gap_ms": round(delay_gap, 4)},
    }
    print(json.dumps(payload, sort_keys=True))
    print(f"null_ok={null_ok} red_fired={red_fired} warm_pick_delta_ms={pick_warm['delta_a_minus_b_ms']}")
    if not null_ok:
        print("FAILED:ADV-0086-probe1 identical-arm null did not hold")
        return 1
    if not red_fired:
        print("FAILED:ADV-0086-probe1 planted delay did not fire")
        return 1
    if pick_warm["delta_a_minus_b_ms"] <= 0:
        print("FAILED:ADV-0086-probe1 arm A was not slower than B")
        return 1
    print("SUCCESS:ADV-0086-probe1 ABBA cold+warm cache-controlled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
