#!/usr/bin/env python3
"""Probe 2: independently re-derive ranks of three sampled claims from the edge list.

Mechanically different from probe 1: does not call UnionFind. Walks the
receipt's directed edge list with DFS after inverting confirmation->probe->upstream.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from graph import ranks_from_edge_list  # noqa: E402
from ingest import load_planted  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0132.json"
SAMPLED = (
    "C-CACHE-COLLAPSE",
    "C-SHELL-FIELD-INDEP",
    "C-THIRD-INDEPENDENT",
)
EXPECT = {
    "C-CACHE-COLLAPSE": 1,
    "C-SHELL-FIELD-INDEP": 2,
    "C-THIRD-INDEPENDENT": 3,
}


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0132-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    edges = doc.get("edge_list") or (doc.get("independence_graph") or {}).get("edges")
    if not isinstance(edges, list) or not edges:
        print("FAILED:CNF-0132-probe2 edge_list missing")
        return 1
    records = list(load_planted().get("records") or [])
    recomputed = ranks_from_edge_list(edges, records)
    rows = []
    failed = False
    art_per = {
        r.get("claim_id"): r for r in ((doc.get("per_claim") or {}).get("planted") or [])
    }
    for cid in SAMPLED:
        got = (recomputed.get(cid) or {}).get("rank")
        expect = EXPECT[cid]
        art_rank = (art_per.get(cid) or {}).get("rank")
        match = got == expect and got == art_rank
        rows.append(
            {
                "claim_id": cid,
                "dfs_rank": got,
                "expected": expect,
                "receipt_rank": art_rank,
                "match": match,
            }
        )
        if not match:
            failed = True
    print(json.dumps(rows, sort_keys=True))
    if failed:
        print("FAILED:CNF-0132-probe2 rank mismatch")
        return 1
    if not doc.get("edge_list"):
        print("FAILED:CNF-0132-probe2 receipt omitted edge_list")
        return 1
    print("SUCCESS:CNF-0132-probe2 edge-list recompute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
