#!/usr/bin/env python3
"""Probe 2: distinctness floor is computed; clone tournament drops it (both states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from compare import build_analysis, distinctness_floor, similarity_view  # noqa: E402


def main() -> int:
    analysis = build_analysis()
    live = analysis["distinctness_floor"]
    clone = analysis["clone_tournament_floor"]
    pairs = analysis["pairs"]
    recomputed = distinctness_floor(pairs)
    print(
        f"live_floor={live['floor']} pair={live['floor_pair']} "
        f"jaccard={live['floor_jaccard']} cosine={live['floor_cosine']}"
    )
    print(f"clone_floor={clone['floor']} pair_count={clone['pair_count']}")
    print(f"recomputed_floor={recomputed['floor']}")
    print(f"duplicates={len(analysis['duplicates'])} contested={len(analysis['contested'])}")
    if live["floor"] is None:
        print("FAILED:ARC-0072-probe2 live floor missing")
        return 1
    if abs(live["floor"] - recomputed["floor"]) > 1e-9:
        print("FAILED:ARC-0072-probe2 floor is not min of pairwise distances")
        return 1
    if clone["floor"] is None or clone["floor"] >= live["floor"]:
        print("FAILED:ARC-0072-probe2 clone tournament did not drop the floor")
        return 1
    if clone["floor"] > 0.08:
        print("FAILED:ARC-0072-probe2 clone floor not near zero")
        return 1
    art = HERE.parents[3] / "command-center/phase3/ARCH-SIMILARITY.json"
    if art.is_file():
        doc = json.loads(art.read_text(encoding="utf-8"))
        rec = similarity_view(doc).get("distinctness_floor") or {}
        if rec.get("floor") != live["floor"]:
            print("FAILED:ARC-0072-probe2 artifact floor mismatch")
            return 1
        print("artifact_agrees=true")
    # Shared mechanisms enumerated on every DUPLICATE/CONTESTED pair.
    for row in analysis["duplicates"] + analysis["contested"]:
        if row["shared_mechanism_count"] < 1 and row["class"] == "DUPLICATE":
            print(f"FAILED:ARC-0072-probe2 duplicate {row['left']}/{row['right']} has no shared statements")
            return 1
    print("SUCCESS:ARC-0072-probe2 distinctness-floor both-states clone-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
