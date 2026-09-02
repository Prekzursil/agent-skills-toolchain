"""Deterministic public-vs-revealed convergence for a roster.

Public channel follows assigned_stance when present (the performed debate).
Revealed channel follows locked prior only (the belief the seat actually holds).
The update rule is the same on both channels; only the anchor differs.
Thresholds are declared in fixtures.json and re-read here before scoring.
"""
from __future__ import annotations

from typing import Any

from priors import prior_confidence, prior_polarity, stance_polarity

DEFAULTS = {
    "THEATRE_PUBLIC_MIN": 1.0,
    "THEATRE_REVEALED_MAX": 0.25,
    "REAL_PUBLIC_MIN": 1.0,
    "REAL_REVEALED_MIN": 1.0,
    "MEASURABLE_REVEALED_GAP": 0.5,
    "ROUNDS": 8,
    "ALPHA": 0.35,
}


def pairwise_mean_abs(votes: list[float]) -> float:
    n = len(votes)
    if n < 2:
        return 0.0
    total = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += abs(votes[i] - votes[j])
            count += 1
    return total / count


def _step(
    anchors: list[float],
    confidences: list[float],
    prev: list[float],
    alpha: float,
) -> list[float]:
    n = len(anchors)
    out: list[float] = []
    for i in range(n):
        others = [prev[j] for j in range(n) if j != i]
        mean_o = (sum(others) / len(others)) if others else anchors[i]
        social = (1.0 - confidences[i]) * alpha
        out.append((1.0 - social) * anchors[i] + social * mean_o)
    return out


def public_anchor(seat: dict[str, Any]) -> float:
    stance = stance_polarity(seat.get("assigned_stance"))
    if stance is not None:
        return stance
    return prior_polarity(seat)


def revealed_anchor(seat: dict[str, Any]) -> float:
    return prior_polarity(seat)


def run_roster(
    seats: list[dict[str, Any]],
    rounds: int = 8,
    alpha: float = 0.35,
) -> dict[str, Any]:
    pub_a = [public_anchor(s) for s in seats]
    rev_a = [revealed_anchor(s) for s in seats]
    conf = [prior_confidence(s) for s in seats]
    public = pub_a[:]
    revealed = rev_a[:]
    pub_hist = [public[:]]
    rev_hist = [revealed[:]]
    for _ in range(int(rounds)):
        public = _step(pub_a, conf, public, float(alpha))
        revealed = _step(rev_a, conf, revealed, float(alpha))
        pub_hist.append(public[:])
        rev_hist.append(revealed[:])
    pub_dis = pairwise_mean_abs(public)
    rev_dis = pairwise_mean_abs(revealed)
    return {
        "seat_ids": [str(s.get("seat_id")) for s in seats],
        "public_final": public,
        "revealed_final": revealed,
        "public_disagreement": pub_dis,
        "revealed_disagreement": rev_dis,
        "channel_gap": abs(pub_dis - rev_dis),
        "rounds": int(rounds),
        "alpha": float(alpha),
    }


def theatre_signature(measured: dict[str, Any], thr: dict[str, float]) -> bool:
    return (
        measured["public_disagreement"] >= thr["THEATRE_PUBLIC_MIN"]
        and measured["revealed_disagreement"] <= thr["THEATRE_REVEALED_MAX"]
    )


def real_signature(measured: dict[str, Any], thr: dict[str, float]) -> bool:
    return (
        measured["public_disagreement"] >= thr["REAL_PUBLIC_MIN"]
        and measured["revealed_disagreement"] >= thr["REAL_REVEALED_MIN"]
    )


def thresholds_from_fixtures(doc: dict[str, Any]) -> dict[str, float]:
    raw = dict(DEFAULTS)
    raw.update(doc.get("thresholds_declared_before_scoring") or {})
    return {k: float(v) for k, v in raw.items()}
