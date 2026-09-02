#!/usr/bin/env python3
"""Probe 2: same fixture WITHOUT the fix reproduces the column shift (both-states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import extract_normalize as en


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0250-probe2 {msg}")
    return 1


def main() -> int:
    planted = en.planted_fixture()
    benign = en.benign_fixture()
    if b"\x1f" not in planted:
        return fail("planted fixture missing US")
    if b"\x1f" in benign:
        return fail("benign fixture unexpectedly contains US")

    fixed_planted = en.parse_table(planted)
    naive_planted = en.parse_table_naive(planted)
    fixed_benign = en.parse_table(benign)
    naive_benign = en.parse_table_naive(benign)

    planted_row = planted.split(b"\n")[1]
    late = [
        en.strip_controls_except_delimiter(p)
        for p in en.split_on_delimiter_and_controls(planted_row)
    ]

    fixed_w = [len(r) for r in fixed_planted]
    naive_w = [len(r) for r in naive_planted]
    if fixed_w != [3, 3, 3]:
        return fail(f"fixed parser shifted widths={fixed_w}")
    if naive_w[1] <= 3:
        return fail(
            f"naive parser did not reproduce the shift widths={naive_w} "
            "(detector blind)"
        )
    if len(late) <= 3:
        return fail(f"post-split sanitize recovered columns late={len(late)}")
    if naive_w == fixed_w:
        return fail("both-states collapsed: naive == fixed on planted fixture")

    # Detector silence on the clean twin.
    if [len(r) for r in naive_benign] != [3, 3, 3]:
        return fail("naive parser fires on benign fixture (false positive)")
    if [len(r) for r in fixed_benign] != [3, 3, 3]:
        return fail("fixed parser fires on benign fixture")
    if naive_benign != fixed_benign:
        return fail("benign naive/fixed mismatch")

    print(
        json.dumps(
            {
                "fixed_widths": fixed_w,
                "naive_widths": naive_w,
                "late_sanitize_width": len(late),
                "shift_reproduced": naive_w[1] > 3,
                "late_sanitize_insufficient": len(late) > 3,
                "benign_silent": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0250-probe2 both-states column-shift control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
