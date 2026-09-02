#!/usr/bin/env python3
"""Probe 2: fabricated citations must not satisfy the gate.

Independent of probe 1's tempfile. Independently os.stat's the planted
missing paths. Shows each fabricated cite LOOKS plausible, then asserts
the live gate still leaves it unresolved.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import fixtures as F  # noqa: E402
from council.vote.evidence_gate import (  # noqa: E402
    BLOCK_EVIDENCE_FREE_MAJORITY,
    anchor_resolution_pass,
    citation_looks_plausible,
    evaluate_gate,
    resolve_citation,
)

UNIT = "IMP-0307"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    root = F.EVIDENCE
    ballots = F.fabricated_majority_real_minority()
    result = evaluate_gate(ballots, F.GRAPH, root)
    census = anchor_resolution_pass(ballots, F.GRAPH, root)

    independent_missing = []
    for path in F.fabricated_paths_must_be_absent():
        exists = path.exists()
        independent_missing.append(
            {"path": str(path), "exists": exists, "independent_stat": "absent"}
        )
        if exists:
            return fail(f"fabricated path exists on disk: {path}")
        try:
            os.stat(path)
            return fail(f"independent stat unexpectedly succeeded: {path}")
        except FileNotFoundError:
            pass

    per_cite = []
    for cite in F.FABRICATED:
        res = resolve_citation(cite, F.GRAPH, root)
        looks = citation_looks_plausible(cite)
        per_cite.append(
            {
                "citation": cite,
                "looks_plausible": looks,
                "resolved": res.resolved,
                "method": res.method,
                "error": res.error,
            }
        )
        if not looks:
            return fail(f"fixture cite is not plausible (bad fixture): {cite}")
        if res.resolved:
            return fail(f"fabricated citation resolved: {cite}")

    if result.plausible_heuristic_consulted:
        return fail("gate consulted citation_looks_plausible")
    if result.raw_winner != "ship-it":
        return fail(f"raw winner {result.raw_winner!r}")
    if result.raw_tally.get("ship-it") != 7:
        return fail(f"raw majority size {result.raw_tally}")
    if result.backed_tally.get("ship-it", 0) != 0:
        return fail("fabricated majority counted as backed")
    if result.backed_tally.get("hold") != 2:
        return fail("well-anchored minority not counted under fabricated majority")
    if result.well_anchored_minority_blocked:
        return fail("well-anchored minority blocked")
    if not result.evidence_free_majority_blocked:
        return fail("fabricated majority was allowed to bind as majority")
    if result.gated_winner != "hold":
        return fail(f"gated winner {result.gated_winner!r} != hold")
    if result.reason != BLOCK_EVIDENCE_FREE_MAJORITY:
        return fail(f"reason {result.reason}")
    if census["resolved_count"] != 2:
        return fail(f"resolved_count={census['resolved_count']} (want 2 real)")
    caught = set(result.fabricated_caught)
    for cite in F.FABRICATED:
        if cite not in caught and cite not in result.unresolved:
            return fail(f"fabricated cite not listed unresolved: {cite}")

    # file:// fabricated URI must take the fetch path then fail stat.
    file_cite = [c for c in F.FABRICATED if c.startswith("file://")][0]
    file_res = resolve_citation(file_cite, F.GRAPH, root)
    if file_res.resolved:
        return fail("file:// fabricated URI resolved")
    https_cite = [c for c in F.FABRICATED if c.startswith("https://")][0]
    https_res = resolve_citation(https_cite, F.GRAPH, root)
    if https_res.resolved:
        return fail("https DOI-shaped cite resolved")
    if https_res.method != "no-fetch-hermetic":
        return fail(f"https method {https_res.method}")

    payload = {
        "pass": True,
        "probe": "probe2-fabricated-citation",
        "unit_id": UNIT,
        "gate": result.to_dict(),
        "anchor_resolution_pass": {
            "cited_count": census["cited_count"],
            "resolved_count": census["resolved_count"],
            "unresolved_count": census["unresolved_count"],
            "unresolved": census["unresolved"],
        },
        "fabricated": per_cite,
        "independent_missing": independent_missing,
        "plausible_heuristic_consulted_by_gate": result.plausible_heuristic_consulted,
        "fabricated_any_resolved": False,
        "well_anchored_minority_blocked": result.well_anchored_minority_blocked,
        "gated_winner": result.gated_winner,
        "evidence_free_majority_blocked": result.evidence_free_majority_blocked,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "fabricated_any_resolved=False minority_blocked={mb} "
        "gated={gated} independent_stat_missing=True".format(
            mb=result.well_anchored_minority_blocked,
            gated=result.gated_winner,
        )
    )
    print(
        f"SUCCESS:{UNIT}-probe2 fabricated citations unresolved; "
        "well-anchored minority not blocked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
