"""Goodhart detector: metric rises while outcome falls across iterations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

MIN_ITERATIONS = 5


@dataclass
class Finding:
    fired: bool
    severity: str
    reason: str


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def correlation_series(rows: list[dict[str, Any]], *, metric_id: str, outcome_id: str) -> list[dict[str, Any]]:
    by_iter: dict[int, list] = {}
    for row in rows:
        by_iter.setdefault(int(row["iter"]), []).append(row)
    series = []
    for it in sorted(by_iter):
        chunk = by_iter[it]
        xs = [float(r["metrics"][metric_id]) for r in chunk]
        ys = [float(r["outcomes"][outcome_id]) for r in chunk]
        series.append(
            {
                "iter": it,
                "metric_mean": sum(xs) / len(xs),
                "outcome_mean": sum(ys) / len(ys),
                "corr": _pearson(xs, ys),
            }
        )
    return series


def detect_goodhart(series: list[dict[str, Any]]) -> Finding:
    if len(series) < MIN_ITERATIONS:
        return Finding(False, "INFO", "too-short")
    m0, m1 = series[0]["metric_mean"], series[-1]["metric_mean"]
    o0, o1 = series[0]["outcome_mean"], series[-1]["outcome_mean"]
    if m1 > m0 and o1 < o0:
        return Finding(True, "P1", "metric rose while outcome fell")
    return Finding(False, "P0", "aligned")


def evaluate_metric_gain(series: list[dict[str, Any]], *, ignore_decay: bool = False) -> dict[str, Any]:
    if not series:
        return {"gain": 0.0, "vacuous": True}
    gain = series[-1]["metric_mean"] - series[0]["metric_mean"]
    decay = series[-1]["outcome_mean"] - series[0]["outcome_mean"]
    if ignore_decay:
        return {"gain": gain, "vacuous": True, "decay_ignored": True, "celebrate": True}
    celebrate = gain > 0 and decay >= 0
    return {"gain": gain, "outcome_delta": decay, "vacuous": False, "celebrate": celebrate}
