#!/usr/bin/env python3
"""Probe 1: both-states control for completion-predicate condition 3.

0-byte artifact must be UNSATISFIED; a file at exactly the declared floor
must be SATISFIED. Evidence is the live condition vector plus an independent
stat() of each file.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    FLOOR_PRIMARY,
    SATISFIED,
    UNSATISFIED,
    evaluate_c03,
    load_reducer,
    write_case,
)

RUNTIME = HERE / "runtime" / "both-states"


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0143-probe1 {msg}")
    return 1


def main() -> int:
    reducer_path, mod = load_reducer()
    if RUNTIME.exists():
        shutil.rmtree(RUNTIME)
    RUNTIME.mkdir(parents=True, exist_ok=True)

    zero_ws = write_case(RUNTIME, "zero", 0, FLOOR_PRIMARY)
    floor_ws = write_case(RUNTIME, "floor", FLOOR_PRIMARY, FLOOR_PRIMARY)
    zero = evaluate_c03(zero_ws, mod)
    floor = evaluate_c03(floor_ws, mod)

    if zero["independent_stat"]["stat_st_size"] != 0:
        return _fail(f"zero-byte fixture is {zero['independent_stat']['stat_st_size']}B")
    if floor["independent_stat"]["stat_st_size"] != FLOOR_PRIMARY:
        return _fail(
            f"floor fixture is {floor['independent_stat']['stat_st_size']}B "
            f"want {FLOOR_PRIMARY}"
        )
    if not zero["stat_agrees_with_read"] or not floor["stat_agrees_with_read"]:
        return _fail("stat() disagreed with read_bytes() length")
    if zero["c03_outcome"] != UNSATISFIED:
        return _fail(
            f"0-byte C03 outcome={zero['c03_outcome']!r} basis={zero['c03_basis']!r}"
        )
    if floor["c03_outcome"] != SATISFIED:
        return _fail(
            f"floor-sized C03 outcome={floor['c03_outcome']!r} basis={floor['c03_basis']!r}"
        )
    if not zero["vector_matches_stat"] or not floor["vector_matches_stat"]:
        return _fail("condition vector disagreed with independent stat")

    out = {
        "pass": True,
        "probe": "probe1-both-states",
        "unit_id": "TST-0143",
        "reducer": str(reducer_path.relative_to(HERE.parents[3]).as_posix()),
        "reducer_id": floor.get("reducer_id"),
        "floor": FLOOR_PRIMARY,
        "zero": {
            "stat_st_size": zero["independent_stat"]["stat_st_size"],
            "c03_outcome": zero["c03_outcome"],
            "c03_basis": zero["c03_basis"],
            "effective_min_bytes": zero.get("effective_min_bytes"),
        },
        "floor_sized": {
            "stat_st_size": floor["independent_stat"]["stat_st_size"],
            "c03_outcome": floor["c03_outcome"],
            "c03_basis": floor["c03_basis"],
            "effective_min_bytes": floor.get("effective_min_bytes"),
        },
        "both_directions": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "zero={z}B C03={zo} floor={f}B C03={fo} reducer={r}".format(
            z=zero["independent_stat"]["stat_st_size"],
            zo=zero["c03_outcome"],
            f=floor["independent_stat"]["stat_st_size"],
            fo=floor["c03_outcome"],
            r=out["reducer"],
        )
    )
    print("SUCCESS:TST-0143-probe1 0-byte fails, floor-sized passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
