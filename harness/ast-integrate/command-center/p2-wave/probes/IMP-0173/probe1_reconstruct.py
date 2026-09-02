#!/usr/bin/env python3
"""Probe 1: pre-collapse candidate set reconstructible from the post-collapse graph.

Catalog tests_required[0]: pre-collapse set reconstructible from the graph (set equality).
Both-states: a lossy delete-collapse must FAIL the same check.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collapse as C  # noqa: E402

FIX = HERE / "fixtures" / "candidates.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0173-probe1 {msg}")
    return 1


def main() -> int:
    candidates = C.load_candidates(FIX)
    graph = C.collapse_duplicates(candidates)
    cmp_ok = C.sets_equal(candidates, graph)
    print(json.dumps({"good": cmp_ok}, sort_keys=True))

    if not cmp_ok["equal"]:
        return fail("set-equality-failed-on-preserving-collapse")
    if cmp_ok["pre_collapse_n"] != len(candidates):
        return fail("pre-collapse-set-shrank-before-compare")
    if sorted(cmp_ok["pre_collapse_ids"]) != sorted(c["id"] for c in candidates):
        return fail("id-set-drift")

    # IDs are never deleted.
    live_ids = {r["id"] for r in graph["rows"]}
    want_ids = {c["id"] for c in candidates}
    if live_ids != want_ids:
        return fail(f"deleted-ids live={sorted(live_ids)} want={sorted(want_ids)}")

    # Pre-collapse duplicate-of edges survive.
    retained = [e for e in graph["edges"] if e.get("retained") is True]
    if not any(e["from"] == "C-A2" and e["to"] == "C-A1" for e in retained):
        return fail("pre-collapse-duplicate-of-edge-dropped")

    # Loser provenance is still on the aliased row, not swallowed.
    a2 = next(r for r in graph["rows"] if r["id"] == "C-A2")
    if a2["status"] != "aliased":
        return fail("C-A2-should-be-aliased-despite-repetition_count=99")
    if a2["provenance"].get("source_id") != "src.bravo":
        return fail("loser-provenance-dropped")
    if "C-A1" not in a2["duplicate_of"]:
        return fail("loser-missing-duplicate-of-canonical")

    # Canonical of group A is C-A1 (high evidence), not C-A2 (high echo count).
    a_canon = {r["canonical_id"] for r in graph["rows"] if r["mechanism_fingerprint"] == "mech.stage-gate.v1"}
    if a_canon != {"C-A1"}:
        return fail(f"group-A-canonical-wrong {a_canon}")

    # Union keeps C-A3's unique stop_rule on the canonical payload_union.
    a1 = next(r for r in graph["rows"] if r["id"] == "C-A1")
    if a1["payload_union"].get("stop_rule") != "halt-on-licence":
        return fail("union-dropped-loser-unique-payload")

    # Canonical lineage is the cluster provenance union.
    sources = {p.get("source_id") for p in a1["lineage"]}
    if sources != {"src.alpha", "src.bravo", "src.charlie"}:
        return fail(f"canonical-lineage-incomplete {sources}")

    # Negative control: deleting aliased rows must make reconstruction fail.
    lossy = C.collapse_lossy_delete(candidates)
    cmp_bad = C.sets_equal(candidates, lossy)
    print(json.dumps({"lossy": cmp_bad}, sort_keys=True))
    if cmp_bad["equal"]:
        return fail("lossy-delete-still-reconstructed-silent-detector")
    if not cmp_bad["missing_from_graph"]:
        return fail("lossy-delete-did-not-lose-records")

    print(
        "reconstruct_equal=True "
        f"n={cmp_ok['pre_collapse_n']} "
        f"canonical={graph['canonical_ids']} "
        f"aliased={graph['aliased_ids']} "
        f"lossy_missing={len(cmp_bad['missing_from_graph'])}"
    )
    print("SUCCESS:IMP-0173-probe1 pre-collapse set reconstructible (set equality)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
