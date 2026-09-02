#!/usr/bin/env python3
"""Probe 1: each of 12 isolation rows fails only condition k.

test_each_condition_fails_in_isolation[1..12]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

REPO = HERE.parents[3]


def main() -> int:
    rows = C.run_corpus(REPO)
    fail = False
    for k in range(1, 13):
        row = next(r for r in rows if r["intended_violation"] == k)
        ok = (
            row["verdict"] == "FAILED"
            and row["failing_condition_id"] == k
            and row["unsatisfied"] == [k]
            and row["isolated"] is True
        )
        print(
            f"test_each_condition_fails_in_isolation[{k}] "
            f"verdict={row['verdict']} failing={row['failing_condition_id']} "
            f"unsatisfied={row['unsatisfied']} isolated={row['isolated']} "
            f"mutation={row['mutation']}"
        )
        if not ok:
            fail = True
            print(f"  FAILED: expected FAILED id={k} only, reason={row['reason']}")
    ids = [
        r["failing_condition_id"]
        for r in rows
        if r["intended_violation"] is not None
    ]
    distinct = sorted(x for x in ids if x is not None)
    print(f"distinct_failing_condition_ids={distinct}")
    if distinct != list(range(1, 13)):
        fail = True
        print("FAILED:TST-0002-probe1 expected 12 distinct failing-condition-ids")
    if fail:
        print("FAILED:TST-0002-probe1 isolation")
        print(json.dumps(
            [{k: r[k] for k in (
                "row_id", "verdict", "failing_condition_id", "unsatisfied", "isolated"
            )} for r in rows],
            indent=1,
        ))
        return 1
    print("SUCCESS:TST-0002-probe1 12 isolation rows, 12 distinct failing-condition-ids")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
