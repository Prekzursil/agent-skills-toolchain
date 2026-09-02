#!/usr/bin/env python3
"""Probe 2: ranking reconstructs from the archived pairwise matrix alone.

Does not re-score workflows. A fabricated total order that breaks ties by
workflow id must not match the honest ranking whenever a tied group exists.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center"))

from workflow_tournament import (  # noqa: E402
    CORPUS_ID,
    fabricated_total_order,
    matched_corpus,
    rank_from_matrix_archive,
    run_round_robin,
    scorers,
)
from workflow_tournament.engine import rank_map  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0200.json"


def _rank_tuple(ranking) -> list[tuple[int, str]]:
    return [(int(r.rank), r.workflow_id) for r in ranking]


def main() -> int:
    tour = run_round_robin(scorers(), matched_corpus(), corpus_id=CORPUS_ID)
    archive = tour.matrix_archive()
    expected_pairs = len(tour.candidates) * (len(tour.candidates) - 1) // 2
    if len(archive["pairs"]) != expected_pairs:
        print(
            f"FAILED:IMP-0200-probe2 pair_count={len(archive['pairs'])} "
            f"expected={expected_pairs}"
        )
        return 1
    if archive.get("forced_total_order") is True:
        print("FAILED:IMP-0200-probe2 fixture lost the injected tie")
        return 1

    reconstructed, groups, forced = rank_from_matrix_archive(archive)
    live_map = rank_map(tour.ranking)
    rec_map = rank_map(reconstructed)
    if live_map != rec_map:
        print("FAILED:IMP-0200-probe2 reconstructed ranks != live ranks")
        print(json.dumps({"live": live_map, "reconstructed": rec_map}, sort_keys=True))
        return 1

    tied = [g for g in groups if len(g) > 1]
    if not tied:
        print("FAILED:IMP-0200-probe2 no tied group in reconstructed ranking")
        return 1

    fab = fabricated_total_order(archive)
    fab_map = {row["workflow_id"]: row["rank"] for row in fab}
    if fab_map == rec_map:
        print("FAILED:IMP-0200-probe2 fabricated total order collapsed onto honest ranks")
        return 1
    # Fabricated assigns unique ranks; honest shares a rank inside the tie.
    if len(set(fab_map.values())) != len(fab_map):
        print("FAILED:IMP-0200-probe2 fabricated order did not force unique ranks")
        return 1
    honest_unique = len(set(rec_map.values())) < len(rec_map)
    if not honest_unique:
        print("FAILED:IMP-0200-probe2 honest ranking has no shared rank")
        return 1

    payload = {
        "pair_count": len(archive["pairs"]),
        "forced_total_order": forced,
        "tied_groups": groups,
        "honest_ranks": rec_map,
        "fabricated_ranks": fab_map,
        "reconstructed_matches_live": True,
    }

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        matrix = (doc.get("pairwise_matrix") or doc.get("tournament") or {}).get(
            "pairs"
        )
        if matrix is None:
            tm = doc.get("tournament") or {}
            matrix = (tm.get("pairwise_matrix") or {}).get("pairs")
        if not matrix:
            print("FAILED:IMP-0200-probe2 receipt pairwise matrix missing")
            return 1
        if len(matrix) != expected_pairs:
            print(
                f"FAILED:IMP-0200-probe2 receipt pairs={len(matrix)} "
                f"expected={expected_pairs}"
            )
            return 1
        # Reconstruct from the *receipt* archive, not the in-memory rerun.
        receipt_archive = {
            "candidates": (doc.get("tournament") or {}).get("candidates")
            or archive["candidates"],
            "pairs": matrix,
        }
        # Receipt may store full matrix_archive
        if isinstance(doc.get("pairwise_matrix"), dict) and "pairs" in doc["pairwise_matrix"]:
            receipt_archive = {
                "candidates": doc["pairwise_matrix"].get("candidates") or archive["candidates"],
                "pairs": doc["pairwise_matrix"]["pairs"],
            }
        r2, g2, _ = rank_from_matrix_archive(receipt_archive)
        if rank_map(r2) != rec_map:
            print("FAILED:IMP-0200-probe2 receipt matrix reconstructs a different ranking")
            return 1
        payload["receipt_matrix_pairs"] = len(matrix)
        payload["receipt_reconstructed"] = True

    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0200-probe2 ranking reconstructs from pairwise matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
