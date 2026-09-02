#!/usr/bin/env python3
"""Probe 1: planted trivial variants must collapse under the independent recount.

This is the DETECTOR CONTROL. It re-derives the collapse from the ledger;
it does not trust the artifact's boolean.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from ledger import PLANTED, SEED_ID, build_ledger  # noqa: E402
from measures import cluster_by_mechanism, recount_unique, report_payload  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0087-idea-count-recount.json"


def main() -> int:
    ledger = build_ledger()
    ideas = ledger["ideas"]
    planted_ids = [p[0] for p in PLANTED]
    want = {SEED_ID, *planted_ids}
    clusters = cluster_by_mechanism(ideas)
    matching = [
        members
        for members in clusters.values()
        if want <= {m["id"] for m in members}
    ]
    if len(matching) != 1:
        print(f"FAILED:CNF-0087-probe1 matching_clusters={len(matching)}")
        return 1
    members = matching[0]
    if len(members) < 4:
        print(f"FAILED:CNF-0087-probe1 cluster_size={len(members)} want>=4")
        return 1
    recount_n = recount_unique(ideas)
    if recount_n != 97:
        print(f"FAILED:CNF-0087-probe1 recount_unique={recount_n} want=97")
        return 1
    distinct = [i for i in ideas if i["id"] in {"I-002", "I-003", "I-004"}]
    d_clusters = cluster_by_mechanism(distinct)
    if len(d_clusters) != 3:
        print("FAILED:CNF-0087-probe1 distinct trio collapsed")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0087-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    pc = report_payload(doc).get("planted_control") or {}
    if pc.get("collapsed") is not True:
        print("FAILED:CNF-0087-probe1 artifact planted_control.collapsed is not true")
        return 1
    if set(pc.get("variant_ids") or []) != set(planted_ids):
        print("FAILED:CNF-0087-probe1 artifact variant_ids mismatch")
        return 1
    if SENTINEL_SNIP not in json.dumps(doc):
        print("FAILED:CNF-0087-probe1 sentinel absent")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-planted-collapse",
                "unit_id": "CNF-0087",
                "collapsed": True,
                "cluster_size": len(members),
                "member_ids": [m["id"] for m in members],
                "recount_unique": recount_n,
                "distinct_trio_separate": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0087-probe1 planted trivial variants collapsed")
    return 0


SENTINEL_SNIP = "SUCCESS:CNF-0087"


if __name__ == "__main__":
    raise SystemExit(main())
