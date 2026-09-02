"""Cohen's kappa over categorical labels. Computed, never asserted."""
from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence


def cohen_kappa(y1: Sequence[str], y2: Sequence[str], labels: Iterable[str]) -> dict:
    if len(y1) != len(y2):
        raise ValueError("rater-length-mismatch")
    n = len(y1)
    if n < 1:
        raise ValueError("empty-ratings")
    labs = list(labels)
    agree = sum(1 for a, b in zip(y1, y2) if a == b)
    p_o = agree / n
    c1 = Counter(y1)
    c2 = Counter(y2)
    p_e = 0.0
    for lab in labs:
        p_e += (c1.get(lab, 0) / n) * (c2.get(lab, 0) / n)
    if p_e >= 1.0:
        kappa = 1.0 if p_o >= 1.0 else 0.0
    else:
        kappa = (p_o - p_e) / (1.0 - p_e)
    matrix: dict[str, dict[str, int]] = {a: {b: 0 for b in labs} for a in labs}
    extra_a = sorted(set(y1) - set(labs))
    extra_b = sorted(set(y2) - set(labs))
    for a in extra_a:
        matrix.setdefault(a, {b: 0 for b in list(labs) + extra_b})
    for b in extra_b:
        for row in matrix.values():
            row.setdefault(b, 0)
    for a, b in zip(y1, y2):
        matrix.setdefault(a, {})
        matrix[a][b] = matrix[a].get(b, 0) + 1
    return {
        "n": n,
        "labels": labs,
        "observed_agreement": round(p_o, 12),
        "expected_agreement": round(p_e, 12),
        "kappa": round(kappa, 12),
        "agree_n": agree,
        "disagree_n": n - agree,
        "confusion": matrix,
        "marginal_a": {k: int(v) for k, v in sorted(c1.items())},
        "marginal_b": {k: int(v) for k, v in sorted(c2.items())},
        "formula": "kappa = (p_o - p_e) / (1 - p_e) with p_e = sum_k p1_k p2_k",
    }
