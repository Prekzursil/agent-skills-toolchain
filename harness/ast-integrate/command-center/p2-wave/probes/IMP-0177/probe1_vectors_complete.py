#!/usr/bin/env python3
"""Probe 1: coverage vectors computed for every registry candidate (no nulls).

Signals:
  * vector_count == candidate_count and null_count == 0
  * empty-covers candidate yields a zero vector, not None
  * mutating one cover flips exactly one bit (vector is computed, not a constant)
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center"))

from foundry.capability.taxonomy import (  # noqa: E402
    capability_ids,
    check_guard,
    load_lock,
    load_spec,
    load_taxonomy,
    spec_matches_taxonomy,
)
from foundry.capability.vectorize import (  # noqa: E402
    load_candidates,
    vectorize,
    vectorize_all,
)

HERE = Path(__file__).resolve().parent


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0177-probe1 {msg}")
    return 1


def main() -> int:
    tax = load_taxonomy()
    lock = load_lock()
    families = load_spec()
    aligned, why = spec_matches_taxonomy(families, tax)
    if not aligned:
        return fail(why)
    guard = check_guard(tax, lock)
    if not guard["ok"]:
        return fail(f"live-guard:{guard['code']}")

    candidates = load_candidates()
    bundle = vectorize_all(candidates, tax)
    axis = capability_ids(tax)
    if bundle["candidate_count"] != len(candidates):
        return fail("candidate-count-mismatch")
    if bundle["null_count"] != 0:
        return fail(f"nulls={bundle['null_ids']}")
    if bundle["vector_count"] != bundle["candidate_count"]:
        return fail("vector-count-short")
    if not bundle["coverage_complete"]:
        return fail("coverage-incomplete")
    if any(v.get("bits") is None for v in bundle["vectors"]):
        return fail("null-bits")
    if any(len(v["bits"]) != len(axis) for v in bundle["vectors"]):
        return fail("axis-length-mismatch")
    if any(any(b not in (0, 1) for b in v["bits"]) for v in bundle["vectors"]):
        return fail("non-binary-bit")

    by_id = {v["candidate_id"]: v for v in bundle["vectors"]}
    empty = by_id.get("cand.imported.empty-covers")
    if empty is None:
        return fail("empty-candidate-missing")
    if empty["bits"] is None:
        return fail("empty-vector-null")
    if sum(empty["bits"]) != 0:
        return fail("empty-vector-not-zero")
    if len(empty["bits"]) != len(axis):
        return fail("empty-vector-short")

    single = by_id.get("cand.imported.single-bit")
    if single is None or sum(single["bits"]) != 1:
        return fail("single-bit-weight")
    watch_idx = axis.index("watchlist")
    if single["bits"][watch_idx] != 1:
        return fail("single-bit-wrong-axis")

    # Mutation: adding gem-hunt to the empty candidate must flip exactly one bit.
    mutant = copy.deepcopy(next(c for c in candidates if c["id"] == "cand.imported.empty-covers"))
    mutant["stages"] = [{"id": "s1", "kind": "hunt", "covers": ["gem-hunt"]}]
    mutated = vectorize(mutant, tax)
    hamming = sum(a != b for a, b in zip(empty["bits"], mutated["bits"]))
    gem_idx = axis.index("gem-hunt")
    if hamming != 1 or mutated["bits"][gem_idx] != 1:
        return fail(f"mutation-hamming={hamming} gem={mutated['bits'][gem_idx]}")

    out = {
        "probe": "probe1-vectors-complete",
        "unit_id": "IMP-0177",
        "pass": True,
        "candidate_count": bundle["candidate_count"],
        "vector_count": bundle["vector_count"],
        "null_count": bundle["null_count"],
        "axis_length": len(axis),
        "taxonomy_version": tax["version"],
        "family_count": len(families),
        "family_sizes": {k: len(v) for k, v in families.items()},
        "empty_vector_zero": True,
        "mutation_hamming": hamming,
        "spec_aligned": True,
        "guard_ok": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"vectors={bundle['vector_count']}/{bundle['candidate_count']} "
        f"nulls={bundle['null_count']} axis={len(axis)} "
        f"empty_zero=True hamming={hamming}"
    )
    print("SUCCESS:IMP-0177-probe1 coverage vectors for every candidate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
