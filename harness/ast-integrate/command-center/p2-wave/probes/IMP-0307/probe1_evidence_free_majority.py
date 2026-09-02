#!/usr/bin/env python3
"""Probe 1: evidence-free majority is blocked; well-anchored minority is not.

Both-states: when every ballot is backed, ordinary plurality decides
(the gate does not invert a fully-evidenced vote).
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
    BIND_BACKED_TALLY,
    BLOCK_EVIDENCE_FREE_MAJORITY,
    POLICY,
    anchor_resolution_pass,
    evaluate_gate,
)

UNIT = "IMP-0307"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    root = F.EVIDENCE
    if not (root / "node-hold-1.json").is_file():
        return fail("real evidence fixture missing")

    mixed = evaluate_gate(F.majority_unbacked_minority_backed(), F.GRAPH, root)
    all_backed = evaluate_gate(F.all_ballots_backed(), F.GRAPH, root)
    census = anchor_resolution_pass(
        F.majority_unbacked_minority_backed(), F.GRAPH, root
    )

    if mixed.plausible_heuristic_consulted:
        return fail("evaluate_gate consulted citation_looks_plausible")
    if not mixed.policy.get("agreement_is_not_proof"):
        return fail("POLICY.agreement_is_not_proof missing from result")
    if mixed.raw_winner != "ship-it":
        return fail(f"raw winner {mixed.raw_winner!r} != ship-it")
    if mixed.raw_tally.get("ship-it") != 7 or mixed.raw_tally.get("hold") != 2:
        return fail(f"raw tally {mixed.raw_tally}")
    if mixed.backed_tally.get("ship-it", 0) != 0:
        return fail("unbacked majority leaked into backed tally")
    if mixed.backed_tally.get("hold") != 2:
        return fail("well-anchored minority was not counted")
    if mixed.well_anchored_minority_blocked:
        return fail("well-anchored minority was blocked")
    if "hold" not in mixed.well_anchored_positions:
        return fail("hold missing from well_anchored_positions")
    if not mixed.evidence_free_majority_blocked:
        return fail("evidence-free majority was not blocked")
    if mixed.gated_winner != "hold":
        return fail(f"gated winner {mixed.gated_winner!r} != hold")
    if mixed.reason != BLOCK_EVIDENCE_FREE_MAJORITY:
        return fail(f"reason {mixed.reason}")
    if not mixed.binding:
        return fail("backed minority did not produce a binding gated winner")
    if census["resolved_count"] != 2:
        return fail(f"expected 2 resolved anchors, got {census['resolved_count']}")
    if census["unresolved_count"] < 7:
        return fail("unbacked majority citations were not listed unresolved")

    # Both-states: fully backed ballots follow ordinary plurality.
    if all_backed.raw_winner != "ship-it":
        return fail("all-backed raw winner drifted")
    if all_backed.gated_winner != all_backed.raw_winner:
        return fail("all-backed: gate inverted ordinary tally")
    if all_backed.evidence_free_majority_blocked:
        return fail("all-backed majority was treated as evidence-free")
    if all_backed.reason != BIND_BACKED_TALLY:
        return fail(f"all-backed reason {all_backed.reason}")
    if all_backed.backed_tally.get("hold") != 2:
        return fail("all-backed minority was dropped")
    if all_backed.well_anchored_minority_blocked:
        return fail("all-backed minority blocked")
    if all_backed.plausible_heuristic_consulted:
        return fail("all-backed consulted heuristic")

    # Independent stat of the two real minority files.
    for name in ("node-hold-1.json", "node-hold-2.json"):
        st = os.stat(root / name)
        if st.st_size <= 0:
            return fail(f"{name} independently stats empty")

    payload = {
        "pass": True,
        "probe": "probe1-evidence-free-majority",
        "unit_id": UNIT,
        "mixed": mixed.to_dict(),
        "all_backed": all_backed.to_dict(),
        "anchor_resolution_pass": {
            "cited_count": census["cited_count"],
            "resolved_count": census["resolved_count"],
            "unresolved_count": census["unresolved_count"],
            "unresolved": census["unresolved"],
        },
        "policy_explicit": dict(POLICY),
        "plausible_heuristic_consulted": mixed.plausible_heuristic_consulted,
        "evidence_free_majority_blocked": mixed.evidence_free_majority_blocked,
        "well_anchored_minority_blocked": mixed.well_anchored_minority_blocked,
        "gated_winner": mixed.gated_winner,
        "all_backed_raw_equals_gated": all_backed.gated_winner
        == all_backed.raw_winner,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "mixed blocked={blocked} gated={gated} all_backed_equal={eq} "
        "minority_blocked={mb}".format(
            blocked=mixed.evidence_free_majority_blocked,
            gated=mixed.gated_winner,
            eq=all_backed.gated_winner == all_backed.raw_winner,
            mb=mixed.well_anchored_minority_blocked,
        )
    )
    print(
        f"SUCCESS:{UNIT}-probe1 evidence-free majority blocked; "
        "well-anchored minority not blocked; all-backed tally preserved"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
