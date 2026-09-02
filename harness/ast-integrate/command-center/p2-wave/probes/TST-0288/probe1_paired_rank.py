#!/usr/bin/env python3
"""Probe 1: paired comparison, weight-source ablation, random-weight null.

Recomputes the gold-set ranking live. Every method is scored on the same
resolved cases. Random weights must not significantly beat majority (else the
corpus is too small and a ranking is withheld). The always-95 forecaster must
score worse than majority so the metric can fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0288.json"


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0288-probe1 {msg}")
    return 1


def main() -> int:
    doc = H.run()
    n = doc["n_test"]
    if n != H.N_TEST:
        return _fail(f"n_test={n} want={H.N_TEST}")
    cases = doc["per_case"]
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        return _fail("duplicate case ids")
    if len(cases) != n:
        return _fail(f"per_case={len(cases)}")

    names = [m for m in H.METHOD_ORDER]
    for c in cases:
        missing = [m for m in names if m not in c["brier"] or m not in c["forecasts"]]
        if missing:
            return _fail(f"case {c['id']} missing methods {missing}")
        if c["y"] not in (0, 1):
            return _fail(f"case {c['id']} y={c['y']}")

    if doc["random_weights_beats_majority"]:
        if not doc["ranking_withheld"]:
            return _fail("random weights beat majority but ranking was not withheld")
        print("null_control random_beats=True ranking_withheld=True (corpus too small)")
    else:
        print("null_control random_beats=False ranking_proceeds")

    if not doc["metric_separates_always_95"]:
        return _fail("always_95 Brier did not exceed majority (metric does not separate)")
    print(
        "metric_control always_95_brier="
        f"{doc['methods']['always_95']['mean_brier']:.6f} "
        f"majority={doc['methods']['majority']['mean_brier']:.6f}"
    )

    abl = doc["ablation"]
    if abl["calibration_mean_brier"] == abl["role_mean_brier"]:
        return _fail("ablation: calibration and role Brier identical")
    print(
        "ablation cal="
        f"{abl['calibration_mean_brier']:.6f} role={abl['role_mean_brier']:.6f}"
    )

    coinc = doc["coincidences_on_binary_gold"]
    if not coinc["majority_eq_approval"] or not coinc["score_eq_bayes_linear"]:
        return _fail(f"binary coincidences broken {coinc}")
    print(f"coincidences {json.dumps(coinc)}")

    ranking = doc["ranking_by_mean_brier"]
    if ranking[0] != doc["best_method"]:
        return _fail("best_method != ranking[0]")
    print(f"best={doc['best_method']} ranking_head={ranking[:5]}")
    print(f"weighting_beats_majority={doc['weighting_beats_majority']}")

    maj = doc["methods"]["majority"]["mean_brier"]
    wcal = doc["methods"]["weighted_calibration"]["mean_brier"]
    blog = doc["methods"]["bayes_log"]["mean_brier"]
    print(f"brier majority={maj:.6f} weighted_cal={wcal:.6f} bayes_log={blog:.6f}")

    if ART.is_file():
        rec = json.loads(ART.read_text(encoding="utf-8"))
        if rec.get("unit_id") != "TST-0288":
            return _fail("receipt unit_id")
        st = str(rec.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return _fail(f"receipt self-declared {st}")
        text = json.dumps(rec)
        if "SUCCESS:TST-0288" not in text:
            return _fail("sentinel absent in receipt")
        live_best = rec.get("comparison", {}).get("best_method")
        if live_best != doc["best_method"]:
            return _fail(f"receipt best={live_best} live={doc['best_method']}")
        rec_maj = rec.get("comparison", {}).get("methods", {}).get("majority", {})
        if rec_maj:
            if abs(float(rec_maj["mean_brier"]) - maj) > 1e-9:
                return _fail("receipt majority Brier drift")
        rec_claim = rec.get("claim") or rec.get("comparison", {}).get("claim") or ""
        if "do not outperform unweighted majority" in doc["claim"]:
            if "do not outperform unweighted majority" not in rec_claim and not doc["weighting_beats_majority"]:
                return _fail("receipt claim does not match live weighting result")
        print("receipt_match best and majority Brier")

    print("SUCCESS:TST-0288-probe1 paired rank, ablation, null control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
