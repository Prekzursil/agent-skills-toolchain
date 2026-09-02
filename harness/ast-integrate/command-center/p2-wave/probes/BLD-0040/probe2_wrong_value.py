#!/usr/bin/env python3
"""Probe 2: independent reviewer — break compute_score, confirm detection power.

Inject a wrong-but-non-crashing return. NO-CRASH-ONLY must stay green;
EXACT-VALUE must go red. Shared fixtures must be byte-identical afterwards.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import discriminate as D  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "BLD-0040.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0040-probe2 {msg}")
    return 1


def main() -> int:
    rec = D.run_discrimination()
    print(json.dumps(rec, indent=2))
    if not rec.get("ok"):
        return fail(
            f"discrimination failed baseline={rec.get('baseline')} "
            f"mutated={rec.get('mutated')} unchanged={rec.get('shared_tree_unchanged')}"
        )
    if not RECEIPT.is_file():
        return fail("receipt absent")
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        return fail("reviewer.independent is not true")
    if str(rev.get("verdict") or "").upper() != "PASS":
        return fail("reviewer.verdict is not PASS")
    if not rev.get("no_crash_stayed_green"):
        return fail("receipt reviewer did not record no-crash stayed green")
    if not rev.get("exact_value_went_red"):
        return fail("receipt reviewer did not record exact-value went red")
    if str(rev.get("broken_function") or "") != "compute_score":
        return fail("receipt reviewer.broken_function mismatch")
    print(
        "baseline_both_pass=True no_crash_stayed_green=True "
        "exact_value_went_red=True shared_tree_unchanged=True"
    )
    print("SUCCESS:BLD-0040-probe2 wrong-value discrimination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
