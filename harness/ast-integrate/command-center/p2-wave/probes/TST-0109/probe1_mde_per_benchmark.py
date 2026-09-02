#!/usr/bin/env python3
"""Named probe 1: MDE is computed per benchmark (live re-run + receipt).

Catalog test: test_minimum_detectable_effect_is_computed_per_benchmark.

Independently runs the harness, derives MDE from each raw vector, and
checks the receipt carries the same fields. Empty input must refuse a
number. Does not trust the receipt summary without recomputing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from independent import close, hand_oracle, recompute  # noqa: E402
from variance_band.benchmarks import EmptyInputError, router_once  # noqa: E402
from variance_band.harness import run_pack  # noqa: E402
from variance_band.stats import band_from_raw  # noqa: E402

UNIT = "TST-0109"
ART = REPO / "command-center/receipts/TST-0109.json"
REQUIRED = (
    "router-latency",
    "hook-overhead",
    "fan-out-throughput",
    "suite-wall-clock",
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if "SUCCESS:TST-0109" not in text:
        return fail("sentinel-absent")

    live = run_pack(REPO)
    live_rows = {r["id"]: r for r in live["benchmarks"]}
    rec_rows = {r["id"]: r for r in (doc.get("benchmarks") or []) if isinstance(r, dict)}
    missing_live = [i for i in REQUIRED if i not in live_rows]
    missing_rec = [i for i in REQUIRED if i not in rec_rows]
    if missing_live:
        return fail(f"live missing {missing_live}")
    if missing_rec:
        return fail(f"receipt missing {missing_rec}")

    for bid in REQUIRED:
        row = live_rows[bid]
        raw = list(row["raw"])
        if len(raw) != int(row["n"]) or len(raw) < 2:
            return fail(f"{bid} raw/n mismatch n={row['n']} raw={len(raw)}")
        derived = recompute([float(x) for x in raw])
        if not close(derived["mde"], float(row["mde"])):
            return fail(f"{bid} live MDE != independent recompute")
        if derived["mde"] < 0:
            return fail(f"{bid} negative MDE")
        lib = band_from_raw(bid, raw)
        if not close(lib["mde"], derived["mde"]):
            return fail(f"{bid} library/independent MDE mismatch")
        rec = rec_rows[bid]
        if "mde" not in rec or rec.get("mde") is None:
            return fail(f"{bid} receipt MDE absent")
        rec_raw = rec.get("raw")
        if not isinstance(rec_raw, list) or len(rec_raw) < 2:
            return fail(f"{bid} receipt raw absent")
        rec_derived = recompute([float(x) for x in rec_raw])
        if not close(rec_derived["mde"], float(rec["mde"])):
            return fail(f"{bid} receipt MDE not derived from its raw")
        if int(rec["n"]) != len(rec_raw):
            return fail(f"{bid} receipt n != len(raw)")

    gauss = (live.get("controls") or {}).get("gaussian-seeded") or {}
    if not gauss or gauss.get("mde") is None:
        return fail("gaussian control MDE absent")
    g_derived = recompute([float(x) for x in gauss["raw"]])
    if not close(g_derived["mde"], float(gauss["mde"])):
        return fail("gaussian MDE mismatch")

    empty = (live.get("controls") or {}).get("empty-input") or {}
    if empty.get("fired_on_empty") is not True or empty.get("emitted_number") is not False:
        return fail(f"empty-input control {empty}")
    try:
        router_once([])
        return fail("empty router emitted a number")
    except EmptyInputError:
        pass

    hand = hand_oracle()
    lib_hand = band_from_raw(hand["id"], hand["raw"])
    if not close(lib_hand["mean"], hand["mean"]) or not close(lib_hand["mde"], hand["mde"]):
        return fail("hand fixture library mismatch")
    if not close(lib_hand["stdev"] ** 2, 2.5):
        return fail("hand fixture variance is not 2.5")

    out = {
        "probe": "probe1-mde-per-benchmark",
        "unit_id": UNIT,
        "benchmarks": [
            {
                "id": bid,
                "n": live_rows[bid]["n"],
                "mean": live_rows[bid]["mean"],
                "stdev": live_rows[bid]["stdev"],
                "mde": live_rows[bid]["mde"],
                "n_min_for_claimed_5pct": live_rows[bid]["n_min_for_claimed_5pct"],
            }
            for bid in REQUIRED
        ],
        "empty_input_refused": True,
        "hand_mde": hand["mde"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    for bid in REQUIRED:
        r = live_rows[bid]
        print(
            f"benchmark {bid} n={r['n']} mean={r['mean']:.3f} "
            f"stdev={r['stdev']:.3f} mde={r['mde']:.3f} "
            f"n_min_5pct={r['n_min_for_claimed_5pct']}"
        )
    print("SUCCESS:TST-0109-probe1 MDE computed per benchmark")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
