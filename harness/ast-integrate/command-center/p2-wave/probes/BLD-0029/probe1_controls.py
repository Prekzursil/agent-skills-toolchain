#!/usr/bin/env python3
"""Probe 1: both-states controls for the two-part unknowns test."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import classify as C  # noqa: E402
import parse_register as R  # noqa: E402


def main() -> int:
    rows = {r["id"]: r for r in R.parse_file(HERE / "fixtures" / "register.md")}
    for need in ("U-VACUOUS", "U-JARGON", "U-WELL-FORMED"):
        if need not in rows:
            print(f"FAILED:BLD-0029-probe1 missing fixture {need}")
            return 1
    vac = C.classify(rows["U-VACUOUS"]["experiment"], rows["U-VACUOUS"]["impact"])
    jar = C.classify(rows["U-JARGON"]["experiment"], rows["U-JARGON"]["impact"])
    well = C.classify(
        rows["U-WELL-FORMED"]["experiment"], rows["U-WELL-FORMED"]["impact"]
    )
    if vac["named_experiment"]["pass"]:
        print("FAILED:BLD-0029-probe1 vacuous experiment passed named half")
        return 1
    if vac["named_experiment"]["reason"] != "vacuous-investigate-further":
        print(
            "FAILED:BLD-0029-probe1 expected vacuous-investigate-further "
            f"got {vac['named_experiment']['reason']}"
        )
        return 1
    if not vac["owner_visible_impact"]["pass"]:
        print("FAILED:BLD-0029-probe1 vacuous row should still pass owner half")
        return 1
    if jar["owner_visible_impact"]["pass"]:
        print("FAILED:BLD-0029-probe1 jargon impact passed owner half")
        return 1
    if not jar["named_experiment"]["pass"]:
        print(
            "FAILED:BLD-0029-probe1 jargon row should pass named half "
            f"{jar['named_experiment']}"
        )
        return 1
    if not well["pass_both"]:
        print(f"FAILED:BLD-0029-probe1 well-formed false positive {well}")
        return 1
    print(
        "vacuous_named=FAIL jargon_owner=FAIL well_formed=PASS "
        f"vac_reason={vac['named_experiment']['reason']} "
        f"jar_reason={jar['owner_visible_impact']['reason']}"
    )
    print("SUCCESS:BLD-0029-probe1 two-part controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
