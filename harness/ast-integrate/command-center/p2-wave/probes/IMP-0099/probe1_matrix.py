#!/usr/bin/env python3
"""Probe 1: 20-case affected/unaffected matrix on the advisory interval engine.

Signal 1 of IMP-0099. Boundary loci (at-fixed, prerelease-of-fixed) are
asserted by name, not averaged into a pass rate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.advisory import from_record, is_affected  # noqa: E402

FIX = REPO / "tools/marketplace/fixtures/imp0099_matrix.json"
ART = REPO / "command-center/receipts/IMP-0099.json"
REQUIRED_LOCI = {
    "below",
    "at-lower-bound",
    "inside",
    "at-fixed",
    "above",
    "prerelease-of-fixed",
}


def main() -> int:
    doc = json.loads(FIX.read_text(encoding="utf-8"))
    cases = doc["cases"]
    if len(cases) != 20:
        print(f"FAILED:IMP-0099-probe1 matrix size {len(cases)} want=20")
        return 1
    loci = {c["locus"] for c in cases}
    missing = REQUIRED_LOCI - loci
    if missing:
        print(f"FAILED:IMP-0099-probe1 missing loci {sorted(missing)}")
        return 1
    adv = from_record(doc["advisory"])
    rows = []
    fail = False
    for row in cases:
        got = is_affected(adv, row["version"])
        ok = got == row["expected_affected"]
        if not ok:
            fail = True
        rec = {
            "id": row["id"],
            "version": row["version"],
            "locus": row["locus"],
            "expected": row["expected_affected"],
            "advisory_engine": got,
            "match": ok,
        }
        rows.append(rec)
        print(
            f"case {row['id']:02d} version={row['version']:<16} "
            f"locus={row['locus']:<22} expected={row['expected_affected']!s:<5} "
            f"got={got!s:<5} ok={ok}"
        )
    matched = sum(1 for r in rows if r["match"])
    print(f"matched={matched}/20 fail={fail}")

    at_fixed = [r for r in rows if r["locus"] == "at-fixed"]
    pre_fixed = [r for r in rows if r["locus"] == "prerelease-of-fixed"]
    if not at_fixed or any(r["advisory_engine"] for r in at_fixed):
        print("FAILED:IMP-0099-probe1 fixed-version boundary off-by-one")
        return 1
    if not pre_fixed or not all(r["advisory_engine"] for r in pre_fixed):
        print("FAILED:IMP-0099-probe1 prerelease-of-fixed must be affected")
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0099" not in text:
            print("FAILED:IMP-0099-probe1 receipt sentinel absent")
            return 1
        receipt = json.loads(text)
        st = str(receipt.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0099-probe1 receipt self-declared {st}")
            return 1

    summary = {
        "probe": "probe1-matrix",
        "unit_id": "IMP-0099",
        "cases": 20,
        "matched": matched,
        "at_fixed_unaffected": True,
        "prerelease_of_fixed_affected": True,
        "pass": not fail and matched == 20,
    }
    print(json.dumps(summary, sort_keys=True))
    if fail or matched != 20:
        print("FAILED:IMP-0099-probe1 matrix disagreement")
        return 1
    print("SUCCESS:IMP-0099-probe1 20-case advisory range matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
