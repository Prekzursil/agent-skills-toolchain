#!/usr/bin/env python3
"""Probe 2: boundary test at floor-1, floor, floor+1 for condition 3.

Independent of probe1: writes three files, stats each, and reads C03 from
the live reducer's condition vector. Also proves the declared floor is
consulted (alt floor=40) and that two weaker checkers would fail this test.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    FLOOR_ALT,
    FLOOR_PRIMARY,
    FLOOR_SUB_ABSOLUTE,
    SATISFIED,
    UNSATISFIED,
    evaluate_c03,
    load_reducer,
    nonempty_only_outcome,
    strict_exceeds_outcome,
    write_case,
)

RUNTIME = HERE / "runtime" / "boundary"


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0143-probe2 {msg}")
    return 1


def _run_triple(root: Path, prefix: str, floor: int, mod) -> list[dict]:
    rows = []
    for delta, label in ((-1, "floor-1"), (0, "floor"), (1, "floor+1")):
        size = floor + delta
        ws = write_case(root, f"{prefix}-{label}", size, floor)
        row = evaluate_c03(ws, mod)
        if row["independent_stat"]["stat_st_size"] != size:
            raise AssertionError(
                f"{label}: stat {row['independent_stat']['stat_st_size']} want {size}"
            )
        if not row["stat_agrees_with_read"]:
            raise AssertionError(f"{label}: stat/read mismatch")
        want = SATISFIED if delta >= 0 else UNSATISFIED
        if row["c03_outcome"] != want:
            raise AssertionError(
                f"{label} size={size} floor={floor} "
                f"C03={row['c03_outcome']!r} want={want} basis={row['c03_basis']!r}"
            )
        rows.append(
            {
                "label": label,
                "size": size,
                "floor": floor,
                "c03_outcome": row["c03_outcome"],
                "c03_basis": row["c03_basis"],
                "stat_st_size": row["independent_stat"]["stat_st_size"],
                "effective_min_bytes": row.get("effective_min_bytes"),
                "nonempty_only": nonempty_only_outcome(size),
                "strict_exceeds": strict_exceeds_outcome(size, floor),
            }
        )
    return rows


def main() -> int:
    reducer_path, mod = load_reducer()
    if RUNTIME.exists():
        shutil.rmtree(RUNTIME)
    RUNTIME.mkdir(parents=True, exist_ok=True)

    try:
        primary = _run_triple(RUNTIME, "p", FLOOR_PRIMARY, mod)
        alt = _run_triple(RUNTIME, "alt", FLOOR_ALT, mod)
    except AssertionError as exc:
        return _fail(str(exc))

    # Vacuous non-empty-only checker passes floor-1; live C03 must not.
    floor_minus = next(r for r in primary if r["label"] == "floor-1")
    if floor_minus["nonempty_only"] != SATISFIED:
        return _fail("vacuous nonempty-only checker did not pass floor-1")
    if floor_minus["c03_outcome"] != UNSATISFIED:
        return _fail("live C03 did not reject floor-1 (would match nonempty-only)")

    # Strict `size > floor` rejects the exact floor; catalog requires it passes.
    exact = next(r for r in primary if r["label"] == "floor")
    if exact["strict_exceeds"] != UNSATISFIED:
        return _fail("strict-exceeds checker unexpectedly passed exact floor")
    if exact["c03_outcome"] != SATISFIED:
        return _fail("live C03 rejected the exact declared floor")

    # Alt floor proves min_bytes_threshold is read, not a hardcoded 128.
    alt_exact = next(r for r in alt if r["label"] == "floor")
    if alt_exact["size"] != FLOOR_ALT:
        return _fail("alt floor fixture size mismatch")
    if alt_exact["c03_outcome"] != SATISFIED:
        return _fail(
            f"declared floor={FLOOR_ALT} at exactly {FLOOR_ALT}B was not SATISFIED "
            "(hardcoded 128 would fail this case)"
        )

    # Live anti-gaming floor: a declared 40B floor at exactly 40B must not
    # SATISFY. IMP-0416's size>=declared stub would pass; the shared reducer
    # raises to ABSOLUTE_MIN_BYTES=64.
    sub_ws = write_case(RUNTIME, "sub-absolute", FLOOR_SUB_ABSOLUTE, FLOOR_SUB_ABSOLUTE)
    sub = evaluate_c03(sub_ws, mod)
    if sub["independent_stat"]["stat_st_size"] != FLOOR_SUB_ABSOLUTE:
        return _fail("sub-absolute fixture size mismatch")
    if sub["c03_outcome"] != UNSATISFIED:
        return _fail(
            f"declared floor={FLOOR_SUB_ABSOLUTE} at {FLOOR_SUB_ABSOLUTE}B was "
            f"{sub['c03_outcome']!r}; live ABSOLUTE_MIN_BYTES must raise the bar"
        )
    if int(sub.get("effective_min_bytes") or 0) < 64:
        return _fail(
            f"effective_min_bytes={sub.get('effective_min_bytes')!r} "
            "did not raise a sub-absolute declared floor"
        )

    out = {
        "pass": True,
        "probe": "probe2-boundary",
        "unit_id": "TST-0143",
        "reducer": str(reducer_path.relative_to(HERE.parents[3]).as_posix()),
        "reducer_id": sub.get("reducer_id"),
        "primary_floor": FLOOR_PRIMARY,
        "alt_floor": FLOOR_ALT,
        "primary": primary,
        "alt": alt,
        "sub_absolute": {
            "declared_floor": FLOOR_SUB_ABSOLUTE,
            "stat_st_size": sub["independent_stat"]["stat_st_size"],
            "c03_outcome": sub["c03_outcome"],
            "c03_basis": sub["c03_basis"],
            "effective_min_bytes": sub.get("effective_min_bytes"),
        },
        "vacuous_nonempty_only_would_fail_this_test": True,
        "strict_exceeds_would_fail_this_test": True,
        "declared_floor_is_consulted": True,
        "sub_absolute_declared_floor_is_raised": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "floor={f} minus={m} exact={e} plus={p} alt_exact={a} reducer={r}".format(
            f=FLOOR_PRIMARY,
            m=floor_minus["c03_outcome"],
            e=exact["c03_outcome"],
            p=next(r for r in primary if r["label"] == "floor+1")["c03_outcome"],
            a=alt_exact["c03_outcome"],
            r=out["reducer"],
        )
    )
    print("SUCCESS:TST-0143-probe2 floor-1 fails, floor and floor+1 pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
