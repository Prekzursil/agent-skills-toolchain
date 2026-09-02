#!/usr/bin/env python3
"""Probe 2: each mutation unsatisfies exactly one condition.

Independence is measured by evaluating all twelve checks on each mutant.
A skip-k hole detector must return TRUE on mutant k (proving the test
would catch a reducer that dropped that condition).
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
    rows = result["independence"]
    holes = result["hole_detector"]
    exact = all(r.get("exactly_one") for r in rows) and len(rows) == 12
    holes_ok = all(
        h.get("full_reducer_false") and h.get("skip_condition_true") for h in holes
    )
    ok = bool(exact and holes_ok and result["healthy_verdict"] == "TRUE")
    payload = {
        "probe": "probe2-condition-independence",
        "unit_id": UNIT,
        "n": len(rows),
        "all_exactly_one": exact,
        "hole_detector_all_true_when_skipped": holes_ok,
        "independence": rows,
        "pass": ok,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"exactly_one={exact} skip_k_holes={holes_ok} "
        f"healthy={result['healthy_verdict']}"
    )
    if not ok:
        print(f"FAILED:{UNIT}-probe2 independence or hole-detector")
        return 1
    print(f"SUCCESS:{UNIT}-probe2 each mutant violates exactly one condition")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
