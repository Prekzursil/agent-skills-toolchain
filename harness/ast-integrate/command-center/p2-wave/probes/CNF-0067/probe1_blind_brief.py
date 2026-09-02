#!/usr/bin/env python3
"""Probe 1: blind brief — no original verdict in briefs; leak control fires once."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import brief as B  # noqa: E402
import corpus as C  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0067-dedup-edge-recheck.json"


def main() -> int:
    claims = C.load_claims()
    sealed = C.load_sealed()
    pairs = C.sample_pairs(claims, sealed)
    briefs = []
    for pair in pairs:
        br = B.build_brief(pair["edge_id"], pair["left"], pair["right"])
        leaks = B.leak_keys(br)
        print(f"brief {pair['edge_id']} leaks={leaks or []}")
        if leaks:
            print(f"FAILED:CNF-0067-probe1 leak on clean brief {pair['edge_id']}")
            return 1
        briefs.append(br)

    planted = B.inject_conclusion(briefs[0], "DUPLICATE")
    planted_leaks = B.leak_keys(planted)
    print(f"control injected leaks={planted_leaks}")
    if not planted_leaks:
        print("FAILED:CNF-0067-probe1 leak detector silent on injected brief")
        return 1
    for br in briefs[1:]:
        if B.leak_keys(br):
            print(f"FAILED:CNF-0067-probe1 control leaked onto {br['edge_id']}")
            return 1

    # Detector must not be silent in both states.
    if planted_leaks and not any(B.leak_keys(b) for b in briefs):
        pass
    else:
        print("FAILED:CNF-0067-probe1 detector did not discriminate")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0067-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("brief_was_blind") is not True:
        print("FAILED:CNF-0067-probe1 artifact brief_was_blind is not true")
        return 1
    lc = doc.get("leak_control") or {}
    if lc.get("passed") is not True:
        print("FAILED:CNF-0067-probe1 artifact leak_control not passed")
        return 1
    if len(doc.get("sampled_edges") or []) != len(briefs):
        print("FAILED:CNF-0067-probe1 sample size drift")
        return 1
    print(
        f"n_briefs={len(briefs)} injected_leaks={planted_leaks} "
        "clean=0 leak_control=PASS"
    )
    print("SUCCESS:CNF-0067-probe1 blind brief + leak control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
