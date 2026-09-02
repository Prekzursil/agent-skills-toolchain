#!/usr/bin/env python3
"""Probe 2: construction check on 10 fusible pairs (independent of emit sample).

Evidence B: fusion of each sampled pair type is expressible in IR.
Both-states: a HARD-conflict pair must be refused; claiming it fusible goes red.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from ir import construct_fusion  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0081-merge-compatibility-map-v2.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:WFA-0081-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    by = {n["id"]: n for n in doc["nodes"]}
    listed = [tuple(p) for p in doc.get("fusible_pairs") or []]
    if len(listed) < 10:
        print(f"FAILED:WFA-0081-probe2 fusible_pairs {len(listed)} < 10")
        return 1
    sample = []
    for a, b in listed:
        row = construct_fusion(by[a], by[b])
        if not row["expressible"]:
            print(f"FAILED:WFA-0081-probe2 listed fusible not constructible {a}+{b} {row.get('reason')}")
            return 1
        sample.append(row)
        if len(sample) >= 10:
            break
    recorded = doc.get("construction_sample") or []
    if len(recorded) != 10:
        print(f"FAILED:WFA-0081-probe2 artifact sample {len(recorded)} want 10")
        return 1
    rec_pairs = {tuple(r["pair"]) for r in recorded}
    live_pairs = {tuple(r["pair"]) for r in sample}
    if rec_pairs != live_pairs:
        print(f"FAILED:WFA-0081-probe2 sample mismatch rec={sorted(rec_pairs)[:3]} live={sorted(live_pairs)[:3]}")
        return 1
    for r in recorded:
        if not r.get("expressible") or not r.get("ir"):
            print("FAILED:WFA-0081-probe2 recorded sample not expressible")
            return 1
        ir = r["ir"]
        if ir.get("lineage", {}).get("decomposes_to") != r["pair"]:
            print("FAILED:WFA-0081-probe2 lineage does not recover sources")
            return 1
        if ir.get("execution_semantics") is not None:
            print("FAILED:WFA-0081-probe2 IR claimed execution semantics")
            return 1

    hard_edge = next(
        e
        for e in doc["edges"]
        if e.get("kind") == "conflicts-with" and e.get("grade") == "HARD"
    )
    ha, hb = hard_edge["source"], hard_edge["target"]
    lo, hi = (ha, hb) if ha < hb else (hb, ha)
    if [lo, hi] in [list(p) for p in listed] or [hi, lo] in [list(p) for p in listed]:
        print("FAILED:WFA-0081-probe2 HARD pair listed as fusible")
        return 1
    refused = construct_fusion(by[ha], by[hb])
    if refused["expressible"]:
        print("FAILED:WFA-0081-probe2 HARD pair constructed")
        return 1
    if not refused.get("conflicting_mechanisms"):
        print("FAILED:WFA-0081-probe2 refusal did not name mechanisms")
        return 1

    mutant = copy.deepcopy(doc)
    mutant["fusible_pairs"] = [[lo, hi]] + mutant["fusible_pairs"]
    mutant_listed = [tuple(p) for p in mutant["fusible_pairs"]]
    if (lo, hi) in mutant_listed or (hi, lo) in mutant_listed:
        planted = construct_fusion(by[lo], by[hi])
        if planted["expressible"]:
            print("FAILED:WFA-0081-probe2 mutant HARD pair became expressible")
            return 1
        print("mutant_hard_pair_refused=True")
    else:
        print("FAILED:WFA-0081-probe2 mutant plant failed")
        return 1

    honesty = str((doc.get("honesty") or {}).get("statement") or "").lower()
    if "no merge has yet been executed" not in honesty:
        print("FAILED:WFA-0081-probe2 honesty block missing")
        return 1

    print(
        json.dumps(
            {
                "constructed": 10,
                "all_expressible": True,
                "hard_pair_refused": True,
                "hard_pair": [lo, hi],
                "conflicting_mechanisms": refused["conflicting_mechanisms"],
                "operators": sorted({r["operator"] for r in sample}),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0081-probe2 fusion construction and HARD-pair refusal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
