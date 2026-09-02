"""Goodhart detector (TST-0308): metric rises while the end-state outcome falls.

A proxy metric is only trusted while it stays correlated with an independent,
deterministic end-state oracle across iterations of an improvement loop. The
detector needs a *series* (>= ``MIN_ITERATIONS``); a single snapshot is not
evidence of decay.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

MIN_ITERATIONS = 5
# Pearson drop across the series that counts as decoupling even if the outcome
# mean did not fall (a proxy that stops tracking the oracle is already gamed).
CORR_DECAY_THRESHOLD = 0.3


@dataclass
class Finding:
    fired: bool
    severity: str
    reason: str
    iterations: int = 0
    metric_gain: float = 0.0
    outcome_delta: float = 0.0
    corr_delta: float = 0.0
    first_r: float = 0.0
    last_r: float = 0.0
    rule: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


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


def _iteration_of(row: dict[str, Any]) -> int:
    for key in ("iteration", "iter"):
        if key in row:
            return int(row[key])
    raise KeyError("row has neither 'iteration' nor 'iter'")


def _metric_value(row: dict[str, Any], metric_id: str) -> float:
    metrics = row.get("metrics")
    if isinstance(metrics, dict) and metric_id in metrics:
        return float(metrics[metric_id])
    if row.get("metric_id") == metric_id and "metric_value" in row:
        return float(row["metric_value"])
    raise KeyError(metric_id)


def _outcome_value(row: dict[str, Any], outcome_id: str) -> float:
    outcomes = row.get("outcomes")
    if isinstance(outcomes, dict) and outcome_id in outcomes:
        return float(outcomes[outcome_id])
    if row.get("outcome_id") == outcome_id and "outcome_value" in row:
        return float(row["outcome_value"])
    raise KeyError(outcome_id)


def correlation_series(
    rows: list[dict[str, Any]], *, metric_id: str, outcome_id: str
) -> list[dict[str, Any]]:
    """Per-iteration Pearson r between the proxy metric and the end-state oracle."""
    by_iter: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_iter.setdefault(_iteration_of(row), []).append(row)
    series: list[dict[str, Any]] = []
    for it in sorted(by_iter):
        chunk = by_iter[it]
        xs = [_metric_value(r, metric_id) for r in chunk]
        ys = [_outcome_value(r, outcome_id) for r in chunk]
        r = _pearson(xs, ys)
        series.append(
            {
                "iteration": it,
                "iter": it,
                "n": len(chunk),
                "metric_id": metric_id,
                "outcome_id": outcome_id,
                "metric_mean": round(sum(xs) / len(xs), 6),
                "outcome_mean": round(sum(ys) / len(ys), 6),
                "pearson_r": round(r, 6),
                "corr": round(r, 6),
            }
        )
    return series


def _deltas(series: list[dict[str, Any]]) -> dict[str, float]:
    first, last = series[0], series[-1]
    return {
        "metric_gain": round(last["metric_mean"] - first["metric_mean"], 6),
        "outcome_delta": round(last["outcome_mean"] - first["outcome_mean"], 6),
        "corr_delta": round(last["pearson_r"] - first["pearson_r"], 6),
        "first_r": first["pearson_r"],
        "last_r": last["pearson_r"],
    }


def detect_goodhart(series: list[dict[str, Any]]) -> Finding:
    n = len(series)
    if n < MIN_ITERATIONS:
        return Finding(
            False,
            "INFO",
            f"too-short: {n} iteration(s) < {MIN_ITERATIONS}; a snapshot is not decay evidence",
            iterations=n,
            rule="min-iterations",
        )
    d = _deltas(series)
    if d["metric_gain"] > 0 and d["outcome_delta"] < 0:
        return Finding(
            True,
            "P1",
            "metric rose while end-state outcome fell",
            iterations=n,
            rule="metric-up-outcome-down",
            evidence={"series_len": n},
            **d,
        )
    if d["metric_gain"] > 0 and d["corr_delta"] <= -CORR_DECAY_THRESHOLD:
        return Finding(
            True,
            "P1",
            "metric rose while its correlation with the outcome decayed",
            iterations=n,
            rule="correlation-decay",
            evidence={"threshold": CORR_DECAY_THRESHOLD},
            **d,
        )
    return Finding(False, "P0", "aligned: metric and outcome move together", iterations=n, rule="aligned", **d)


def evaluate_metric_gain(
    series: list[dict[str, Any]], *, ignore_decay: bool = False
) -> dict[str, Any]:
    """Decide whether a metric gain may be celebrated.

    ``ignore_decay=True`` is the vacuous twin (detector control): it looks only
    at the metric and therefore celebrates a gamed proxy. The live evaluator
    consults ``detect_goodhart`` and refuses when the proxy decayed.
    """
    if not series:
        return {"gain": 0.0, "vacuous": True, "celebrate": False, "severity": "INFO", "reason": "empty"}
    gain = round(series[-1]["metric_mean"] - series[0]["metric_mean"], 6)
    if ignore_decay:
        return {
            "gain": gain,
            "vacuous": True,
            "decay_ignored": True,
            "celebrate": gain > 0,
            "severity": "VACUOUS",
            "reason": "metric-only view; outcome not consulted",
        }
    finding = detect_goodhart(series)
    decay = round(series[-1]["outcome_mean"] - series[0]["outcome_mean"], 6) if len(series) > 1 else 0.0
    celebrate = gain > 0 and decay >= 0 and not finding.fired
    return {
        "gain": gain,
        "outcome_delta": decay,
        "vacuous": False,
        "celebrate": celebrate,
        "severity": finding.severity if finding.fired else ("OK" if celebrate else "INFO"),
        "reason": finding.reason,
        "finding": finding.as_dict(),
    }
