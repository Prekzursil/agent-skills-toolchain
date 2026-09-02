#!/usr/bin/env python3
"""Named probe 1: re-derive repeat-application hash equality for both directions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import report_payload, run_suite  # noqa: E402
from lifecycle import PAIRS  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0036-repeat-application.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"


def catalog_sentinel() -> str:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "CNF-0036":
            return str(unit.get("completion_sentinel") or "")
    return ""


def main() -> int:
    suite = run_suite()
    ops = suite["operations"]
    tests = suite["tests"]
    expected = {(fwd, d) for fwd, _ in PAIRS for d in ("forward", "reverse")}
    seen = {(row["name"], row["direction"]) for row in ops}
    unsafe = [
        f"{row['name']}/{row['direction']}"
        for row in ops
        if not row["hash_sets_equal"] or not row["second_exit_ok"]
    ]
    derived_pass = (
        seen == expected
        and not unsafe
        and tests["hash_sets_equal_both_directions"]["pass"]
        and tests["second_exit_already_applied_or_zero"]["pass"]
    )
    print(
        json.dumps(
            {
                "probe": "probe1-repeat-hashes",
                "unit_id": "CNF-0036",
                "pairs": len(ops),
                "coverage": sorted(f"{n}/{d}" for n, d in seen),
                "unsafe": unsafe,
                "derived_pass": derived_pass,
            },
            sort_keys=True,
        )
    )
    if not derived_pass:
        print("FAILED:CNF-0036-probe1 hash sets not equal both directions")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0036-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    sentinel = catalog_sentinel()
    if not sentinel or sentinel not in text:
        print("FAILED:CNF-0036-probe1 sentinel-absent")
        return 1
    if doc.get("unit_id") != "CNF-0036" or str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNF-0036-probe1 artifact state", doc.get("state"))
        return 1
    art_ops = report_payload(doc).get("operations") or []
    if len(art_ops) != 10:
        print(f"FAILED:CNF-0036-probe1 artifact operations={len(art_ops)} want=10")
        return 1
    if not all(row.get("hash_sets_equal") for row in art_ops):
        print("FAILED:CNF-0036-probe1 artifact reports a non-idempotent op")
        return 1
    print("SUCCESS:CNF-0036-probe1 repeat-application both directions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
