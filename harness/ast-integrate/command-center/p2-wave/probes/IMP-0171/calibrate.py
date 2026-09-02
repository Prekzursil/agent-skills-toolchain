#!/usr/bin/env python3
"""Calibrate token-Jaccard bands from the planted-mutant corpus.

Bands are numeric min/max/mean. Adjectives are not a calibration.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import lexical as L  # noqa: E402

HIGH = C.HIGH_BAND_CLASSES
LOW = C.LOW_BAND_CLASSES


def _band(scores: list[float]) -> dict[str, Any]:
    if not scores:
        raise ValueError("empty score list")
    rounded = [round(s, 6) for s in scores]
    return {
        "n": len(rounded),
        "min": round(min(rounded), 6),
        "max": round(max(rounded), 6),
        "mean": round(mean(rounded), 6),
        "scores": rounded,
        "kind": "numeric",
    }


def calibrate() -> dict[str, Any]:
    seed = C.SEED
    by_class: dict[str, list[dict]] = defaultdict(list)
    for row in C.seed_pairs():
        scored = L.score_pair(C.SEED_ID, seed, row["id"], row["text"])
        scored["class"] = row["class"]
        by_class[row["class"]].append(scored)

    bands = {cls: _band([r["jaccard"] for r in rows]) for cls, rows in by_class.items()}
    high_min = min(bands[c]["min"] for c in HIGH)
    low_max = max(bands[c]["max"] for c in LOW)
    gap = round(high_min - low_max, 6)
    threshold = round((high_min + low_max) / 2.0, 6)
    control = next(
        r
        for r in by_class["known_distinct"]
        if r["right_id"] == C.KNOWN_DISTINCT_CONTROL_ID
        or r["left_id"] == C.KNOWN_DISTINCT_CONTROL_ID
    )
    return {
        "instrument": "token-set-jaccard",
        "token_pattern": L.TOKEN_RE.pattern,
        "scope": L.SCOPE,
        "seed_id": C.SEED_ID,
        "seed_token_count": len(L.tokenize(seed)),
        "classes": {cls: rows for cls, rows in by_class.items()},
        "bands": bands,
        "high_band_classes": list(HIGH),
        "low_band_classes": list(LOW),
        "high_band_min": high_min,
        "low_band_max": low_max,
        "separation_gap": gap,
        "lexical_near_duplicate_threshold": threshold,
        "threshold_rule": (
            "midpoint between min(exact_rename, paraphrase, one_parameter_fork) "
            "and max(full_rewrite, known_distinct). Pairs at or above the "
            "threshold are lexical near-duplicates. Pairs below it are not "
            "findings of this instrument, including full semantic rewrites."
        ),
        "known_distinct_control": {
            "pair": [C.SEED_ID, C.KNOWN_DISTINCT_CONTROL_ID],
            "jaccard": control["jaccard"],
            "intersection": control["intersection"],
            "union": control["union"],
        },
        "separated": gap > 0,
    }


def main() -> int:
    report = calibrate()
    print(json.dumps({k: report[k] for k in (
        "bands",
        "high_band_min",
        "low_band_max",
        "separation_gap",
        "lexical_near_duplicate_threshold",
        "known_distinct_control",
        "separated",
        "seed_token_count",
    )}, indent=2, sort_keys=True))
    if not report["separated"]:
        print("FAILED:IMP-0171 high and low bands overlap; corpus needs a wider gap")
        return 1
    for cls in HIGH:
        if report["bands"][cls]["min"] < report["lexical_near_duplicate_threshold"]:
            print(f"FAILED:IMP-0171 {cls} min below threshold")
            return 1
    for cls in LOW:
        if report["bands"][cls]["max"] >= report["lexical_near_duplicate_threshold"]:
            print(f"FAILED:IMP-0171 {cls} max reaches threshold")
            return 1
    print("SUCCESS:IMP-0171-calibrate bands separated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
