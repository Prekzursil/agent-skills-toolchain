"""Binomial sample-size / detection-probability calculator.

Primary rule used by the sampling scheme:
  escalate if sample error rate > theta (strict).
For n=14 and theta=0.05, 1/n ~= 0.071 > 0.05, so the rule is equivalent to
escalate on any observed defect (X >= 1). Detection probability at prevalence p
is then 1-(1-p)^n (with-replacement / infinite-population binomial, which is
conservative versus hypergeometric without replacement).

Hand-check (must match code):
  p=0.20, confidence=0.95, miss=0.80
  0.80**13 = 0.0549755813888 > 0.05  -> n=13 insufficient
  0.80**14 = 0.04398046511104 <= 0.05 -> n=14 sufficient
  detection = 1-0.80**14 ~= 0.95602 >= 0.95
"""
from __future__ import annotations

import math
from typing import Any


def detection_probability(n: int, p: float) -> float:
    if n < 0:
        raise ValueError("n must be >= 0")
    if p < 0 or p > 1:
        raise ValueError("p must be in [0, 1]")
    if n == 0:
        return 0.0
    return 1.0 - (1.0 - p) ** n


def min_sample_size(p: float, confidence: float) -> int:
    """Smallest n such that 1-(1-p)^n >= confidence, escalate-on-any-error."""
    if not (0.0 < p < 1.0):
        raise ValueError("p must be in (0, 1)")
    if not (0.0 < confidence < 1.0):
        raise ValueError("confidence must be in (0, 1)")
    target_miss = 1.0 - confidence
    miss = 1.0 - p
    n = 1
    miss_n = miss
    while miss_n > target_miss:
        n += 1
        miss_n *= miss
        if n > 100_000:
            raise OverflowError("sample size did not converge")
    return n


def closed_form_min_n(p: float, confidence: float) -> int:
    """ceil(log(1-confidence)/log(1-p)), then clamp with the same inequality."""
    n = int(math.ceil(math.log(1.0 - confidence) / math.log(1.0 - p)))
    n = max(n, 1)
    while detection_probability(n, p) < confidence:
        n += 1
    while n > 1 and detection_probability(n - 1, p) >= confidence:
        n -= 1
    return n


def scheme_accepted(
    n: int, p: float, confidence: float
) -> dict[str, Any]:
    """Reject a scheme that would pass a p-defective class too often.

    'Pass' means fail to escalate (miss the class-wide defect). A scheme is
    accepted only if P(detect | prevalence=p) >= claimed confidence.
    """
    det = detection_probability(n, p)
    miss = 1.0 - det
    accepted = det >= confidence
    return {
        "n": n,
        "prevalence": p,
        "claimed_confidence": confidence,
        "detection_probability": det,
        "probability_pass_defective_class": miss,
        "accepted": accepted,
        "reason": (
            "detection_probability >= claimed_confidence"
            if accepted
            else (
                "REJECTED: scheme would pass a "
                f"{p:.0%}-defective class with probability {miss:.4f} "
                f">= {1.0 - confidence:.4f} miss budget"
            )
        ),
    }


def sensitivity_table(
    prevalences: tuple[float, ...] = (0.05, 0.10, 0.20, 0.50),
    confidences: tuple[float, ...] = (0.80, 0.90, 0.95, 0.99),
) -> list[dict[str, Any]]:
    rows = []
    for p in prevalences:
        for c in confidences:
            n = min_sample_size(p, c)
            rows.append(
                {
                    "prevalence": p,
                    "confidence": c,
                    "n": n,
                    "detection_probability": detection_probability(n, p),
                }
            )
    return rows


def hypergeometric_p_miss(N: int, K: int, n: int) -> float:
    """P(X=0) drawing n without replacement from N items with K defectives."""
    if n > N - K:
        return 0.0
    # P = C(N-K, n) / C(N, n) = product_{i=0..n-1} (N-K-i)/(N-i)
    num = 1.0
    for i in range(n):
        num *= (N - K - i) / (N - i)
    return num


def worked_example(p: float, confidence: float) -> dict[str, Any]:
    n13_miss = (1.0 - p) ** 13
    n14_miss = (1.0 - p) ** 14
    n = min_sample_size(p, confidence)
    n_closed = closed_form_min_n(p, confidence)
    if n != n_closed:
        raise RuntimeError(f"loop n={n} closed-form n={n_closed}")
    return {
        "formula": "smallest n s.t. (1-p)^n <= 1-confidence   [escalate on X>=1]",
        "p": p,
        "confidence": confidence,
        "miss_13": n13_miss,
        "miss_13_exceeds_budget": n13_miss > (1.0 - confidence),
        "miss_14": n14_miss,
        "miss_14_exceeds_budget": n14_miss > (1.0 - confidence),
        "n": n,
        "detection_probability": detection_probability(n, p),
        "closed_form_matches_loop": True,
        "hand_check": (
            f"0.80**13={n13_miss:.12f}>0.05; 0.80**14={n14_miss:.12f}<=0.05; n={n}"
        ),
    }
