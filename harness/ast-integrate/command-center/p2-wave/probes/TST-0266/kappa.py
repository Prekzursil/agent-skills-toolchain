#!/usr/bin/env python3
"""Cohen's kappa and a frozen bootstrap CI for 3-class novelty labels.

The bootstrap seed and resample count are part of the published protocol so a
statistics reviewer can reproduce the interval from the raw per-case table
without touching the scorer.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

LABELS: tuple[str, ...] = ("duplicate", "variant", "distinct")
BOOTSTRAP_SEED = 266
BOOTSTRAP_N = 2000
CI_ALPHA = 0.05


def confusion(y_true: Sequence[str], y_pred: Sequence[str]) -> list[list[int]]:
    idx = {lab: i for i, lab in enumerate(LABELS)}
    matrix = [[0, 0, 0] for _ in range(3)]
    for truth, pred in zip(y_true, y_pred):
        if truth not in idx or pred not in idx:
            raise ValueError(f"unknown label pair {(truth, pred)}")
        matrix[idx[truth]][idx[pred]] += 1
    return matrix


def agreement_table(y_true: Sequence[str], y_pred: Sequence[str]) -> dict:
    matrix = confusion(y_true, y_pred)
    n = len(y_true)
    if n == 0:
        raise ValueError("empty agreement table")
    observed = sum(matrix[i][i] for i in range(3)) / n
    row = [sum(matrix[i]) for i in range(3)]
    col = [sum(matrix[r][c] for r in range(3)) for c in range(3)]
    expected = sum((row[i] / n) * (col[i] / n) for i in range(3))
    if expected >= 1.0:
        kappa = 1.0 if observed >= 1.0 else 0.0
    else:
        kappa = (observed - expected) / (1.0 - expected)
    return {
        "n": n,
        "labels": list(LABELS),
        "matrix": matrix,
        "observed_agreement": observed,
        "expected_agreement": expected,
        "kappa": kappa,
        "row_marginals": row,
        "col_marginals": col,
    }


def cohen_kappa(y_true: Sequence[str], y_pred: Sequence[str]) -> float:
    return float(agreement_table(y_true, y_pred)["kappa"])


def _percentile_indices(n_boot: int, alpha: float) -> tuple[int, int]:
    lo = int(math.floor((alpha / 2.0) * n_boot))
    hi = int(math.ceil((1.0 - alpha / 2.0) * n_boot) - 1)
    lo = max(0, min(n_boot - 1, lo))
    hi = max(0, min(n_boot - 1, hi))
    if hi < lo:
        hi = lo
    return lo, hi


def bootstrap_ci(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    *,
    seed: int = BOOTSTRAP_SEED,
    n_boot: int = BOOTSTRAP_N,
    alpha: float = CI_ALPHA,
) -> dict:
    """Percentile bootstrap CI. Uses an independent LCG so Python hash seed is irrelevant."""
    n = len(y_true)
    if n == 0:
        raise ValueError("empty series")
    stats: list[float] = []
    state = seed & 0xFFFFFFFF
    for _ in range(n_boot):
        idx: list[int] = []
        for _j in range(n):
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            idx.append(state % n)
        yt = [y_true[i] for i in idx]
        yp = [y_pred[i] for i in idx]
        stats.append(cohen_kappa(yt, yp))
    stats.sort()
    lo_i, hi_i = _percentile_indices(n_boot, alpha)
    point = cohen_kappa(y_true, y_pred)
    return {
        "method": "percentile-bootstrap",
        "seed": seed,
        "n_boot": n_boot,
        "alpha": alpha,
        "kappa": point,
        "ci_low": stats[lo_i],
        "ci_high": stats[hi_i],
        "lo_index": lo_i,
        "hi_index": hi_i,
    }


def accuracy(y_true: Iterable[str], y_pred: Iterable[str]) -> float:
    pairs = list(zip(y_true, y_pred))
    if not pairs:
        return 0.0
    return sum(1 for t, p in pairs if t == p) / len(pairs)
