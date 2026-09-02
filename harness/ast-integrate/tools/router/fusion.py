"""Rank fusion and confidence calibration across the two matcher stages (IMP-0391).

The router has two matcher stages: the deterministic rule matcher
(``tools/router/rule_matcher.py``: keyword / glob / cwd-prefix / tool-verb) and
the semantic matcher (``tools/router/semantic_matcher.py``).  This module is the
seam between them and the confidence the router reports:

* ``rrf`` / ``fuse_rankings`` - reciprocal-rank fusion of the two stages' rank
  lists (``score(d) = w_det/(k+rank_det(d)) + w_sem/(k+rank_sem(d))``).
* ``linear_fuse`` - weighted fusion of two per-candidate stage scores, clipped to
  ``[0, 1]``.  This is the fused score the labelled corpus is scored with and the
  number the router displays as its confidence.
* ``reliability_diagram`` / ``brier_score`` / ``log_loss`` /
  ``calibration_report`` - the audit that decides whether that displayed number
  is a probability or merely a score: the fused scores are binned, and every
  occupied bin must have ``|observed_accuracy - predicted_confidence| <=
  CALIBRATION_TOLERANCE``.  The 0.9 band (``predicted >= BAND_0_9_FLOOR``) must
  be occupied and hold about 90 percent correct selections.
* ``mutation_control`` - the falsifier: with the calibrator held fixed, a
  sign-flipped pair of fusion weights must move at least one bin outside the
  tolerance and lower accuracy, otherwise the calibration test cannot fail and
  proves nothing.

Nothing here calls a model.  The labelled corpus the unit is measured on lives
with its probes (``command-center/p2-wave/probes/IMP-0391/corpus.py``); the
emitter recomputes the diagram through this module and refuses to write a
receipt when the two computations disagree.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

__all__ = [
    "BAND_0_9_FLOOR",
    "BIN_EDGES",
    "CALIBRATION_TOLERANCE",
    "DECISION_THRESHOLD",
    "DEFAULT_WEIGHTS",
    "RRF_K",
    "brier_score",
    "calibration_report",
    "clip01",
    "fuse_rankings",
    "linear_fuse",
    "log_loss",
    "mutation_control",
    "reliability_diagram",
    "rrf",
    "score_pairs",
]

# |observed_accuracy - predicted_confidence| a bin may show before it is named an
# outlier.  Shared with the unit's labelled corpus and both probes.
CALIBRATION_TOLERANCE: float = 0.15

# Production fusion weights: the deterministic stage carries the larger weight
# because its matches are exact role hits; the semantic stage breaks ties and
# recovers paraphrases.
DEFAULT_WEIGHTS: dict[str, float] = {"w_det": 0.65, "w_sem": 0.35}

# Reciprocal-rank-fusion damping constant (Cormack et al. 2009 use 60).
RRF_K: int = 60

# A fused score at or above this is a "selected" verdict.
DECISION_THRESHOLD: float = 0.5

# Reliability-diagram bins: [lo, hi).  The last edge is 1.01 so a fused score
# of exactly 1.0 lands in the top bin instead of falling off the diagram.
BIN_EDGES: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.01)

# Bins whose mean predicted confidence is at or above this form the 0.9 band.
BAND_0_9_FLOOR: float = 0.8

ScoredPair = tuple[float, int]


# -- fusion --------------------------------------------------------------------
def clip01(value: float) -> float:
    """Clamp ``value`` into ``[0.0, 1.0]``."""
    return max(0.0, min(1.0, float(value)))


def linear_fuse(det: float, sem: float, w_det: float, w_sem: float) -> float:
    """Weighted fusion of two stage scores, clipped to ``[0, 1]``.

    ``det`` is the deterministic stage's score for a candidate, ``sem`` the
    semantic stage's.  The result is what the router reports as confidence, so
    it is audited by :func:`calibration_report` rather than trusted.
    """
    return clip01(w_det * float(det) + w_sem * float(sem))


def rrf(rank_det: int | None, rank_sem: int | None, w_det: float, w_sem: float, k: int = RRF_K) -> float:
    """Reciprocal-rank fusion of one candidate's two ranks (1-based; None = absent)."""
    score = 0.0
    if rank_det is not None:
        score += w_det / (k + int(rank_det))
    if rank_sem is not None:
        score += w_sem / (k + int(rank_sem))
    return score


def fuse_rankings(
    det_ranking: Sequence[str],
    sem_ranking: Sequence[str],
    w_det: float = DEFAULT_WEIGHTS["w_det"],
    w_sem: float = DEFAULT_WEIGHTS["w_sem"],
    k: int = RRF_K,
) -> list[tuple[str, float]]:
    """Fuse two ordered candidate lists into one, best first.

    Ties break on the deterministic rank, then the semantic rank, then the id,
    so the output is a total order and two runs cannot disagree.
    """
    det_rank = {cid: i + 1 for i, cid in enumerate(det_ranking)}
    sem_rank = {cid: i + 1 for i, cid in enumerate(sem_ranking)}
    ids = list(dict.fromkeys([*det_ranking, *sem_ranking]))
    fused = [(cid, rrf(det_rank.get(cid), sem_rank.get(cid), w_det, w_sem, k)) for cid in ids]
    fused.sort(
        key=lambda row: (
            -row[1],
            det_rank.get(row[0], len(ids) + 1),
            sem_rank.get(row[0], len(ids) + 1),
            row[0],
        )
    )
    return fused


