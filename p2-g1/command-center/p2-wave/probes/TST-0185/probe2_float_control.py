#!/usr/bin/env python3
"""TST-0185 probe2 -- negative control: a float-based parser MUST fail above 2^53.

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import int_roundtrip as IR  # noqa: E402

UNIT = "TST-0185"


def main() -> int:
    failures = 0
    examples = []
    checked = 0
    for delta in [1, 2, 3, 5, 1025, 1 << 20]:
        v = (1 << 53) + delta
        text = IR.emit_exact({"id": v})
        got = IR.parse_float_lossy(text)["id"]
        exact = IR.parse_exact(text)["id"]
        checked += 1
        if got != exact:
            failures += 1
            examples.append({"value": v, "float_got": int(got), "loss": exact - int(got)})
        if float(v) != v:
            pass  # float(v) rounding is the same defect seen through a different door
    # canonical demonstration: 2^53 and 2^53+1 are the SAME float
    collapse = float(1 << 53) == float((1 << 53) + 1)

    payload = {
        "probe": "probe2-float-control",
        "unit_id": UNIT,
        "pass": failures >= 3 and collapse,
        "float_lane_failures_above_2p53": failures,
        "values_checked": checked,
        "examples": examples[:5],
        "float64_collapse_2p53_vs_2p53p1": collapse,
        "note": "the lossy float path losing ids is the negative control that proves the exact lane matters",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 float_failures=%d/%d collapse=%s"
              % (UNIT, failures, checked, collapse))
        return 0
    print("FAILED:%s-probe2 failures=%d collapse=%s" % (UNIT, failures, collapse))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
