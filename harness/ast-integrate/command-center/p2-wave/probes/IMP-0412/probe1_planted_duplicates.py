#!/usr/bin/env python3
"""Probe 1: planted-duplicate control (exact + reworded) and claim-time catch.

Both injected clones of IMP-0412 must collide. A ghost claim under a new id
must be caught against the live catalog. A mutation that drops the input set
from the comparison must still catch the exact clone (target tokens suffice
for that pair) — the required negative is the reverse: dropping TARGET tokens
and hashing inputs alone must fail to distinguish IMP-0412 from IMP-0456,
proving the input set is not the whole fingerprint; that check lives in probe 2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import run_duplicate_control  # noqa: E402
from scan import load_catalog  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0412.json"


def main() -> int:
    catalog = load_catalog()
    units = catalog.get("work_units") or []
    result = run_duplicate_control(units)
    print(json.dumps(result, sort_keys=True, default=str))
    if not result["exact_duplicate_caught"]:
        print("FAILED:IMP-0412-probe1 exact planted duplicate not caught")
        return 1
    if not result["reworded_duplicate_caught"]:
        print("FAILED:IMP-0412-probe1 reworded planted duplicate not caught")
        return 1
    if not result["claim_time_caught_donor"]:
        print("FAILED:IMP-0412-probe1 claim-time check missed IMP-0412")
        return 1
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SENTINEL:IMP-0412:DUPLICATES-FINGERPRINTED" not in text:
            print("FAILED:IMP-0412-probe1 receipt sentinel absent")
            return 1
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0412-probe1 receipt state={doc.get('state')}")
            return 1
    print(
        "exact=True reworded=True claim_time=True "
        f"injected_pairs={result['injected_collision_pair_count']}"
    )
    print("SUCCESS:IMP-0412-probe1 planted exact and reworded duplicates caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