def score_pairs(
    pairs: Iterable[tuple[float, float, int]],
    w_det: float = DEFAULT_WEIGHTS["w_det"],
    w_sem: float = DEFAULT_WEIGHTS["w_sem"],
) -> list[ScoredPair]:
    """``(det, sem, label)`` rows -> ``(fused_score, label)`` rows."""
    return [(linear_fuse(det, sem, w_det, w_sem), int(bool(label))) for det, sem, label in pairs]


# -- calibration audit ---------------------------------------------------------
def brier_score(scored: Sequence[ScoredPair]) -> float:
    """Mean squared error between reported confidence and the 0/1 label."""
    if not scored:
        return 0.0
    return sum((p - y) ** 2 for p, y in scored) / len(scored)


def log_loss(scored: Sequence[ScoredPair], eps: float = 1e-12) -> float:
    """Mean negative log-likelihood, with confidences clipped away from 0 and 1."""
    if not scored:
        return 0.0
    total = 0.0
    for p, y in scored:
        q = min(max(float(p), eps), 1.0 - eps)
        total += -math.log(q) if y else -math.log(1.0 - q)
    return total / len(scored)


def reliability_diagram(
    scored: Sequence[ScoredPair],
    edges: Sequence[float] = BIN_EDGES,
    tolerance: float = CALIBRATION_TOLERANCE,
) -> dict[str, Any]:
    """Bin fused scores and compare mean confidence with observed accuracy.

    Returns ``bins`` (one row per ``[lo, hi)`` interval, empty bins included
    with ``n=0`` and ``observed_accuracy=None``), ``named_outlier_bins`` (the
    occupied bins whose ``delta`` exceeds ``tolerance``) and ``band_0_9`` (the
    occupied bins whose mean predicted confidence is at least
    :data:`BAND_0_9_FLOOR`).
    """
    bins: list[dict[str, Any]] = []
    outliers: list[dict[str, Any]] = []
    for i in range(len(edges) - 1):
        lo, hi = float(edges[i]), float(edges[i + 1])
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
        predicted = sum(p for p, _ in bucket) / len(bucket)
        observed = sum(y for _, y in bucket) / len(bucket)
        delta = abs(observed - predicted)
        row = {
            "lo": lo,
            "hi": hi,
            "n": len(bucket),
            "predicted": predicted,
            "observed_accuracy": observed,
            "delta": delta,
        }
        bins.append(row)
        if delta > tolerance:
            outliers.append(row)
    band = [b for b in bins if b["n"] and b["predicted"] >= BAND_0_9_FLOOR]
    return {"bins": bins, "named_outlier_bins": outliers, "band_0_9": band}


def calibration_report(
    scored: Sequence[ScoredPair],
    edges: Sequence[float] = BIN_EDGES,
    tolerance: float = CALIBRATION_TOLERANCE,
    threshold: float = DECISION_THRESHOLD,
) -> dict[str, Any]:
    """Everything a reviewer needs to re-derive the calibration verdict."""
    n = len(scored)
    n_correct = sum(int((p >= threshold) == bool(y)) for p, y in scored)
    diagram = reliability_diagram(scored, edges, tolerance)
    band = diagram["band_0_9"]
    band_ok = bool(band) and all(
        b["delta"] is None or float(b["delta"]) <= tolerance for b in band
    )
    return {
        "n": n,
        "n_correct": n_correct,
        "accuracy": (n_correct / n) if n else 0.0,
        "brier": brier_score(scored),
        "log_loss": log_loss(scored),
        "tolerance": tolerance,
        "decision_threshold": threshold,
        "reliability_diagram": diagram["bins"],
        "named_outlier_bins": diagram["named_outlier_bins"],
        "band_0_9": band,
        "band_0_9_occupied": bool(band),
        "band_0_9_within_tolerance": band_ok,
        "within_tolerance": not diagram["named_outlier_bins"],
        "calibrator": {
            "method": "identity-on-fused-score, histogram-audited",
            "fit_on": "nothing: the fused score is reported as-is and audited per bin",
            "edges": [float(e) for e in edges],
            "values": [b["observed_accuracy"] for b in diagram["bins"]],
            "counts": [b["n"] for b in diagram["bins"]],
        },
    }


def mutation_control(
    production: dict[str, Any],
    mutant: dict[str, Any],
    production_weights: dict[str, float],
    mutant_weights: dict[str, float],
    tolerance: float = CALIBRATION_TOLERANCE,
) -> dict[str, Any]:
    """Does the miscalibrated-weight mutant turn the calibration test red?"""
    prod_out = len(production.get("named_outlier_bins") or [])
    mut_out = len(mutant.get("named_outlier_bins") or [])
    return {
        "description": (
            "Hold the calibrator fixed and flip the sign of both fusion weights. "
            f"At least one reliability bin must leave the {tolerance:.2f} tolerance "
            "and accuracy must drop, or the calibration test could not fail."
        ),
        "production_weights": dict(production_weights),
        "mutant_weights": dict(mutant_weights),
        "production_outlier_count": prod_out,
        "mutant_outlier_count": mut_out,
        "mutant_moves_a_bin_outside_tolerance": mut_out > prod_out,
        "mutant_accuracy_drops": float(mutant.get("accuracy", 0.0)) < float(production.get("accuracy", 0.0)),
    }
