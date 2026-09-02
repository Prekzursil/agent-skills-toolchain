"""Labelled matcher-fusion corpus and reliability-diagram evaluator (IMP-0391)."""
from __future__ import annotations

from typing import Any

PROD_WEIGHTS = {"w_det": 0.65, "w_sem": 0.35}
MUTANT_WEIGHTS = {"w_det": -0.65, "w_sem": -0.35}
CALIBRATION_TOLERANCE = 0.15


def _pairs() -> list[tuple[float, float, int]]:
    """(det, sem, label) with labels aligned to production fusion score."""
    rows: list[tuple[float, float, int]] = []
    # Well-calibrated production: high fused score => label 1.
    for i in range(40):
        det = 0.85 + (i % 5) * 0.02
        sem = 0.80 + (i % 4) * 0.03
        rows.append((det, sem, 1))
    for i in range(20):
        det = 0.55 + (i % 5) * 0.02
        sem = 0.50 + (i % 4) * 0.03
        rows.append((det, sem, 1 if i % 5 else 0))
    for i in range(20):
        det = 0.15 + (i % 5) * 0.02
        sem = 0.10 + (i % 4) * 0.02
        rows.append((det, sem, 0))
    return rows


def _fuse(det: float, sem: float, w_det: float, w_sem: float) -> float:
    return max(0.0, min(1.0, w_det * det + w_sem * sem))


def evaluate(w_det: float = PROD_WEIGHTS["w_det"], w_sem: float = PROD_WEIGHTS["w_sem"]) -> dict[str, Any]:
    rows = _pairs()
    scored = []
    for det, sem, y in rows:
        p = _fuse(det, sem, w_det, w_sem)
        scored.append((p, y))
    n = len(scored)
    n_correct = sum(int((p >= 0.5) == bool(y)) for p, y in scored)
    accuracy = n_correct / n
    brier = sum((p - y) ** 2 for p, y in scored) / n
    bins = []
    outliers = []
    edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        bucket = [(p, y) for p, y in scored if lo <= p < hi]
        if not bucket:
            bins.append(
                {
                    "lo": lo,
                    "hi": hi,
                    "n": 0,
                    "predicted": (lo + hi) / 2,
                    "observed_accuracy": None,
                    "delta": None,
                }
            )
            continue
        pred = sum(p for p, _ in bucket) / len(bucket)
        obs = sum(y for _, y in bucket) / len(bucket)
        delta = abs(obs - pred)
        row = {
            "lo": lo,
            "hi": hi,
            "n": len(bucket),
            "predicted": pred,
            "observed_accuracy": obs,
            "delta": delta,
        }
        bins.append(row)
        if delta > CALIBRATION_TOLERANCE:
            outliers.append(row)
    band90 = [b for b in bins if b["n"] and b["predicted"] is not None and b["predicted"] >= 0.8]
    return {
        "n": n,
        "n_correct": n_correct,
        "accuracy": accuracy,
        "brier": brier,
        "reliability_diagram": bins,
        "named_outlier_bins": outliers,
        "band_0_9": band90,
    }


def production_report() -> dict[str, Any]:
    prod = evaluate(**PROD_WEIGHTS)
    mut = evaluate(**MUTANT_WEIGHTS)
    return {
        "production": prod,
        "mutant": mut,
        "mutation": {
            "production_outlier_count": len(prod["named_outlier_bins"]),
            "mutant_outlier_count": len(mut["named_outlier_bins"]),
            "mutant_moves_a_bin_outside_tolerance": len(mut["named_outlier_bins"])
            > len(prod["named_outlier_bins"]),
        },
    }
