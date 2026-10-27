#!/usr/bin/env python3
"""IMP-0102 probe1: determinism. Query 'quuxzorch' run 50x on one index and
after 50 independent index rebuilds from shuffled plugin lists yields ONE
distinct ordering; alpha-tie/beta-tie is a TRUE score tie broken by stable
key; popularity never moves the order (negative control)."""
from __future__ import annotations

import glob
import importlib.util
import json
import random
import sys
import sys as _sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def load_search():
    hits = sorted(glob.glob(str(REPO / "tools" / "marketplace" / "search.py")))
    spec = importlib.util.spec_from_file_location("imp0102_search", hits[0])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    S = load_search()
    corpus = json.loads((REPO / "tools" / "marketplace" / "fixtures"
                         / "registry_corpus.json").read_text(encoding="utf-8"))
    plugins = corpus["plugins"]

    baseline = S.SearchIndex(plugins).query("quuxzorch")
    base_order = [h["id"] for h in baseline["hits"]]

    # 50 repeats on one index
    one_index_orders = {tuple(S.SearchIndex(plugins).query("quuxzorch")["hits"]
                              and [h["id"] for h in S.SearchIndex(plugins)
                                   .query("quuxzorch")["hits"]])
                        for _ in range(50)}
    # 50 rebuilds from shuffled insertion orders
    rng = random.Random(102)
    rebuild_orders = set()
    for _ in range(50):
        shuffled = list(plugins)
        rng.shuffle(shuffled)
        rebuild_orders.add(tuple(h["id"] for h in S.SearchIndex(shuffled).query("quuxzorch")["hits"]))
    distinct = len(rebuild_orders | one_index_orders)
    one_distinct = distinct == 1 and rebuild_orders == {tuple(base_order)}

    # true tie: alpha-tie and beta-tie share an identical score; id breaks it
    hits = baseline["hits"]
    tie_equal = (len(hits) == 2 and hits[0]["score"] == hits[1]["score"]
                 and hits[0]["id"] == "alpha-tie" and hits[1]["id"] == "beta-tie")

    # popularity negative control: inflate popular-decoy, order unchanged
    mutated = [dict(p) for p in plugins]
    for p in mutated:
        if p["id"] == "popular-decoy":
            p["downloads"] = 10**12
            p["stars"] = 10**9
    mut_order = [h["id"] for h in S.SearchIndex(mutated).query("quuxzorch")["hits"]]
    popularity_inert = mut_order == base_order

    result = {
        "unit_id": "IMP-0102",
        "probe": "probe1-repeat-shuffle",
        "ordering": base_order,
        "tie_equal": tie_equal,
        "distinct": distinct,
        "one_distinct_ordering": one_distinct,
        "popularity_inert": popularity_inert,
        "pass": one_distinct and tie_equal and popularity_inert,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0102-probe1 one distinct ordering across 50 repeats + 50 shuffled "
            "rebuilds; true tie broken by stable key; popularity inert"
            if result["pass"] else
            "FAILED:IMP-0102-probe1 determinism contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
