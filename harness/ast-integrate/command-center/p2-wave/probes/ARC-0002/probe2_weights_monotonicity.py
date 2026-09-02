#!/usr/bin/env python3
"""Probe 2: weights sum to 1.00; strictly better vector cannot score lower."""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score as S  # noqa: E402

REPO = HERE.parents[3]
RUBRIC = REPO / "command-center/phase3/RUBRIC.json"


def equal_marks(val: str) -> dict[str, Decimal]:
    return {d["id"]: Decimal(val) for d in S.public_dimensions()}


def main() -> int:
    S.assert_weight_contract()
    wsum = S.weights_sum()
    bps = S.basis_points_sum()
    if wsum != Decimal("1.00") or bps != 10000:
        print(f"FAILED:ARC-0002-probe2 weight sum {wsum} bps={bps}")
        return 1
    if not RUBRIC.is_file():
        print("FAILED:ARC-0002-probe2 missing RUBRIC.json")
        return 1
    doc = json.loads(RUBRIC.read_text(encoding="utf-8"))
    dims = doc.get("dimensions") or []
    if len(dims) < 5:
        print("FAILED:ARC-0002-probe2 too few dimensions")
        return 1
    live_sum = sum(Decimal(str(d["weight_decimal"])) for d in dims)
    if live_sum != Decimal("1.00"):
        print(f"FAILED:ARC-0002-probe2 live weight_decimal sum {live_sum}")
        return 1
    live_bps = sum(int(d["basis_points"]) for d in dims)
    if live_bps != 10000:
        print(f"FAILED:ARC-0002-probe2 live basis_points sum {live_bps}")
        return 1
    ids = [d["id"] for d in dims]
    base = equal_marks("0.50")
    better = dict(base)
    worse = dict(base)
    target = ids[0]
    better[target] = Decimal("0.60")
    worse[target] = Decimal("0.50")
    if not S.strictly_better(better, worse, dims):
        print("FAILED:ARC-0002-probe2 strictly_better predicate false")
        return 1
    s_better = S.score_vector(better, dims)
    s_worse = S.score_vector(worse, dims)
    s_equal = S.score_vector(base, dims)
    mono = s_better > s_worse and s_worse == s_equal
    # Flip: worse-on-one cannot score higher
    flipped = dict(base)
    flipped[target] = Decimal("0.40")
    s_flipped = S.score_vector(flipped, dims)
    both_states = s_better > s_equal > s_flipped
    print(json.dumps(
        {
            "probe": "probe2-weights-monotonicity",
            "unit_id": "ARC-0002",
            "weights_sum": str(wsum),
            "basis_points_sum": bps,
            "live_weight_decimal_sum": str(live_sum),
            "dimension_improved": target,
            "score_equal": str(s_equal),
            "score_better": str(s_better),
            "score_worse_on_one": str(s_flipped),
            "monotonic_up": bool(mono),
            "both_states": bool(both_states),
            "delta": str(s_better - s_equal),
        },
        indent=2,
        sort_keys=True,
    ))
    print(
        f"sum={wsum} bps={bps} better={s_better} equal={s_equal} "
        f"flipped={s_flipped} mono={mono} both_states={both_states}"
    )
    if not (mono and both_states):
        print("FAILED:ARC-0002-probe2 monotonicity")
        return 1
    print("SUCCESS:ARC-0002-probe2 weight-sum and monotonicity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
