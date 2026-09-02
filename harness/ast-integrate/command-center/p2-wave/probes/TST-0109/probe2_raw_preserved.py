#!/usr/bin/env python3
"""Named probe 2: raw per-run numbers are preserved, not only the summary.

Catalog test: test_raw_per_run_numbers_are_preserved_not_only_the_summary.

Statistics reviewer: re-derives mean, stdev, variance band, and MDE from
the attached raw vector (independent.py, not variance_band.stats) and
refuses a summary-only copy of the receipt.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from independent import close, hand_oracle, recompute  # noqa: E402

UNIT = "TST-0109"
ART = REPO / "command-center/receipts/TST-0109.json"
REQUIRED = (
    "router-latency",
    "hook-overhead",
    "fan-out-throughput",
    "suite-wall-clock",
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def raw_ok(row: dict) -> tuple[bool, str]:
    raw = row.get("raw")
    if not isinstance(raw, list) or len(raw) < 2:
        return False, "raw-absent"
    if len(raw) != int(row.get("n") or 0):
        return False, "n-len-mismatch"
    derived = recompute([float(x) for x in raw])
    for key, dkey in (("mean", "mean"), ("stdev", "stdev"), ("mde", "mde")):
        if key not in row or not close(float(row[key]), float(derived[dkey])):
            return False, f"{key}-not-from-raw"
    band = row.get("variance_band") or {}
    if band:
        if not close(float(band["low"]), derived["band_low"]):
            return False, "band-low-mismatch"
        if not close(float(band["high"]), derived["band_high"]):
            return False, "band-high-mismatch"
    nmin = row.get("n_min_for_claimed_5pct")
    if nmin is not None and int(nmin) != int(derived["n_min_for_claimed_5pct"]):
        return False, "n-min-mismatch"
    return True, "ok"


def summary_only_rejected(doc: dict) -> bool:
    stripped = copy.deepcopy(doc)
    for row in stripped.get("benchmarks") or []:
        row.pop("raw", None)
    for row in stripped.get("benchmarks") or []:
        ok, _ = raw_ok(row)
        if ok:
            return False
    return True


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")
    if "SUCCESS:TST-0109" not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    rows = {r["id"]: r for r in (doc.get("benchmarks") or []) if isinstance(r, dict)}
    missing = [i for i in REQUIRED if i not in rows]
    if missing:
        return fail(f"missing {missing}")

    checked = []
    for bid in REQUIRED:
        ok, why = raw_ok(rows[bid])
        if not ok:
            return fail(f"{bid} {why}")
        checked.append(
            {
                "id": bid,
                "n": rows[bid]["n"],
                "raw_len": len(rows[bid]["raw"]),
                "mean_from_raw": True,
                "mde_from_raw": True,
            }
        )

    gauss = ((doc.get("controls") or {}).get("gaussian-seeded")) or {}
    if gauss:
        ok, why = raw_ok(gauss)
        if not ok:
            return fail(f"gaussian {why}")

    hand_rec = ((doc.get("controls") or {}).get("hand-derived-five")) or {}
    oracle = hand_oracle()
    if not hand_rec:
        return fail("hand control absent from receipt")
    if list(hand_rec.get("raw") or []) != oracle["raw"]:
        return fail("hand raw mutated")
    ok, why = raw_ok(hand_rec)
    if not ok:
        return fail(f"hand {why}")
    if not close(float(hand_rec["mean"]), oracle["mean"]):
        return fail("hand mean != 12")
    if not close(float(hand_rec["stdev"]) ** 2, 2.5):
        return fail("hand variance != 2.5")

    if not summary_only_rejected(doc):
        return fail("summary-only copy was accepted")

    mutated = copy.deepcopy(doc)
    mutated["benchmarks"][0]["mean"] = float(mutated["benchmarks"][0]["mean"]) + 1e9
    ok, why = raw_ok(mutated["benchmarks"][0])
    if ok:
        return fail("wrong-summary still accepted")
    if why != "mean-not-from-raw":
        return fail(f"wrong-summary why={why}")

    out = {
        "probe": "probe2-raw-preserved",
        "unit_id": UNIT,
        "checked": checked,
        "summary_only_rejected": True,
        "wrong_summary_rejected": True,
        "hand_mean": oracle["mean"],
        "hand_variance": 2.5,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    for row in checked:
        print(
            f"raw {row['id']} n={row['n']} raw_len={row['raw_len']} "
            "mean_from_raw=true mde_from_raw=true"
        )
    print("SUCCESS:TST-0109-probe2 raw per-run numbers preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
