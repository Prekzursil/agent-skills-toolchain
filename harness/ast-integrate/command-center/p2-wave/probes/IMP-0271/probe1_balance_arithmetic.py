#!/usr/bin/env python3
"""Probe 1: balance arithmetic across 5 class mixes.

Independently counts seated classes from the roster and compares them
to the fixture's hand-computed expected_seats. Mix 5 is unfillable:
the unfilled-class report must name regulator.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import fixtures as F  # noqa: E402
from council.participants.select_stakeholder import (  # noqa: E402
    STAKEHOLDER_CLASSES,
    census_check,
    select,
)

UNIT = "IMP-0271"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def count_classes(seats: list[dict]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for seat in seats:
        c[str(seat["stakeholder_class"])] += 1
    return {name: int(c.get(name, 0)) for name in STAKEHOLDER_CLASSES}


def main() -> int:
    pool = F.candidate_pool()
    mixes = F.mixes()
    if len(mixes) != 5:
        return fail(f"expected 5 mixes, got {len(mixes)}")

    rows: list[dict] = []
    for mix in mixes:
        run = F.run_mix(select, pool, mix)
        counted = count_classes(run["seats"])
        expected = mix["expected_seats"]
        check = census_check(run)
        row = {
            "id": mix["id"],
            "kind": mix["kind"],
            "fillable": mix["fillable"],
            "counted": counted,
            "expected": expected,
            "match": counted == expected,
            "unfilled_report": run["unfilled_report"],
            "census_check_ok": check["ok"],
            "census_check_reason": check["reason"],
            "roster_len": len(run["roster"]),
        }
        rows.append(row)
        if counted != expected:
            return fail(
                f"{mix['id']} counted={counted} expected={expected}"
            )
        if mix["fillable"] and not check["ok"]:
            return fail(f"{mix['id']} fillable mix failed census_check: {check}")
        if mix["fillable"] and run["unfilled_report"]:
            return fail(f"{mix['id']} fillable mix emitted unfilled_report")
        if mix["fillable"] and run["under_represented"]:
            return fail(f"{mix['id']} fillable mix marked under_represented")
        if not mix["fillable"]:
            names = [r["stakeholder_class"] for r in run["unfilled_report"]]
            if names != mix["expected_unfilled"]:
                return fail(
                    f"{mix['id']} unfilled={names} "
                    f"expected={mix['expected_unfilled']}"
                )
            if not check["ok"]:
                return fail(f"{mix['id']} honest unfilled run failed census_check")
            short = run["unfilled_report"][0]["shortfall"]
            if short != mix["expected_shortfall"]["regulator"]:
                return fail(f"{mix['id']} shortfall={short}")

    # Cross-class substitution must not have occurred: no class exceeds request.
    unfill = next(r for r in rows if r["id"] == "unfillable-regulator")
    if unfill["counted"]["regulator"] != 1:
        return fail("unfillable mix substituted another class for regulator")

    payload = {
        "probe": "probe1-balance-arithmetic",
        "unit_id": UNIT,
        "mix_count": len(rows),
        "rows": rows,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "mixes=5 all_counted_match=True unfilled_named=['regulator'] "
        "honest_census_ok=True"
    )
    print("SUCCESS:IMP-0271-probe1 balance arithmetic across 5 class mixes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
