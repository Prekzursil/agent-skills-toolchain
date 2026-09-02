#!/usr/bin/env python3
"""Probe 2: re-derive the variance band from raw_ns; same-seed reproduction stays inside it."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.OUT_REL
UNIT = H.UNIT


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if H.COMPLETION_SENTINEL not in json.dumps(doc):
        return fail("completion_sentinel absent")
    view = H.payload(doc)

    seed = int(view.get("seed"))
    frozen_fp = str(view.get("input_fingerprint") or "")
    live = H.capture(seed)
    if live["input_fingerprint"] != frozen_fp:
        return fail(
            f"same seed rebuilt different inputs frozen={frozen_fp} "
            f"live={live['input_fingerprint']}"
        )

    frozen = {b["id"]: b for b in (view.get("benchmarks") or []) if isinstance(b, dict)}
    live_map = {b["id"]: b for b in live["benchmarks"]}
    want = (
        "router_latency",
        "hook_overhead",
        "fanout_throughput",
        "suite_wall_clock",
    )
    rows = []
    for bid in want:
        fb = frozen.get(bid)
        lb = live_map.get(bid)
        if not fb or not lb:
            return fail(f"missing benchmark {bid}")
        arms = fb.get("arms") or []
        if not arms or not isinstance(arms[0], dict):
            return fail(f"{bid} missing required arms[]")
        raw = arms[0].get("raw_ns") or fb.get("raw_ns") or []
        if len(raw) < 11:
            return fail(f"{bid} raw_ns n={len(raw)}")
        arm_stats = arms[0].get("statistics") or {}
        if not arm_stats:
            return fail(f"{bid} arms[0] missing statistics")
        derived = H.summarize(raw)
        stored = fb.get("statistics") or {}
        for key in (
            "n",
            "median_ns",
            "iqr_ns",
            "mean_ns",
            "ci95_lo_ns",
            "ci95_hi_ns",
            "stdev_ns",
        ):
            if key == "n":
                if derived["n"] != stored["n"]:
                    return fail(f"{bid} n recomputed={derived['n']} stored={stored['n']}")
                continue
            if not H.close(float(derived[key]), float(stored[key])):
                return fail(
                    f"{bid} {key} recomputed={derived[key]} stored={stored[key]}"
                )
        band_derived = H.variance_band(derived)
        band_stored = fb.get("variance_band") or {}
        if band_stored.get("derived_from") != "raw_ns":
            return fail(f"{bid} band not derived from raw_ns")
        if not H.close(band_derived["lo_ns"], float(band_stored["lo_ns"])):
            return fail(f"{bid} band.lo mismatch")
        if not H.close(band_derived["hi_ns"], float(band_stored["hi_ns"])):
            return fail(f"{bid} band.hi mismatch")
        live_median = float(lb["statistics"]["median_ns"])
        inside = H.within_band(live_median, band_stored)
        if not inside:
            return fail(
                f"{bid} live median {live_median} outside declared band "
                f"[{band_stored['lo_ns']}, {band_stored['hi_ns']}]"
            )
        rows.append(
            {
                "id": bid,
                "frozen_median_ns": stored["median_ns"],
                "live_median_ns": live_median,
                "band_lo_ns": band_stored["lo_ns"],
                "band_hi_ns": band_stored["hi_ns"],
                "within_band": inside,
                "n_inputs": fb["n_inputs"],
            }
        )
        print(
            f"{bid} frozen_median_ns={stored['median_ns']} "
            f"live_median_ns={live_median} within_band={inside} "
            f"n_inputs={fb['n_inputs']}"
        )

    payload = {
        "probe": "probe2-variance-band",
        "unit_id": UNIT,
        "seed": seed,
        "input_fingerprint": frozen_fp,
        "same_seed_inputs": True,
        "rows": rows,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
    print(
        "SUCCESS:TST-0025-probe2 variance band re-derived from raw_ns; "
        "same-seed reproduction inside the declared band"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
