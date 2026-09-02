#!/usr/bin/env python3
"""Probe 2: seeded three-defect aggregate + dependent short-circuit + red exit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402

UNIT = "TST-0016"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    rows = S.run_required_tests()
    print(json.dumps({"probe": "probe2-seeded-aggregate", "tests": rows}, sort_keys=True))
    for row in rows:
        print(f"{row['id']} {row['result']}")
        if row["result"] != "PASS":
            return fail(row["id"])
    want = {
        "test_three_seeded_independent_defects_are_all_reported_in_one_run",
        "test_a_genuinely_dependent_step_still_short_circuits",
        "test_aggregate_exit_code_is_red_when_any_check_is_red",
    }
    got = {r["id"] for r in rows}
    if got != want:
        return fail(f"test id mismatch {got}")
    print(
        "SUCCESS:TST-0016-probe2 three independent defects in one run; "
        "dependent short-circuits; aggregate exit red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
