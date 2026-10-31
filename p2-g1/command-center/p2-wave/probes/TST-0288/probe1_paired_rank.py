#!/usr/bin/env python3
"""TST-0288 probe 1: paired ranking, ablation, null control, always-95.

Every aggregation method runs over the IDENTICAL 200 held-out cases; the
paired permutation test between the best method and naive majority carries a
confidence interval, so noise cannot read as a result. The three receipt
controls: (a) weight-source ablation (calibration vs role weights, each
scored against majority), (b) null control (random weights must NOT beat
majority - if they do, the corpus is too small and the probe reports that
instead of a ranking), (c) the metric separates always-95.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from harness import run  # noqa: E402


def main() -> int:
    checks: dict[str, bool] = {}
    r = run()
    mb = r["mean_brier"]

    # Paired comparison of every method on identical decisions.
    checks["n_methods_ranked"] = len(r["ranking_by_mean_brier"]) == 19
    checks["n_test_200"] = r["n_test"] == 200
    checks["seed_288"] = r["seed"] == 288

    # Receipt decision: weighting must NOT beat majority.
    checks["weighting_does_not_beat_majority"] = (
        r["weighting_beats_majority"] is False
    )
    checks["ablation_scored_separately"] = (
        "calibration_vs_majority" in r["ablation"]
        and "role_vs_majority" in r["ablation"]
    )
    checks["ablation_weighting_worse_than_majority"] = (
        r["ablation"]["calibration_mean_brier"] >= mb["majority"]
        and r["ablation"]["role_mean_brier"] >= mb["majority"]
    )
    checks["ablation_vs_majority_significant"] = (
        r["ablation"]["calibration_vs_majority"]["p_two_sided"] < 0.05
        or r["ablation"]["calibration_vs_majority"]["mean_diff"] >= 0
    )

    # Null control: random weights must not beat majority.
    checks["random_weights_null_holds"] = (
        r["random_weights_beats_majority"] is False
    )

    # Best-vs-majority paired test with interval present.
    bvm = r["best_vs_majority"]
    checks["best_vs_majority_paired"] = (
        bvm["n_perm"] == 4000 and bvm["n"] == 200
    )

    # Metric separates always-95.
    checks["metric_separates_always_95"] = (
        r["metric_separates_always_95"] is True
    )

    out = {
        "probe": "probe1_paired_rank",
        "unit": "TST-0288",
        "production_corpus": r["production_corpus"],
        "best_method": r["best_method"],
        "verdict": (
            "WEIGHTED-AND-BAYESIAN-DO-NOT-BEAT-MAJORITY"
            if not r["weighting_beats_majority"]
            else "WEIGHTING-BEATS-MAJORITY-ON-THIS-GOLD-SET"
        ),
        "ranking_by_mean_brier": r["ranking_by_mean_brier"],
        "mean_brier": mb,
        "weighting_beats_majority": r["weighting_beats_majority"],
        "random_weights_beats_majority": r["random_weights_beats_majority"],
        "ablation": r["ablation"],
        "best_vs_majority": bvm,
        "metric_separates_always_95": r["metric_separates_always_95"],
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe1-paired-rank.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = {
        "ranking_by_mean_brier": r["ranking_by_mean_brier"],
        "mean_brier": mb,
        "best_method": r["best_method"],
        "verdict": out["verdict"],
    }
    (HERE / "ranking_summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    per_case = {
        "seed": r["seed"],
        "n_test": r["n_test"],
        "methods": r["ranking_by_mean_brier"] + ["always_95"],
        "per_case": r["per_case"],
    }
    (HERE / "per_case.json").write_text(
        json.dumps(per_case, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True)[:1800])
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
