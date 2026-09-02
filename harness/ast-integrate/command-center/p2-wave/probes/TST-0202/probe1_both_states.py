#!/usr/bin/env python3
"""Probe 1: both-states control — direct path of equal resolved length.

A junction/symlink target and a direct (non-junction) path whose resolved
length is identical must receive the same accept/reject decision from the
production writer (resolved-path budget).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def main() -> int:
    row = S.run_both_states()
    print(json.dumps(
        {
            "probe": "probe1-both-states",
            "unit_id": "TST-0202",
            "pass": row["pass"],
            "identical_over_budget": row["identical_over_budget"],
            "identical_in_budget": row["identical_in_budget"],
            "over_resolved_length": row["over"]["resolved_length"],
            "over_alias_length": row["over"]["alias_length"],
            "over_direct_resolved_length": row["over"]["direct_resolved_length"],
            "junction_over_raised": row["junction_over"]["raised"],
            "direct_over_raised": row["direct_over"]["raised"],
            "junction_over_measured": row["junction_over"]["measured_length"],
            "direct_over_measured": row["direct_over"]["measured_length"],
            "junction_under_wrote": row["junction_under"].get("wrote"),
            "direct_under_wrote": row["direct_under"].get("wrote"),
            "junction_over_residue": row["junction_over_residue"],
            "direct_over_residue": row["direct_over_residue"],
        },
        sort_keys=True,
    ))
    if not row["pass"]:
        print("FAILED:TST-0202-probe1 both-states mismatch")
        return 1
    print("SUCCESS:TST-0202-probe1 both-states equal resolved length")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
