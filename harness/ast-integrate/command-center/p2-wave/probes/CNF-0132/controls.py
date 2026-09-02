#!/usr/bin/env python3
"""Catalog-required planted controls for CNF-0132."""
from __future__ import annotations

from graph import build, claim_rank, ranks_from_edge_list


CACHE_CLAIM = "C-CACHE-COLLAPSE"
INDEP_CLAIM = "C-SHELL-FIELD-INDEP"
THIRD_CLAIM = "C-THIRD-INDEPENDENT"
CACHE_IDS = ("planted-cache-a", "planted-cache-b")
THIRD_IDS = ("planted-third-a", "planted-third-b", "planted-third-c")


def _ok(cond: bool, detail: str) -> dict:
    return {"pass": bool(cond), "detail": detail}


def evaluate_required_tests(records: list[dict]) -> list[dict]:
    result = build(records)
    tests: list[dict] = []

    cache = claim_rank(result, CACHE_CLAIM) or {}
    tests.append(
        {
            "id": "planted-same-cache-collapses-to-rank-1",
            "name": "Two confirmations on the same cached artifact collapse to rank 1.",
            "result": "PASS"
            if cache.get("rank") == 1 and cache.get("apparent_n") == 2
            else "FAIL",
            **_ok(
                cache.get("rank") == 1 and cache.get("apparent_n") == 2,
                f"C-CACHE-COLLAPSE apparent_n={cache.get('apparent_n')} rank={cache.get('rank')}",
            ),
        }
    )

    indep = claim_rank(result, INDEP_CLAIM) or {}
    tests.append(
        {
            "id": "planted-different-shell-field-stays-rank-2",
            "name": "Two confirmations with different shells, fields, and files stay rank 2.",
            "result": "PASS"
            if indep.get("rank") == 2 and indep.get("apparent_n") == 2
            else "FAIL",
            **_ok(
                indep.get("rank") == 2 and indep.get("apparent_n") == 2,
                f"C-SHELL-FIELD-INDEP apparent_n={indep.get('apparent_n')} rank={indep.get('rank')}",
            ),
        }
    )

    assigned: list[str] = []
    for ns in result.get("partition") or []:
        assigned.extend(ns.get("record_ids") or [])
    expected = [r.get("record_id") or r.get("id") for r in records]
    partition_ok = sorted(assigned) == sorted(expected) and len(assigned) == len(
        set(assigned)
    )
    tests.append(
        {
            "id": "partition-every-record-exactly-once",
            "name": "Every confirmation record appears in exactly one node set; counts sum to total.",
            "result": "PASS" if partition_ok and result.get("partition_ok") else "FAIL",
            **_ok(
                partition_ok and result.get("partition_ok"),
                f"assigned={len(assigned)} unique={len(set(assigned))} records={len(expected)}",
            ),
        }
    )

    subset = [r for r in records if r.get("record_id") in THIRD_IDS[:2]]
    full = [r for r in records if r.get("record_id") in THIRD_IDS]
    rank_2 = (claim_rank(build(subset), THIRD_CLAIM) or {}).get("rank")
    rank_3 = (claim_rank(build(full), THIRD_CLAIM) or {}).get("rank")
    cache_naive = 2
    cache_rank = cache.get("rank")
    not_a_counter = cache_rank != cache_naive
    tests.append(
        {
            "id": "regression-third-independent-raises-rank-to-3",
            "name": (
                "Adding a third genuinely independent probe raises rank to 3 "
                "and is not a naive confirmation counter (same-cache stays rank 1)."
            ),
            "result": "PASS"
            if rank_2 == 2 and rank_3 == 3 and not_a_counter
            else "FAIL",
            **_ok(
                rank_2 == 2 and rank_3 == 3 and not_a_counter,
                f"subset_rank={rank_2} full_rank={rank_3} cache_rank={cache_rank} naive_cache={cache_naive}",
            ),
        }
    )

    recomputed = ranks_from_edge_list(result["edges"], records)
    mismatches = []
    for row in result.get("per_claim") or []:
        cid = row["claim_id"]
        alt = recomputed.get(cid)
        alt_rank = 0 if alt is None else alt.get("rank")
        if alt_rank != row.get("rank"):
            mismatches.append((cid, row.get("rank"), alt_rank))
    tests.append(
        {
            "id": "edge-list-recompute-agrees",
            "name": "DFS-from-edges rank agrees with union-find rank for every claim.",
            "result": "PASS" if not mismatches else "FAIL",
            **_ok(not mismatches, f"mismatches={mismatches!r}"),
        }
    )
    return tests
