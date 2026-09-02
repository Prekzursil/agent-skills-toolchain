#!/usr/bin/env python3
"""Probe 1: both-states control for proof_of_impossibility discharge.

Incomplete search must fail to qualify as proof; exhaustive enumeration must
pass. Re-runs the live detector and checks the design-note artifact recorded
the same classifications.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import proof as P  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0073-proof-of-impossibility-what-actually-constitutes-proof.md"
)


def main() -> int:
    live = P.both_states()
    print(json.dumps({k: live[k] for k in ("both_directions_ok", "luck_unread_clean")}, sort_keys=True))
    print(live["negative_control"]["verbatim"])
    if not live["both_directions_ok"]:
        print("FAILED:CNL-0073-probe1 live both-states failed")
        return 1
    inc = live["incomplete_luck"]
    exh = live["exhaustive"]
    if inc["qualifies"] or inc["classification"] != P.TERM_SEARCH:
        print("FAILED:CNL-0073-probe1 incomplete-luck was accepted as proof")
        return 1
    if not exh["qualifies"] or exh["classification"] != P.TERM_PROOF:
        print("FAILED:CNL-0073-probe1 exhaustive did not discharge")
        return 1
    if inc["omniscient_witness_in_unvisited"]:
        print("FAILED:CNL-0073-probe1 luck fixture is not luck (unread has WITNESS)")
        return 1
    if live["incomplete_missed"]["omniscient_witness_in_unvisited"] is not True:
        print("FAILED:CNL-0073-probe1 missed fixture has no unread WITNESS")
        return 1
    if live["gave_up"]["classification"] == exh["classification"]:
        print("FAILED:CNL-0073-probe1 gave-up shares proof classification")
        return 1
    if not ART.is_file():
        print("FAILED:CNL-0073-probe1 design note missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0073-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNL-0073" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0073-probe1 sentinel absent")
        return 1
    rec = doc.get("both_states") or {}
    if rec.get("incomplete_classification") != P.TERM_SEARCH:
        print("FAILED:CNL-0073-probe1 artifact incomplete classification mismatch")
        return 1
    if rec.get("exhaustive_classification") != P.TERM_PROOF:
        print("FAILED:CNL-0073-probe1 artifact exhaustive classification mismatch")
        return 1
    if rec.get("incomplete_qualifies") is not False:
        print("FAILED:CNL-0073-probe1 artifact accepted incomplete as proof")
        return 1
    if rec.get("exhaustive_qualifies") is not True:
        print("FAILED:CNL-0073-probe1 artifact did not accept exhaustive")
        return 1
    if rec.get("incomplete_unvisited_count") != inc["unvisited_count"]:
        print("FAILED:CNL-0073-probe1 artifact unvisited count != live")
        return 1
    nc = (doc.get("negative_controls") or [{}])[0]
    if "UNSUCCESSFUL_SEARCH" not in str(nc.get("verbatim") or ""):
        print("FAILED:CNL-0073-probe1 negative control verbatim missing")
        return 1
    print(
        "incomplete_qualifies=False exhaustive_qualifies=True "
        f"unvisited={inc['unvisited_count']} gave_up={live['gave_up']['classification']}"
    )
    print("SUCCESS:CNL-0073-probe1 both-states exhaustive vs unsuccessful-search")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
