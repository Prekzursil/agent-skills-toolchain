#!/usr/bin/env python3
"""Probe 1: executable distinctness — pair count, nearest-neighbour list, floor."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import catalog as C  # noqa: E402
import distinctness as D  # noqa: E402

FLOOR = 64


def main() -> int:
    corpus = C.load_corpus()
    protocols = corpus["protocols"]
    presets = corpus["presets"]
    if len(protocols) != 58:
        print(f"FAILED:CNL-0102-probe1 protocol_count={len(protocols)}")
        return 1
    if len(presets) != 72:
        print(f"FAILED:CNL-0102-probe1 preset_count={len(presets)}")
        return 1
    if not corpus["id_spaces_disjoint"]:
        print("FAILED:CNL-0102-probe1 protocol/preset id spaces intersect")
        return 1
    bound = {pid for p in presets for pid in p["bound_protocols"]}
    known = {p["id"] for p in protocols}
    unknown = sorted(bound - known)
    if unknown:
        print(f"FAILED:CNL-0102-probe1 unbound protocol ids {unknown}")
        return 1

    report = D.analyse(presets)
    if report["pair_count"] != D.pair_count(72):
        print("FAILED:CNL-0102-probe1 pair_count arithmetic")
        return 1
    if report["pair_count"] != 2556:
        print(f"FAILED:CNL-0102-probe1 pair_count={report['pair_count']}")
        return 1
    if report["distinct_signature_count"] < FLOOR:
        print(
            "FAILED:CNL-0102-probe1 floor "
            f"{report['distinct_signature_count']} < {FLOOR}"
        )
        return 1
    if report["below_threshold_pair_count"] < 1:
        print("FAILED:CNL-0102-probe1 expected named below-threshold pairs")
        return 1
    named = {(r["left"], r["right"]) for r in report["below_threshold_pairs"]}
    if ("C01", "C72") not in named or ("C25", "C71") not in named:
        print(f"FAILED:CNL-0102-probe1 missing clone pairs {named}")
        return 1
    if len(report["nearest_neighbours"]) != 72:
        print("FAILED:CNL-0102-probe1 nn list length")
        return 1
    c01_nn = next(r for r in report["nearest_neighbours"] if r["id"] == "C01")
    if c01_nn["neighbour_id"] != "C72" or not c01_nn["same_signature"]:
        print(f"FAILED:CNL-0102-probe1 C01 neighbour {c01_nn}")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-distinctness",
                "protocol_count": 58,
                "preset_count": 72,
                "pair_count": report["pair_count"],
                "distinct_signature_count": report["distinct_signature_count"],
                "floor": FLOOR,
                "floor_met": report["floor_met"],
                "below_threshold_pair_count": report["below_threshold_pair_count"],
                "below_threshold_pairs": [
                    f"{r['left']}+{r['right']}->{r['surviving_id']}"
                    for r in report["below_threshold_pairs"]
                ],
                "nearest_neighbours_head": report["nearest_neighbours"][:4],
                "id_spaces_disjoint": True,
                "original_library_present": corpus["original_library_present"],
            },
            sort_keys=True,
        )
    )
    print(
        f"pair_count={report['pair_count']} "
        f"distinct={report['distinct_signature_count']} "
        f"below_threshold={report['below_threshold_pair_count']} "
        f"floor_met={report['floor_met']}"
    )
    print("SUCCESS:CNL-0102-probe1 distinctness pair-count and nearest-neighbour list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
