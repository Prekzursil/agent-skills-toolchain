#!/usr/bin/env python3
"""Probe 2: independently written line-set differ over the same pair.

Does not import classify_pair for its verdicts. Requires an exact per-file
match with the production classifier. Disagreements are reported, never averaged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PLUGIN))
import drift as D  # noqa: E402
import independent_differ as I  # noqa: E402
import scenario as S  # noqa: E402

OUT = HERE / "probe2-independent.raw.json"


def main() -> int:
    pair = S.resolve_pair()
    repo_root = Path(pair["repo_root"])
    live_root = Path(pair["live_root"])
    prod = {r["path"]: r["classification"] for r in D.classify_trees(repo_root, live_root)}
    indep_rows = I.classify_trees_independent(repo_root, live_root)
    indep = {r["path"]: r["classification"] for r in indep_rows}

    keys = sorted(set(prod) | set(indep))
    disagreements = []
    for rel in keys:
        a, b = prod.get(rel), indep.get(rel)
        if a != b:
            disagreements.append({"path": rel, "classifier": a, "independent": b})

    doc = {
        "probe": "probe2-independent-differ",
        "unit_id": "IMP-0034",
        "pair_source": pair["source"],
        "files": len(keys),
        "disagreements": disagreements,
        "independent_algorithm": "sha256 identity + sorted two-pointer line comm",
        "classifier_algorithm": "bytes identity + Counter line-multiset subtraction",
        "averaged": False,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if disagreements:
        print(json.dumps(disagreements, indent=2)[:2000])
        print(f"FAILED:IMP-0034-probe2 disagreements={len(disagreements)}")
        return 1
    if len(keys) < 8:
        print(f"FAILED:IMP-0034-probe2 pair too small files={len(keys)}")
        return 1

    print(
        f"source={pair['source']} files={len(keys)} disagreements=0 "
        "signals=classifier,independent-line-comm averaged=False"
    )
    print("SUCCESS:IMP-0034-probe2 independent line-set differ exact match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
