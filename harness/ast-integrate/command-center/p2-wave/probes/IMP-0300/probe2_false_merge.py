#!/usr/bin/env python3
"""Probe 2: distinct-pair false-merge rate, plus string-equality negative control.

Mechanically independent of probe 1: starts from fixtures, not from probe-1 JSON.
Also records that signal A and signal B disagree on at least one XOR pair, proving
they are not the same predicate.
"""
from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from loader import load_counter, load_fixture, planted_members  # noqa: E402


def main() -> int:
    ui = load_counter()
    doc = load_fixture()
    reps = doc["distinct_representatives"]
    texts = [row["text"] for row in reps]
    clustered = ui.cluster_ideas(texts)
    pairs = list(combinations(range(len(texts)), 2))
    merges = ui.false_merge_rate(clustered.cluster_ids, pairs)

    planted_texts, planted_classes, _ = planted_members(doc)
    planted = ui.evaluate_labeled(planted_texts, planted_classes)

    xor_pairs = [(row["left"], row["right"]) for row in doc["xor_pairs"]]
    xor = ui.signals_are_mechanically_different(xor_pairs)

    xor_ok = True
    xor_detail = []
    for row in doc["xor_pairs"]:
        info = ui.pair_signals(row["left"], row["right"])
        a_hit, b_hit = info["signal_a_hit"], info["signal_b_hit"]
        expect = row["expect"]
        ok = (expect == "b_only" and (not a_hit) and b_hit) or (
            expect == "a_only" and a_hit and (not b_hit)
        )
        xor_detail.append(
            {
                "id": row["id"],
                "expect": expect,
                "signal_a_hit": a_hit,
                "signal_b_hit": b_hit,
                "jaccard": info["signal_a_ngram_jaccard"],
                "ok": ok,
            }
        )
        xor_ok = xor_ok and ok

    payload = {
        "pass": False,
        "probe": "probe2-false-merge-and-string-equality-negative",
        "unit_id": "IMP-0300",
        "distinct_n": len(texts),
        "distinct_unique_count": clustered.unique_count,
        "false_merge": merges,
        "planted_string_equality_count": planted["string_equality_count"],
        "planted_semantic_unique_count": planted["unique_count"],
        "string_equality_worse": planted["string_equality_worse"],
        "xor": xor,
        "xor_detail": xor_detail,
    }
    if merges["rate"] != 0.0 or clustered.unique_count != len(texts):
        payload["pass"] = False
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            f"FAILED:IMP-0300-probe2 false-merge rate={merges['rate']} unique={clustered.unique_count}"
        )
        return 1
    if not planted["string_equality_worse"]:
        print(json.dumps(payload, indent=2, sort_keys=True))
        print("FAILED:IMP-0300-probe2 string-equality counter was not worse on planted set")
        return 1
    if not xor["mechanically_different"] or not xor_ok:
        print(json.dumps(payload, indent=2, sort_keys=True))
        print("FAILED:IMP-0300-probe2 signals A and B did not disagree as required")
        return 1
    payload["pass"] = True
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"false_merge_rate={merges['rate']} distinct_unique={clustered.unique_count} "
        f"string_eq={planted['string_equality_count']} semantic={planted['unique_count']} "
        f"xor_count={xor['xor_count']}"
    )
    print("SUCCESS:IMP-0300-probe2 distinct-pairs false-merge=0 and string-equality worse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
