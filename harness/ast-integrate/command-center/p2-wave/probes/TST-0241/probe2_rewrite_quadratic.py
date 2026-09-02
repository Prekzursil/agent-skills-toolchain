#!/usr/bin/env python3
"""Probe 2: O(n) rewrite mutant is quadratic; live append is not; bands re-derived."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = H.REPO / H.OUT_REL
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

    work = HERE / "_work"
    work.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="p2-", dir=str(work)))
    live_append = H.write_size_curve("append", scratch)
    live_rewrite = H.write_size_curve("rewrite", scratch)

    payload = H.receipt_report(doc)
    frozen_scale = payload.get("scaling") or {}
    frozen_dispatch = frozen_scale.get("dispatch") or []
    if not frozen_dispatch:
        return fail("receipt missing scaling.dispatch")
    live_clf = H.classify_curves(live_append, live_rewrite, frozen_dispatch)
    print(json.dumps({"live_classification": live_clf["verdicts"]}, sort_keys=True))
    if live_clf["verdicts"].get("rewrite_write_grows") is not True:
        return fail(f"rewrite write-size did not grow: {live_clf}")
    if live_clf["verdicts"].get("rewrite_cumulative_quadratic") is not True:
        return fail(f"rewrite cumulative is not quadratic: {live_clf}")
    if live_clf["verdicts"].get("append_write_o1") is not True:
        return fail(f"live append write-size is not O(1): {live_clf}")
    if live_clf["verdicts"].get("append_cumulative_linear") is not True:
        return fail(f"live append cumulative is not linear: {live_clf}")

    stored_clf = frozen_scale.get("classification") or {}
    stored_verdicts = stored_clf.get("verdicts") or stored_clf
    if stored_verdicts.get("rewrite_cumulative_quadratic") is not True:
        return fail("receipt did not record a quadratic rewrite curve")

    # Re-derive statistics and variance bands from raw_ns; recapture one arm.
    frozen_benches = {b["id"]: b for b in (payload.get("benchmarks") or [])}
    dispatch = frozen_benches.get("dispatch_per_unit")
    if not dispatch:
        return fail("dispatch_per_unit missing")
    arm2048 = next((a for a in dispatch["arms"] if a.get("id") == "n2048"), None)
    if not arm2048:
        return fail("n2048 dispatch arm missing")
    raw = arm2048.get("raw_ns") or []
    if len(raw) < 11:
        return fail(f"n2048 raw_ns n={len(raw)}")
    derived = H.summarize(raw)
    stored = arm2048.get("statistics") or {}
    for key in ("n", "median_ns", "iqr_ns", "mean_ns", "ci95_lo_ns", "ci95_hi_ns"):
        if key == "n":
            if derived["n"] != stored["n"]:
                return fail(f"n recomputed={derived['n']} stored={stored['n']}")
            continue
        if not H.close_enough(float(derived[key]), float(stored[key])):
            return fail(f"{key} recomputed={derived[key]} stored={stored[key]}")
    band_derived = H.variance_band(derived)
    band_stored = arm2048.get("variance_band") or {}
    if band_stored.get("derived_from") != "raw_ns":
        return fail("band not derived from raw_ns")
    if not H.close_enough(band_derived["lo_ns"], float(band_stored["lo_ns"])):
        return fail("band.lo mismatch")
    if not H.close_enough(band_derived["hi_ns"], float(band_stored["hi_ns"])):
        return fail("band.hi mismatch")

    live_raw = H.measure_dispatch_times(2048, scratch)
    live_stats = H.summarize(live_raw)
    if not H.within_band(live_stats["median_ns"], band_stored):
        return fail(
            f"live n=2048 median {live_stats['median_ns']} outside band "
            f"[{band_stored['lo_ns']}, {band_stored['hi_ns']}]"
        )

    payload = {
        "probe": "probe2-rewrite-quadratic",
        "unit_id": UNIT,
        "rewrite_write_ratio": live_clf["write_ratio_rewrite_2048_over_16"],
        "rewrite_cum_ratio": live_clf["cum_ratio_rewrite_2048_over_16"],
        "append_write_ratio": live_clf["write_ratio_append_2048_over_16"],
        "live_n2048_median_ns": live_stats["median_ns"],
        "within_band": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:TST-0241-probe2 rewrite mutant is quadratic; "
        "append-only stays linear; bands re-derived from raw_ns"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
