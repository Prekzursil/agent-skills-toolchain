#!/usr/bin/env python3
"""Probe 2: independent statistics reviewer.

Recomputes mean Brier, bootstrap CI, and the paired permutation test from the
raw per-case forecasts, without reading the methods[] summary table. Must
reproduce the receipt's effect size and interval.
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
    print(f"FAILED:TST-0288-probe2 {msg}")
    return 1


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def main() -> int:
    doc = H.run()
    cases = doc["per_case"]
    names = list(H.METHOD_ORDER)
    indep_brier: dict[str, list[float]] = {m: [] for m in names}
    for row in cases:
        y = row["y"]
        for m in names:
            p = row["forecasts"][m]
            # Independent scoring path: expand (p-y)**2 here, do not reuse row["brier"].
            indep_brier[m].append((p - y) ** 2)
            stored = row["brier"][m]
            if abs(stored - indep_brier[m][-1]) > 1e-12:
                return _fail(f"stored brier drift case={row['id']} method={m}")

    indep_mean = {m: mean(xs) for m, xs in indep_brier.items()}
    for m, v in indep_mean.items():
        reported = doc["methods"][m]["mean_brier"]
        if abs(v - reported) > 1e-12:
            return _fail(f"mean drift {m} indep={v} reported={reported}")
        print(f"mean_ok {m}={v:.8f}")

    best = min(
        (m for m in names if m not in H.RANK_EXCLUDE),
        key=lambda m: (indep_mean[m], m),
    )
    if best != doc["best_method"]:
        return _fail(f"best indep={best} reported={doc['best_method']}")

    blo, bhi = H.bootstrap_ci(indep_brier[best], seed=H.SEED + 11 + H.METHOD_ORDER.index(best))
    rlo, rhi = doc["methods"][best]["brier_ci95"]
    if abs(blo - rlo) > 1e-12 or abs(bhi - rhi) > 1e-12:
        return _fail(f"CI drift best lo={blo},{rlo} hi={bhi},{rhi}")
    print(f"ci_ok best={best} [{blo:.6f},{bhi:.6f}]")

    paired = H.paired_perm(
        indep_brier[best],
        indep_brier["majority"],
        seed=H.SEED + 7,
    )
    reported_p = doc["best_vs_majority"]
    if abs(paired["mean_diff"] - reported_p["mean_diff"]) > 1e-12:
        return _fail("paired mean_diff drift")
    if abs(paired["p_two_sided"] - reported_p["p_two_sided"]) > 1e-12:
        return _fail("paired p drift")
    print(
        f"paired_ok mean_diff={paired['mean_diff']:.6f} p={paired['p_two_sided']:.6f}"
    )

    rand_mean = indep_mean["random_weights"]
    maj_mean = indep_mean["majority"]
    rand_p = H.paired_perm(
        indep_brier["random_weights"],
        indep_brier["majority"],
        seed=H.SEED + 7,
    )
    beats = rand_mean < maj_mean - 1e-12 and rand_p["p_two_sided"] < 0.05
    if beats != doc["random_weights_beats_majority"]:
        return _fail("null-control reproduction mismatch")
    print(f"null_ok random_mean={rand_mean:.6f} majority_mean={maj_mean:.6f} beats={beats}")

    a95 = [(0.95 - row["y"]) ** 2 for row in cases]
    if mean(a95) <= maj_mean:
        return _fail("always_95 did not separate")
    print(f"always95_ok {mean(a95):.6f} > majority {maj_mean:.6f}")

    if not ART.is_file():
        print("receipt absent; live reproduction only")
        print("SUCCESS:TST-0288-probe2 independent reproduce (no receipt yet)")
        return 0

    rec = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0288" not in json.dumps(rec):
        return _fail("sentinel absent")
    cmp_ = rec.get("comparison") or {}
    rec_best = cmp_.get("best_method")
    if rec_best != best:
        return _fail(f"receipt best={rec_best}")
    rec_delta = float((cmp_.get("best_vs_majority") or {}).get("mean_diff"))
    if abs(rec_delta - paired["mean_diff"]) > 1e-9:
        return _fail(f"receipt effect-size drift {rec_delta} vs {paired['mean_diff']}")
    rec_ci = (cmp_.get("methods") or {}).get(best, {}).get("brier_ci95")
    if not rec_ci or abs(rec_ci[0] - blo) > 1e-9 or abs(rec_ci[1] - bhi) > 1e-9:
        return _fail(f"receipt CI drift {rec_ci}")
    rec_p = float((cmp_.get("best_vs_majority") or {}).get("p_two_sided"))
    if abs(rec_p - paired["p_two_sided"]) > 1e-9:
        return _fail(f"receipt p drift {rec_p}")
    print(
        f"receipt_reproduced effect={rec_delta:.6f} p={rec_p:.6f} "
        f"ci=[{rec_ci[0]:.6f},{rec_ci[1]:.6f}]"
    )
    print("SUCCESS:TST-0288-probe2 independent reproduce of effect size and interval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
