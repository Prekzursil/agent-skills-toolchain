#!/usr/bin/env python3
"""Probe 1: correlated same-vendor panel overstates independence-assuming pool.

Mechanism: Monte Carlo mean |p_indep_bayes - p_true| plus a worked canonical
panel. Distinct from probe 2 (tau=0 identity / both-states detector).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import pool as P  # noqa: E402

OUT = HERE / "probe1-correlated.raw.json"
ART = (
    REPO
    / "command-center/design/council/CNL-0065-bayesian-belief-aggregation-linear-versus-logarithmic-pool.md"
)
DELTA_MIN = 0.08
INFLATION_MIN = 2.0


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0065-probe1 {msg}")
    return 1


def main() -> int:
    corr = P.monte_carlo(tau=P.TAU_CORRELATED)
    can = P.canonical()
    analytic = P.inflation_factor(P.N_SEATS, P.SIGMA, P.TAU_CORRELATED)
    matrix_llr = P.matrix_llr_true(P.CANONICAL_X, P.MU, P.SIGMA, P.TAU_CORRELATED)
    closed_llr = P.llr_true(P.CANONICAL_X, P.MU, P.SIGMA, P.TAU_CORRELATED)
    if abs(matrix_llr - closed_llr) > 1e-12:
        return fail(f"matrix/closed-form mismatch {matrix_llr} vs {closed_llr}")
    if corr["mean_abs_dp_indep"] < DELTA_MIN:
        return fail(f"overstatement too small {corr['mean_abs_dp_indep']}")
    if corr["mean_abs_dp_indep"] <= corr["mean_abs_dp_linear"]:
        return fail("indep Bayes not worse than linear pool on |p-p_true|")
    if analytic < INFLATION_MIN:
        return fail(f"inflation factor {analytic} below {INFLATION_MIN}")
    if can["abs_dp_indep"] <= can["abs_dp_linear"]:
        return fail("canonical panel: indep not more overstated than linear")
    if not can["more_extreme_indep"]:
        return fail("canonical panel: indep Bayes not more extreme")
    ratio = corr["mean_llr_ratio_indep_over_true"]
    if ratio is None or abs(ratio - analytic) > 0.05:
        return fail(f"MC llr ratio {ratio} != analytic {analytic}")

    payload = {
        "probe": "probe1-correlated-overclaim",
        "unit_id": "CNL-0065",
        "tau": P.TAU_CORRELATED,
        "pairwise_corr": corr["pairwise_corr"],
        "mean_abs_dp_indep": corr["mean_abs_dp_indep"],
        "mean_abs_dp_linear": corr["mean_abs_dp_linear"],
        "mean_abs_dp_log_normalized": corr["mean_abs_dp_log_normalized"],
        "analytic_logodds_inflation": analytic,
        "mean_llr_ratio_indep_over_true": ratio,
        "canonical_p_true": can["p_true"],
        "canonical_p_indep_bayes": can["p_indep_bayes"],
        "canonical_p_linear": can["p_linear"],
        "canonical_abs_dp_indep": can["abs_dp_indep"],
        "matrix_llr_matches_closed_form": True,
        "pass": True,
    }
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        q = doc.get("quantification") or {}
        claimed = float(q.get("correlated_mean_abs_dp_indep") or 0)
        if abs(claimed - corr["mean_abs_dp_indep"]) > 1e-9:
            return fail(
                f"artifact dp mismatch claimed={claimed} live={corr['mean_abs_dp_indep']}"
            )
        claimed_inf = float(q.get("analytic_logodds_inflation") or 0)
        if abs(claimed_inf - analytic) > 1e-12:
            return fail(f"artifact inflation mismatch {claimed_inf} vs {analytic}")
        payload["artifact_quantification_matches"] = True

    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "tau={tau} pairwise_corr={pc:.6f} mean_abs_dp_indep={d:.6f} "
        "mean_abs_dp_linear={lin:.6f} inflation={inf:.6f} "
        "canonical_p_true={pt:.6f} canonical_p_indep={pi:.6f} "
        "canonical_abs_dp_indep={cd:.6f}".format(
            tau=P.TAU_CORRELATED,
            pc=corr["pairwise_corr"],
            d=corr["mean_abs_dp_indep"],
            lin=corr["mean_abs_dp_linear"],
            inf=analytic,
            pt=can["p_true"],
            pi=can["p_indep_bayes"],
            cd=can["abs_dp_indep"],
        )
    )
    print("SUCCESS:CNL-0065-probe1 correlated overclaim quantified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
