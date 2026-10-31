"""IMP-0171 calibration: compute numeric similarity bands from the planted corpus.

Prints one JSON object: per-class numeric bands plus the derived lexical
threshold (midpoint between the high-band minimum and the low-band maximum).
Writes calibration.json next to this script.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from corpus import pair_scores, SEED, DISTINCT_NAMES  # noqa: E402
import lexical  # noqa: E402

HIGH_CLASSES = ["exact_rename", "paraphrase", "one_parameter_fork"]
LOW_CLASSES = ["full_rewrite", "known_distinct"]


def _band(scores: list) -> dict:
    return {
        "kind": "numeric",
        "min": min(scores), "max": max(scores), "mean": sum(scores) / len(scores),
        "n": len(scores), "scores": [round(s, 6) for s in scores],
    }


def calibrate() -> dict:
    scores = pair_scores()
    bands = {cls: _band(v) for cls, v in scores.items()}
    high_min = min(bands[c]["min"] for c in HIGH_CLASSES)
    low_max = max(bands[c]["max"] for c in LOW_CLASSES)
    threshold = (high_min + low_max) / 2
    out = {
        "bands": bands,
        "high_band": [round(high_min, 6), round(max(bands[c]["max"] for c in HIGH_CLASSES), 6)],
        "low_band": [round(min(bands[c]["min"] for c in LOW_CLASSES), 6), round(low_max, 6)],
        "gap": round(high_min - low_max, 6),
        "threshold": round(threshold, 6),
        "threshold_rule": "midpoint(high_min, low_max)",
        "distinct_names": DISTINCT_NAMES,
    }
    # seed-vs-first-distinct control pair, recorded verbatim
    first = _distinct_doc0()
    j = lexical.jaccard(SEED, first)
    out["control_pair"] = {
        "pair": ["seed-harbor-review-gate", DISTINCT_NAMES[0]],
        "intersection": j["intersection"], "union": j["union"],
        "jaccard": round(j["jaccard"], 6),
    }
    return out


def _distinct_doc0() -> str:
    from corpus import _distinct
    return _distinct(0)


if __name__ == "__main__":
    result = calibrate()
    (HERE / "calibration.json").write_text(
        json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result["bands"], indent=1))
    print(json.dumps({k: result[k] for k in
                      ["high_band", "low_band", "gap", "threshold", "control_pair"]}))
