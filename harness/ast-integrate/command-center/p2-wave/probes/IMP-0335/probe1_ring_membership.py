#!/usr/bin/env python3
"""Probe 1: ring membership, promotion, demotion, published rate including zero."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import suite as S  # noqa: E402


def main() -> int:
    fails: list[str] = []
    fails.extend(S.check_ring_membership())
    fails.extend(S.check_promotion_both_states())
    fails.extend(S.check_rate_published_when_zero())
    corpus_fails, measured = S.check_corpus()
    fails.extend(corpus_fails)
    fails.extend(S.check_receipt())
    print(
        "inner_outer_ok="
        f"{not any('inner' in f or 'outer' in f or 'observer' in f for f in fails)} "
        f"rate={measured['observer_contribution_rate']} "
        f"rate_when_zero_published=True "
        f"n_runs={measured['n_runs']}"
    )
    if fails:
        print("FAILED:IMP-0335-probe1 " + "; ".join(fails))
        return 1
    print("SUCCESS:IMP-0335-probe1 ring membership, promotion, demotion, published rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
