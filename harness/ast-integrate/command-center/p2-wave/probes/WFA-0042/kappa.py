"""Cohen's kappa over arbitrary string labels (per-dimension agreement)."""
from __future__ import annotations

from typing import Sequence


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    if len(a) != len(b):
        raise ValueError("kappa series length mismatch")
    n = len(a)
    if n == 0:
        raise ValueError("empty kappa series")
    labels = sorted(set(a) | set(b))
    idx = {lab: i for i, lab in enumerate(labels)}
    k = len(labels)
    matrix = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        matrix[idx[x]][idx[y]] += 1
    p_o = sum(matrix[i][i] for i in range(k)) / n
    row = [sum(matrix[i]) for i in range(k)]
    col = [sum(matrix[r][c] for r in range(k)) for c in range(k)]
    p_e = sum((row[i] / n) * (col[i] / n) for i in range(k))
    if p_e >= 1.0:
        return 1.0 if p_o >= 1.0 else 0.0
    return (p_o - p_e) / (1.0 - p_e)


def round6(value: float) -> float:
    return round(float(value), 6)
