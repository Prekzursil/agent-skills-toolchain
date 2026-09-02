#!/usr/bin/env python3
"""Named probe 1: 10 known-answer questions, accuracy vs truth not just median.

Convergence that only collapses dispersion is herding. This probe requires the
evidence-gated holdout median to sit closer to ground truth than the classical
round-2 median on every distinguishable question, and forbids high-evidence
panelists from sacrificing truth to chase the round-1 median.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.topology.delphi import experiment_known_answers  # noqa: E402


def main() -> int:
    result = experiment_known_answers(seed=286)
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, default=str))
    print(
        "n={n} distinguishable={d} holdout_wins={h} sacrifices={s} "
        "herding_flags={f} err_r1={e1:.4f} err_r2={e2:.4f} err_holdout={eh:.4f}".format(
            n=result["n_questions"],
            d=result["n_distinguishable"],
            h=result["holdout_closer_than_classical_on_distinguishable"],
            s=result["high_evidence_anchoring_sacrifices"],
            f=result["herding_flags"],
            e1=result["mean_abs_err_r1_median"],
            e2=result["mean_abs_err_r2_median"],
            eh=result["mean_abs_err_holdout"],
        )
    )
    if result["n_questions"] != 10:
        print("FAILED:IMP-0286-probe1 expected 10 known-answer questions")
        return 1
    if not result["passed"]:
        print("FAILED:IMP-0286-probe1 known-answer convergence contract")
        return 1
    print("SUCCESS:IMP-0286-probe1 known-answer convergence against ground truth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
