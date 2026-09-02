#!/usr/bin/env python3
"""Named probe 1: mutation campaign (evidence A).

Every hop × {delete, empty-string} × {provenance_anchor, licence_class}
must be caught by the named hop gate. A survivor is a P1 hole.
Empty-string is treated identically to missing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from campaign import MUTATIONS, run_campaign  # noqa: E402
from carry import ANCHOR_KEY, HOPS, LICENCE_KEY  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:WFA-0122-probe1 {msg}")
    return 1


def main() -> int:
    result = run_campaign()
    print(
        json.dumps(
            {
                "mutant_count": result["mutant_count"],
                "expected_count": result["expected_count"],
                "surviving_mutants": result["surviving_mutants"],
                "p1_hole": result["p1_hole"],
                "empty_string_equivalent_to_missing": result[
                    "empty_string_equivalent_to_missing"
                ],
                "licence_and_anchor_both_covered": result[
                    "licence_and_anchor_both_covered"
                ],
                "hops_covered": result["hops_covered"],
                "catching_gates": sorted(
                    {r["catching_gate"] for r in result["rows"] if r["catching_gate"]}
                ),
            },
            sort_keys=True,
        )
    )
    expected = len(HOPS) * len(MUTATIONS)
    if result["mutant_count"] != expected:
        return _fail(f"mutant_count={result['mutant_count']} want={expected}")
    if result["p1_hole"] or result["surviving_mutants"]:
        return _fail(f"P1 hole survivors={result['surviving_mutants']}")
    if not result["empty_string_equivalent_to_missing"]:
        return _fail("empty-string not treated identically to missing")
    if not result["licence_and_anchor_both_covered"]:
        return _fail("mutation set did not cover both licence_class and provenance_anchor")
    if result["hops_covered"] != list(HOPS):
        return _fail(f"hops_covered={result['hops_covered']}")
    for row in result["rows"]:
        if not row["caught_expected_field"]:
            return _fail(f"{row['mutant_id']} did not name lost field {row['field']}")
        if row["catching_gate"] is None:
            return _fail(f"{row['mutant_id']} unnamed catching gate")
        if row["field"] not in {ANCHOR_KEY, LICENCE_KEY}:
            return _fail(f"unexpected field {row['field']}")
    print("SUCCESS:WFA-0122-probe1 mutation campaign: 24/24 caught, empty≡missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
