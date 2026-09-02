#!/usr/bin/env python3
"""Probe 1: four planted mutant classes + zero false MERGE on 24 distinct units.

Both-states: a rewrite that lives in the Jaccard 0.05-0.24 band must still be
caught (embedding fire / ADJUDICATE or MERGE). A hand-verified distinct pair
must not auto-MERGE. Per-class rates are printed separately; a single accuracy
number is refused.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from eval import CLASSES, score_distinct, score_planted  # noqa: E402

RECEIPT = HERE.parents[3] / "command-center" / "receipts" / "CC-0020.json"


def main() -> int:
    planted = score_planted()
    distinct = score_distinct()
    summary = {
        "per_class": {
            c: {
                "n": planted["per_class"][c]["n"],
                "caught": planted["per_class"][c]["caught"],
                "rate": planted["per_class"][c]["rate"],
                "jaccard": planted["per_class"][c]["jaccard"],
                "cosine": planted["per_class"][c]["cosine"],
                "verdicts": planted["per_class"][c]["verdicts"],
            }
            for c in CLASSES
        },
        "all_four_caught": planted["all_four_caught"],
        "cross_seed_verdict": planted["cross_seed"]["verdict"],
        "cross_seed_not_merged": planted["cross_seed_not_merged"],
        "distinct_n": distinct["n_units"],
        "distinct_pairs": distinct["n_pairs"],
        "false_merge_count": distinct["false_merge_count"],
        "missing_ids": distinct["missing_ids"],
        "max_distinct_jaccard": distinct["max_jaccard"],
        "max_distinct_cosine": distinct["max_cosine"],
    }
    print(json.dumps(summary, sort_keys=True))
    if distinct["missing_ids"]:
        print("FAILED:CC-0020-probe1 missing catalog ids", distinct["missing_ids"])
        return 1
    if distinct["n_units"] < 24:
        print(f"FAILED:CC-0020-probe1 distinct set {distinct['n_units']} < 24")
        return 1
    if not planted["all_four_caught"]:
        print("FAILED:CC-0020-probe1 planted class miss", planted["misses"])
        return 1
    rewrite = planted["per_class"]["full-rewrite"]
    if not any(not row["lex_fires"] and row["emb_fires"] for row in rewrite["rows"]):
        print("FAILED:CC-0020-probe1 full-rewrite did not defeat lexical while firing embedding")
        return 1
    if distinct["false_merge_count"] != 0:
        print("FAILED:CC-0020-probe1 false MERGE", distinct["merges"][:3])
        return 1
    if not planted["cross_seed_not_merged"]:
        print("FAILED:CC-0020-probe1 cross-seed auto-merged (over-merge)")
        return 1
    if RECEIPT.is_file():
        doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        if "SUCCESS:CC-0020" not in json.dumps(doc):
            print("FAILED:CC-0020-probe1 sentinel absent from receipt")
            return 1
        rates = (doc.get("per_class_detection") or {})
        for c in CLASSES:
            live = planted["per_class"][c]["rate"]
            rec = rates.get(c, {}).get("rate")
            if rec is None or abs(float(rec) - live) > 1e-9:
                print(f"FAILED:CC-0020-probe1 receipt rate drift class={c} live={live} rec={rec}")
                return 1
        if int(doc.get("false_merge_count", -1)) != 0:
            print("FAILED:CC-0020-probe1 receipt false_merge_count not 0")
            return 1
    print("SUCCESS:CC-0020-probe1 four-class catch + zero false MERGE on 24")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
