#!/usr/bin/env python3
"""Probe 1: twelve single-condition mutations each force reducer FALSE.

Healthy input must stay TRUE. The named :10646 case (exit 0 + missing
artifact) is mutation C2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import run_conformance  # noqa: E402

UNIT = "TST-0329"


def main() -> int:
    result = run_conformance()
    table = result["table"]
    healthy_ok = result["healthy_verdict"] == "TRUE" and not result["healthy_failing"]
    all_false = result["n_false"] == 12 and result["n_mutations"] == 12
    c2 = next(r for r in table if r["condition"] == "C2")
    named = bool(c2.get("named_10646")) and c2["reducer_verdict"] == "FALSE"
    ok = bool(result["pass"] and healthy_ok and all_false and named)
    payload = {
        "probe": "probe1-twelve-mutations",
        "unit_id": UNIT,
        "healthy_verdict": result["healthy_verdict"],
        "n_mutations": result["n_mutations"],
        "n_false": result["n_false"],
        "named_10646_is_c2": named,
        "table": [
            {
                "condition": r["condition"],
                "mutation": r["mutation"],
                "reducer_verdict": r["reducer_verdict"],
            }
            for r in table
        ],
        "pass": ok,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"healthy={result['healthy_verdict']} "
        f"false={result['n_false']}/12 "
        f"c2_10646={named}"
    )
    if not ok:
        print(f"FAILED:{UNIT}-probe1 mutation table incomplete")
        return 1
    print(f"SUCCESS:{UNIT}-probe1 twelve mutations each FALSE; healthy TRUE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
