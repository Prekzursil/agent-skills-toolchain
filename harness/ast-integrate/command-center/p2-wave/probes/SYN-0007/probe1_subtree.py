#!/usr/bin/env python3
"""Named probe 1: every ranked row's prevented set is a real hierarchy subtree."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import validate_ranking_doc  # noqa: E402
from rank import children_map, subtree_claims  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0007.intervention-ranking.json"
SCHEMA = REPO / "command-center/schema/intervention-ranking.schema.json"
SENTINEL_SNIP = "SUCCESS:SYN-0007"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:SYN-0007-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL_SNIP not in text:
        print("FAILED:SYN-0007-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "SYN-0007" or doc.get("state") in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:SYN-0007-probe1 state", doc.get("state"))
        return 1
    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        print("FAILED:SYN-0007-probe1 catalog schema missing")
        return 1
    schema_errs = validate_ranking_doc(doc)
    if schema_errs:
        print("FAILED:SYN-0007-probe1 schema", schema_errs[0])
        return 1

    ranking = doc.get("ranking") or []
    if len(ranking) < 3:
        print(f"FAILED:SYN-0007-probe1 ranking too short {len(ranking)}")
        return 1
    hier = doc.get("hierarchy") or {}
    nodes = hier.get("nodes") or []
    edges = hier.get("edges") or []
    nodes_by_id = {str(n["id"]): n for n in nodes if isinstance(n, dict) and n.get("id")}
    kids = children_map(edges)
    if int(hier.get("max_depth") or 0) < 2:
        print("FAILED:SYN-0007-probe1 max_depth < 2 (flat list)")
        return 1

    mismatches = []
    for row in ranking:
        claims = row.get("prevented_claim_ids") or []
        if not isinstance(claims, list) or not claims:
            mismatches.append({"id": row.get("intervention_id"), "reason": "empty-prevented-set"})
            continue
        expected = subtree_claims(str(row["intervention_id"]), nodes_by_id, kids)
        if sorted(claims) != expected:
            mismatches.append(
                {
                    "id": row.get("intervention_id"),
                    "reason": "not-a-subtree",
                    "row": sorted(claims)[:8],
                    "expected": expected[:8],
                }
            )
    if mismatches:
        print("FAILED:SYN-0007-probe1 subtree mismatches")
        print(json.dumps(mismatches[:5], indent=2))
        return 1

    out = {
        "probe": "probe1-subtree",
        "unit_id": "SYN-0007",
        "ranked": len(ranking),
        "max_depth": hier.get("max_depth"),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:SYN-0007-probe1 prevented sets are hierarchy subtrees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
