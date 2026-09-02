#!/usr/bin/env python3
"""Deterministic Delphi feedback modes and the herding gate for CNL-0035."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

WEIGHT = {
    "direct_measurement": 9.0,
    "calibrated_proxy": 4.0,
    "unanchored_guess": 1.0,
}

MEDIAN_SHRINK = 0.5
MEDIAN_PLUS_GAMMA = 3.0
BIN_WIDTH = 10.0
VAR_COLLAPSE_RATIO = 0.5
MAE_IMPROVE_RATIO = 0.9

MODES = (
    "median_only",
    "full_distribution",
    "arguments",
    "median_plus_arguments",
)


def load_panel(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def private_signals(panel: dict) -> list[float]:
    return [float(a["private_signal"]) for a in panel["agents"]]


def evidence_classes(panel: dict) -> list[str]:
    return [str(a["evidence_class"]) for a in panel["agents"]]


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        raise ValueError("median of empty")
    if n % 2:
        return float(s[n // 2])
    return 0.5 * (s[n // 2 - 1] + s[n // 2])


def quartile_hinges(xs: list[float]) -> tuple[float, float, float]:
    s = sorted(xs)
    m = median(s)
    below = [v for v in s if v < m]
    above = [v for v in s if v > m]
    q1 = median(below) if below else m
    q3 = median(above) if above else m
    return q1, m, q3


def histogram(xs: list[float], width: float = BIN_WIDTH) -> dict[str, int]:
    counts: dict[str, int] = {}
    for x in xs:
        lo = int(x // width) * int(width)
        key = f"{lo}-{lo + int(width)}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: int(kv[0].split("-")[0])))


def occupancy(xs: list[float], x: float, width: float = BIN_WIDTH) -> int:
    lo = int(x // width) * int(width)
    return sum(1 for v in xs if int(v // width) * int(width) == lo)


def population_variance(xs: list[float]) -> float:
    n = len(xs)
    if n == 0:
        raise ValueError("variance of empty")
    mean = sum(xs) / n
    return sum((x - mean) ** 2 for x in xs) / n


def second_moment_variance(xs: list[float]) -> float:
    n = len(xs)
    if n == 0:
        raise ValueError("variance of empty")
    m1 = sum(xs) / n
    m2 = sum(x * x for x in xs) / n
    return m2 - m1 * m1


def mae(xs: list[float], theta: float) -> float:
    return sum(abs(x - theta) for x in xs) / len(xs)


def anonymous_arguments(panel: dict) -> list[dict[str, Any]]:
    rows = [
        {
            "evidence_class": a["evidence_class"],
            "private_signal": float(a["private_signal"]),
            "rationale_id": a["rationale_id"],
        }
        for a in panel["agents"]
    ]
    return sorted(
        rows, key=lambda r: (r["evidence_class"], r["private_signal"], r["rationale_id"])
    )


def weighted_pool(panel: dict, extra_median: float | None = None, gamma: float = 0.0) -> float:
    num = 0.0
    den = 0.0
    for a in panel["agents"]:
        w = WEIGHT[a["evidence_class"]]
        num += w * float(a["private_signal"])
        den += w
    n = len(panel["agents"])
    if extra_median is not None and gamma:
        num += gamma * n * extra_median
        den += gamma * n
    if den == 0:
        raise ValueError("zero weight")
    return num / den


def step(mode: str, panel: dict, xs: list[float]) -> list[float]:
    n = len(xs)
    med = median(xs)
    if mode == "median_only":
        a = MEDIAN_SHRINK
        return [(1.0 - a) * x + a * med for x in xs]
    if mode == "full_distribution":
        out = []
        for x in xs:
            occ = occupancy(xs, x)
            shrink = MEDIAN_SHRINK * (1.0 - occ / n)
            out.append((1.0 - shrink) * x + shrink * med)
        return out
    if mode == "arguments":
        target = weighted_pool(panel)
        return [target for _ in xs]
    if mode == "median_plus_arguments":
        target = weighted_pool(panel, extra_median=med, gamma=MEDIAN_PLUS_GAMMA)
        return [target for _ in xs]
    raise ValueError(f"unknown mode {mode}")


def herding_gate(
    var0: float,
    var1: float,
    mae0: float,
    mae1: float,
    classes: list[str],
) -> dict[str, Any]:
    collapsed = var1 < VAR_COLLAPSE_RATIO * var0
    differentiated = len(set(classes)) > 1
    improved = mae1 < MAE_IMPROVE_RATIO * mae0
    if not collapsed:
        return {
            "verdict": "NO_COLLAPSE",
            "herding": False,
            "reason": "variance-did-not-collapse",
            "collapsed": False,
            "evidence_differentiated": differentiated,
            "accuracy_improved": improved,
        }
    if not differentiated:
        return {
            "verdict": "HERDING",
            "herding": True,
            "reason": "collapse-with-homogeneous-evidence",
            "collapsed": True,
            "evidence_differentiated": False,
            "accuracy_improved": improved,
        }
    if not improved:
        return {
            "verdict": "HERDING",
            "herding": True,
            "reason": "collapse-without-accuracy-gain",
            "collapsed": True,
            "evidence_differentiated": True,
            "accuracy_improved": False,
        }
    return {
        "verdict": "REVISION",
        "herding": False,
        "reason": "collapse-with-accuracy-and-evidence",
        "collapsed": True,
        "evidence_differentiated": True,
        "accuracy_improved": True,
    }


def run_mode(panel: dict, mode: str, n_updates: int = 2) -> dict[str, Any]:
    xs = private_signals(panel)
    theta = float(panel["theta"])
    classes = evidence_classes(panel)
    rounds = [list(xs)]
    for _ in range(n_updates):
        xs = step(mode, panel, xs)
        rounds.append(list(xs))
    stats = []
    for rxs in rounds:
        stats.append(
            {
                "estimates": rxs,
                "median": median(rxs),
                "variance": population_variance(rxs),
                "variance_second_moment": second_moment_variance(rxs),
                "mae": mae(rxs, theta),
                "q1_q2_q3": list(quartile_hinges(rxs)),
                "histogram": histogram(rxs),
            }
        )
    gate = herding_gate(
        stats[0]["variance"],
        stats[1]["variance"],
        stats[0]["mae"],
        stats[1]["mae"],
        classes,
    )
    return {
        "mode": mode,
        "panel_id": panel["id"],
        "theta": theta,
        "n_agents": len(xs),
        "classes": classes,
        "rounds": stats,
        "gate_round1": gate,
        "anonymous_payload": anonymous_arguments(panel) if mode == "arguments" else None,
    }


def run_catalog_modes(panel: dict) -> dict[str, dict[str, Any]]:
    return {mode: run_mode(panel, mode) for mode in MODES}


def load_named(name: str) -> dict[str, Any]:
    return load_panel(FIXTURES / name)
