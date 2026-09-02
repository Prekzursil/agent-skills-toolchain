#!/usr/bin/env python3
"""Probe 1: >=10 seeded permutations, outcome matrix, bisection to minimal pairs.

Evidence: every failing permutation is named; each failure bisects to a
minimal ordered pair classified as shared-state leakage. Shuffle must
actually reorder. A 3-permutation all-pass window is labelled WEAK.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    EXPECTED_PAIRS,
    PERM_SEEDS,
    PLANT_READER,
    PLANT_VICTIM,
    RunConfig,
    run_campaign,
)

UNIT = "TST-0344"


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def main() -> int:
    report = run_campaign(RunConfig(seeds=PERM_SEEDS, plants=True, isolate_per_test=False))
    payload = {
        "probe": "probe1-permutations-and-bisect",
        "unit_id": UNIT,
        "n_permutations": report["n_permutations"],
        "seeds": report["seeds"],
        "distinct_orders": report["distinct_orders"],
        "shuffle_moved": report["shuffle_moved"],
        "same_seed_shuffle_identical": report["same_seed_shuffle_identical"],
        "same_seed_matrix_identical": report["same_seed_matrix_identical"],
        "varying_tests": report["varying_tests"],
        "failing_permutation_count": len(report["failing_permutations"]),
        "failing_permutations": [
            {"seed": p["seed"], "failed": p["failed"]}
            for p in report["failing_permutations"]
        ],
        "minimal_pairs": report["minimal_pairs"],
        "relative_order_pairs": report["relative_order_pairs"],
        "expected_planted_pairs": report["expected_planted_pairs"],
        "evidence_strength": report["evidence_strength"],
        "three_permutation_rule": report["three_permutation_rule"],
        "weak_windows": [w for w in report["three_perm_windows"] if w["strength"] == "WEAK"],
        "matrix_sha256": report["matrix_sha256"],
        "bisection_count": len(report["bisections"]),
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))

    if report["n_permutations"] < 10:
        return fail(f"need >=10 permutations, got {report['n_permutations']}")
    if report["evidence_strength"] != "ADEQUATE":
        return fail(f"evidence_strength={report['evidence_strength']}")
    if not report["shuffle_moved"]:
        return fail("shuffle did not reorder; green would be vacuous")
    if report["distinct_orders"] < 2:
        return fail("all seeds produced the same order")
    if not report["same_seed_shuffle_identical"]:
        return fail("same shuffle seed replayed a different order (detector failure)")
    if report["same_seed_matrix_identical"] is not True:
        return fail("same seeds produced a different outcome matrix (detector failure)")
    if not report["failing_permutations"]:
        return fail("no failing permutation; planted control did not surface")
    if PLANT_READER not in report["varying_tests"]:
        return fail(f"planted reader not varying: {report['varying_tests']}")
    if PLANT_VICTIM not in report["varying_tests"]:
        return fail(f"planted victim not varying: {report['varying_tests']}")

    unresolved = [
        b
        for b in report["bisections"]
        if not b.get("pair") or str(b.get("kind") or "").endswith("unresolved")
    ]
    if unresolved:
        return fail("bisection left an unresolved failure", unresolved[:4])

    for b in report["bisections"]:
        if b.get("classification") != "shared-state-leakage":
            return fail("failure classified as something other than leakage", b)
        if not b.get("not_flake"):
            return fail("bisection did not mark not_flake", b)

    for a, b, kind in EXPECTED_PAIRS:
        if [a, b] not in report["minimal_pairs"]:
            return fail(f"expected pair {(a, b, kind)} missing from bisection", report["minimal_pairs"])
        rel = [r for r in report["relative_order_pairs"] if r.get("pair") == [a, b]]
        if not rel:
            return fail(f"relative-order confirmation missed {(a, b)}")
        if rel[0].get("kind") != kind:
            return fail(f"pair kind {rel[0].get('kind')} != {kind}", rel[0])

    if not report["planted_pairs_all_found"]:
        return fail("planted pairs not all found", report["expected_planted_pairs"])

    # Explicit label: any 3-perm all-pass window is WEAK (rule is live, not a comment).
    weak = [w for w in report["three_perm_windows"] if w["all_pass"]]
    print(
        f"perms={report['n_permutations']} failing={len(report['failing_permutations'])} "
        f"pairs={report['minimal_pairs']} weak_3perm_windows={len(weak)} "
        f"matrix={report['matrix_sha256'][:16]}"
    )
    print(
        f"SUCCESS:{UNIT}-probe1 "
        f"{report['n_permutations']} permutations, "
        f"{len(report['failing_permutations'])} failing, "
        f"pairs={report['minimal_pairs']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
