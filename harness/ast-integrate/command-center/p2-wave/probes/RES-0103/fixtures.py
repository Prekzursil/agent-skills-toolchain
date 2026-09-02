"""Deterministic calibrated (score, label) fixture for Chow probes."""
from __future__ import annotations

BUCKETS = (
    (0.95, 20, 20),
    (0.80, 20, 20),
    (0.60, 20, 12),
    (0.40, 20, 8),
    (0.20, 20, 4),
)


def calibrated_items() -> tuple[list[float], list[bool]]:
    scores: list[float] = []
    correct: list[bool] = []
    for s, n, n_ok in BUCKETS:
        scores.extend([s] * n)
        correct.extend([True] * n_ok + [False] * (n - n_ok))
    return scores, correct


calibrated_items = calibrated_items
