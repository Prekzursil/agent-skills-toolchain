#!/usr/bin/env python3
"""Probe 1: six invalid fixtures + valid control in one invocation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from corpus import evaluate_corpus  # noqa: E402


def main() -> int:
    report = evaluate_corpus()
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, sort_keys=True))
    for row in report["rows"]:
        print(
            f"{row['id']} exit={row['exit_code']} vid={row['violation_id']} pass={row['pass']}"
        )
    if not report["same_run"]:
        print("FAILED:CNF-0083-probe1 not same-run")
        return 1
    if not report["valid_ok"]:
        print("FAILED:CNF-0083-probe1 valid control did not pass")
        return 1
    if not report["all_invalid_rejected"]:
        print("FAILED:CNF-0083-probe1 an invalid fixture was accepted or mis-labelled")
        return 1
    if not report["distinguishable_errors"]:
        print(
            "FAILED:CNF-0083-probe1 errors not distinguishable "
            f"ids={report['violation_ids']}"
        )
        return 1
    print("SUCCESS:CNF-0083-probe1 corpus strictness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
