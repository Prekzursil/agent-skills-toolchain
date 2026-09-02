#!/usr/bin/env python3
"""Probe 1: per-format table completeness + one-way control (both-states)."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402


def main() -> int:
    if not C.ART.is_file():
        print("FAILED:RES-0074-probe1 artifact missing")
        return 1
    doc = C.load_art()
    ok, why = C.grade_table(doc)
    print(f"table_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0074-probe1 table check")
        return 1
    bok, bwhy = C.both_states_table(doc)
    print(f"both_states={bok} {bwhy}")
    if not bok:
        print("FAILED:RES-0074-probe1 both-states control")
        return 1
    one_way = [r["format_id"] for r in doc["per_format_table"] if r.get("one_way") is True]
    real = [r["format_id"] for r in doc["per_format_table"] if C.is_real_interchange(r)]
    print(f"one_way={one_way}")
    print(f"real_interchange={real}")
    print("SUCCESS:RES-0074-probe1 per-format table and one-way control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
