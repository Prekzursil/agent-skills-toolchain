"""Monte Carlo and exact checks for class-wide defect detection and escalation."""
from __future__ import annotations

import random
from typing import Any

from power import detection_probability, hypergeometric_p_miss


def escalate(sample_error_rate: float, theta: float) -> bool:
    """Spec :11041 — expand iff sampled error rate EXCEEDS the threshold."""
    return sample_error_rate > theta


def sample_error_rate(labels: list[bool]) -> float:
    if not labels:
        raise ValueError("empty sample")
    return sum(1 for x in labels if x) / float(len(labels))


def inject_class(n_units: int, prevalence: float, rng: random.Random) -> list[bool]:
    k = int(round(prevalence * n_units))
    k = min(max(k, 0), n_units)
    labels = [True] * k + [False] * (n_units - k)
    rng.shuffle(labels)
    return labels


def draw_sample(labels: list[bool], n: int, rng: random.Random) -> list[bool]:
    if n > len(labels):
        raise ValueError("sample larger than class")
    idx = rng.sample(range(len(labels)), n)
    return [labels[i] for i in idx]


def monte_carlo_detection(
    class_size: int,
    prevalence: float,
    n_sample: int,
    theta: float,
    trials: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    hits = 0
    for _ in range(trials):
        labels = inject_class(class_size, prevalence, rng)
        sample = draw_sample(labels, n_sample, rng)
        if escalate(sample_error_rate(sample), theta):
            hits += 1
    emp = hits / trials
    k = int(round(prevalence * class_size))
    exact_miss = hypergeometric_p_miss(class_size, k, n_sample)
    exact_det = 1.0 - exact_miss
    binom_det = detection_probability(n_sample, prevalence)
    return {
        "trials": trials,
        "seed": seed,
        "class_size": class_size,
        "prevalence": prevalence,
        "n_sample": n_sample,
        "theta": theta,
        "empirical_detection": emp,
        "hypergeometric_detection": exact_det,
        "binomial_detection": binom_det,
        "hits": hits,
    }


def escalation_fixture(n: int, n_bad: int, theta: float) -> dict[str, Any]:
    rate = n_bad / float(n)
    fired = escalate(rate, theta)
    return {
        "n": n,
        "n_bad": n_bad,
        "sample_error_rate": rate,
        "theta": theta,
        "fired": fired,
        "comparison": "strict_greater_than",
    }
