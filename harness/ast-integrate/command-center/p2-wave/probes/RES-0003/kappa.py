#!/usr/bin/env python3
"""Cohen's kappa and a printable confusion matrix. Computed, not asserted."""
from __future__ import annotations

from typing import Iterable, Sequence

from grader import LABELS


def confusion(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str] = LABELS) -> list[list[int]]:
    if len(gold) != len(pred):
        raise ValueError("gold/pred length mismatch")
    idx = {lab: i for i, lab in enumerate(labels)}
    m = [[0] * len(labels) for _ in labels]
    for g, p in zip(gold, pred):
        if g not in idx or p not in idx:
            raise ValueError(f"unknown label gold={g!r} pred={p!r}")
        m[idx[g]][idx[p]] += 1
    return m


def observed_agreement(matrix: Sequence[Sequence[int]]) -> float:
    n = sum(sum(row) for row in matrix)
    if n == 0:
        return 0.0
    return sum(matrix[i][i] for i in range(len(matrix))) / n


def expected_agreement(matrix: Sequence[Sequence[int]]) -> float:
    n = sum(sum(row) for row in matrix)
    if n == 0:
        return 0.0
    k = len(matrix)
    gold_m = [sum(matrix[i][j] for j in range(k)) for i in range(k)]
    pred_m = [sum(matrix[i][j] for i in range(k)) for j in range(k)]
    return sum((gold_m[i] / n) * (pred_m[i] / n) for i in range(k))


def cohen_kappa(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str] = LABELS) -> float:
    m = confusion(gold, pred, labels)
    po = observed_agreement(m)
    pe = expected_agreement(m)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1.0 - pe)


def format_matrix(matrix: Sequence[Sequence[int]], labels: Sequence[str] = LABELS) -> str:
    header = "gold\\pred " + " ".join(f"{lab:>4}" for lab in labels)
    lines = [header]
    for i, lab in enumerate(labels):
        cells = " ".join(f"{matrix[i][j]:4d}" for j in range(len(labels)))
        lines.append(f"{lab:>9} {cells}")
    return "\n".join(lines)


def matrix_as_records(matrix: Sequence[Sequence[int]], labels: Sequence[str] = LABELS) -> list[dict]:
    out = []
    for i, g in enumerate(labels):
        for j, p in enumerate(labels):
            out.append({"gold": g, "pred": p, "n": int(matrix[i][j])})
    return out


def permute(labels_in: Iterable[str], seed: int = 1) -> list[str]:
    """Deterministic shuffle for the chance-control (kappa near 0)."""
    items = list(labels_in)
    # Park-Miller LCG; no extra imports.
    x = seed % 2147483647 or 1
    for i in range(len(items) - 1, 0, -1):
        x = (x * 48271) % 2147483647
        j = x % (i + 1)
        items[i], items[j] = items[j], items[i]
    return items
