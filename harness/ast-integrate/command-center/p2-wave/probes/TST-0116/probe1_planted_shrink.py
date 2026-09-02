#!/usr/bin/env python3
"""Probe 1: a planted invariant violation is found and shrunk.

Catalog test: test_a_planted_invariant_violation_is_found_and_shrunk.

Does not rewrite the catalog receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

UNIT = "TST-0116"


def main() -> int:
    report = H.planted_shrink_check()
    print(json.dumps({"probe": "probe1-planted-shrink", "unit_id": UNIT, **{k: report[k] for k in ("pass", "checks", "run")}}, sort_keys=True))
    if not report.get("pass"):
        print("FAILED:TST-0116-probe1 planted invariant was not found-and-shrunk")
        print(json.dumps(report.get("checks"), indent=2)[:3000])
        return 1
    run = report["run"]
    print(
        "found=True original_acyclic=False shrunk_acyclic=False "
        f"original_nodes={run['original_size'].get('nodes')} "
        f"shrunk_nodes={run['shrunk_size'].get('nodes')} "
        f"seed={run.get('seed')} replay_identical=True"
    )
    print(f"SUCCESS:{UNIT}-probe1 planted invariant violation found and shrunk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
