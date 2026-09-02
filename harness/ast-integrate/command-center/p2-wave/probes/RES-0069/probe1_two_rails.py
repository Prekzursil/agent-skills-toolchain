#!/usr/bin/env python3
"""Probe 1: two mechanically independent rails per CONFIRMED claim.

Re-hashes on-disk snapshots, requires structured-api AND prose, permalink,
fetch timestamp, HTTP 200, sha256, and a load-bearing snippet. A mutant that
drops one rail from a CONFIRMED claim must go red.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evidence as E  # noqa: E402


def main() -> int:
    if not E.ART.is_file():
        print("FAILED:RES-0069-probe1 artifact missing")
        return 1
    doc = json.loads(E.ART.read_text(encoding="utf-8"))
    ok, why = E.check_two_rails(doc)
    print(f"two_rails_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0069-probe1 two-rail check failed on artifact")
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for claim in mutant["claims"]:
        if claim.get("verdict") == "CONFIRMED" and len(claim.get("rails") or []) >= 2:
            claim["rails"] = claim["rails"][:1]
            claim["source_lineage"] = claim["rails"]
            stripped = True
            break
    if not stripped:
        print("FAILED:RES-0069-probe1 no CONFIRMED dual-rail claim to mutate")
        return 1
    mok, mwhy = E.check_two_rails(mutant)
    print(f"single_rail_mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0069-probe1 single-rail mutant was accepted")
        return 1

    kinds_mutant = copy.deepcopy(doc)
    for claim in kinds_mutant["claims"]:
        if claim.get("verdict") == "CONFIRMED":
            for rail in claim.get("rails") or []:
                rail["kind"] = "prose"
            break
    kok, kwhy = E.check_two_rails(kinds_mutant)
    print(f"same_kind_mutant_ok={kok} {kwhy}")
    if kok:
        print("FAILED:RES-0069-probe1 same-kind mutant was accepted")
        return 1

    print("SUCCESS:RES-0069-probe1 two-rail evidence and mutants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
