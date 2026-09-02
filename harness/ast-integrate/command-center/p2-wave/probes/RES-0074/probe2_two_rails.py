#!/usr/bin/env python3
"""Probe 2: two independent rails per surviving claim; capture sha256 match."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402


def main() -> int:
    if not C.ART.is_file():
        print("FAILED:RES-0074-probe2 artifact missing")
        return 1
    doc = C.load_art()
    ok, why = C.grade_rails(doc)
    print(f"rails_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0074-probe2 rails check")
        return 1
    bok, bwhy = C.both_states_rails(doc)
    print(f"both_states={bok} {bwhy}")
    if not bok:
        print("FAILED:RES-0074-probe2 both-states control")
        return 1
    # Real interchange must not be assigned to a one-way row.
    for row in doc["per_format_table"]:
        if row.get("format_id") == "GHA-YAML" and C.is_real_interchange(row):
            print("FAILED:RES-0074-probe2 GHA marked real")
            return 1
    print("SUCCESS:RES-0074-probe2 two-rail evidence and sha256 match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
