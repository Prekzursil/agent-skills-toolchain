#!/usr/bin/env python3
"""Probe 1: constructed 3-cycle; declared vs swapped completion change the winner.

Signal 1 is Floyd-Warshall Schulze plus plurality-in-Smith on the same ballots
(tabulate.py). The catalog load-bearing test is that the two winners differ.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from tabulate import (  # noqa: E402
    DECLARED_COMPLETION,
    SWAP_COMPLETION,
    freeze_spec,
    ingest_and_tabulate,
    rebind_after_ingest,
    tabulate_with_rule,
)

ART = (
    REPO
    / "command-center/design/council/CNL-0063-pairwise-condorcet-tabulation-and-the-cycle-rule.md"
)
FIX = HERE / "fixtures.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0063-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNL-0063-probe1 unparseable:{type(exc).__name__}")
        return 1
    if doc.get("unit_id") != "CNL-0063":
        print("FAILED:CNL-0063-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNL-0063" not in text:
        print("FAILED:CNL-0063-probe1 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNL-0063-probe1 self-declared", doc.get("state"))
        return 1

    fx = json.loads(FIX.read_text(encoding="utf-8"))
    cands = fx["candidate_order"]
    ballots = fx["cycle_profile"]["ballots"]
    spec = freeze_spec(DECLARED_COMPLETION, cands)
    declared = ingest_and_tabulate(spec, ballots)
    swapped = tabulate_with_rule(cands, ballots, SWAP_COMPLETION)
    posthoc = rebind_after_ingest(spec, SWAP_COMPLETION)

    print(
        "CYCLE pairwise "
        f"A>B={declared['pairwise']['A']['B']}-"
        f"{declared['pairwise']['B']['A']} "
        f"B>C={declared['pairwise']['B']['C']}-"
        f"{declared['pairwise']['C']['B']} "
        f"C>A={declared['pairwise']['C']['A']}-"
        f"{declared['pairwise']['A']['C']}"
    )
    print(
        f"CYCLE smith={declared['smith_set']} "
        f"condorcet_winner={declared['condorcet_winner']!r} "
        f"cycle_detected={declared['cycle_detected']}"
    )
    print(
        f"DECLARED rule={DECLARED_COMPLETION} winner={declared['winner']} "
        f"completion_used={declared['completion_used']}"
    )
    print(
        f"SWAP rule={SWAP_COMPLETION} winner={swapped['winner']} "
        f"completion_used={swapped['completion_used']}"
    )
    print(f"LOAD_BEARING winners_differ={declared['winner'] != swapped['winner']}")
    print(
        f"POSTHOC ok={posthoc['ok']} reason={posthoc['reason']} "
        f"rejected={posthoc.get('rejected')}"
    )

    if not declared["cycle_detected"] or declared["condorcet_winner"] is not None:
        print("FAILED:CNL-0063-probe1 constructed cycle not detected")
        return 1
    if declared["winner"] == swapped["winner"]:
        print("FAILED:CNL-0063-probe1 swap did not change winner")
        return 1
    if declared["winner"] != "B" or swapped["winner"] != "A":
        print(
            "FAILED:CNL-0063-probe1 unexpected winners "
            f"declared={declared['winner']} swap={swapped['winner']}"
        )
        return 1
    if posthoc.get("ok") is not False:
        print("FAILED:CNL-0063-probe1 post-hoc rebind was allowed")
        return 1

    measured = doc.get("measured_cycle") or {}
    if measured.get("declared_winner") != declared["winner"]:
        print("FAILED:CNL-0063-probe1 artifact declared_winner mismatch")
        return 1
    if measured.get("swap_winner") != swapped["winner"]:
        print("FAILED:CNL-0063-probe1 artifact swap_winner mismatch")
        return 1
    if measured.get("pairwise") != declared["pairwise"]:
        print("FAILED:CNL-0063-probe1 artifact pairwise mismatch")
        return 1
    if doc.get("freeze_contract", {}).get("token") != spec["freeze_token"]:
        print("FAILED:CNL-0063-probe1 freeze token mismatch")
        return 1

    print("SUCCESS:CNL-0063-probe1 constructed 3-cycle load-bearing completion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
