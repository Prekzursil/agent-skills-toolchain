#!/usr/bin/env python3
"""Named probe 2: known-distinct control pair scores in the low band.

Mechanically different from probe 1: does not walk the calibration table.
It re-scores the designated distinct pair (and one exact-rename pair) with
the Jaccard function, then checks the receipt's numeric threshold. A
threshold of 0.01 would false-positive the distinct pair; the calibrated
threshold must not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import lexical as L  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0171.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0171-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0171-probe2 receipt unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0171-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0171" not in text:
        print("FAILED:IMP-0171-probe2 sentinel absent")
        return 1

    cal_doc = doc.get("calibration") if isinstance(doc.get("calibration"), dict) else {}
    threshold = cal_doc.get("lexical_near_duplicate_threshold")
    low_max = cal_doc.get("low_band_max")
    high_min = cal_doc.get("high_band_min")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (threshold, low_max, high_min)):
        print("FAILED:IMP-0171-probe2 threshold/bands are not numbers")
        return 1

    cmap = C.candidate_map()
    seed = cmap[C.SEED_ID]
    distinct = cmap[C.KNOWN_DISTINCT_CONTROL_ID]
    rename_id, rename_text = C.EXACT_RENAME[0]
    rewrite_id, rewrite_text = C.FULL_REWRITE[0]

    distinct_row = L.score_pair(C.SEED_ID, seed, C.KNOWN_DISTINCT_CONTROL_ID, distinct)
    rename_row = L.score_pair(C.SEED_ID, seed, rename_id, rename_text)
    rewrite_row = L.score_pair(C.SEED_ID, seed, rewrite_id, rewrite_text)

    dj = distinct_row["jaccard"]
    rj = rename_row["jaccard"]
    wj = rewrite_row["jaccard"]

    if dj > float(low_max) + 1e-9:
        print(f"FAILED:IMP-0171-probe2 distinct jaccard {dj} above low_band_max {low_max}")
        return 1
    if dj >= float(threshold):
        print(f"FAILED:IMP-0171-probe2 distinct pair false-positive at threshold {threshold}")
        return 1
    if rj < float(high_min) - 1e-9 or rj < float(threshold):
        print(f"FAILED:IMP-0171-probe2 rename jaccard {rj} missed by threshold {threshold}")
        return 1
    if wj >= float(threshold):
        print(f"FAILED:IMP-0171-probe2 rewrite jaccard {wj} claimed detectable")
        return 1
    if wj > float(low_max) + 1e-9:
        print(f"FAILED:IMP-0171-probe2 rewrite {wj} not in low band")
        return 1

    naive_threshold = 0.01
    naive_false_positive = dj >= naive_threshold
    if not naive_false_positive:
        print("FAILED:IMP-0171-probe2 0.01-threshold control did not fire on distinct pair")
        return 1

    same_low_band = (dj <= float(low_max) + 1e-9) and (wj <= float(low_max) + 1e-9)
    if not same_low_band:
        print("FAILED:IMP-0171-probe2 rewrite and distinct not in the same low band")
        return 1

    payload = {
        "calibrated_threshold": threshold,
        "distinct_id": C.KNOWN_DISTINCT_CONTROL_ID,
        "distinct_jaccard": dj,
        "distinct_below_threshold": True,
        "naive_0_01_threshold_false_positive": True,
        "pass": True,
        "probe": "probe2-known-distinct-control",
        "rename_id": rename_id,
        "rename_jaccard": rj,
        "rename_above_threshold": True,
        "rewrite_id": rewrite_id,
        "rewrite_jaccard": wj,
        "rewrite_not_detectable": True,
        "rewrite_and_distinct_same_low_band": True,
        "unit_id": "IMP-0171",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"distinct={dj} rewrite={wj} rename={rj} threshold={threshold} "
        "naive_0.01_false_positive=True"
    )
    print("SUCCESS:IMP-0171-probe2 known-distinct pair scores in the low band")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
