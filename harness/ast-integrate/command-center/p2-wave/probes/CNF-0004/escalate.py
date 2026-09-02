#!/usr/bin/env python3
"""CNF-0004 escalation engine.

Pre-fixed discrepancy-rate threshold plus one-shot whole-class census expansion.
Comparison is strictly greater-than: rate == threshold does not fire.

Expansion is intra-class and one-shot. Firing class A never enqueues class B.
A class already expanded is not re-enqueued.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any

# Pre-registered (spec 11041): detect a 10% class error rate. Not fitted to
# a confirmation corpus — there is no confirmation-receipt corpus on this tree.
THRESHOLD = 0.10
COMPARISON = "strictly_greater_than"
EPSILON = 1e-12
# n0 s.t. 1-(1-p)^n >= 0.90 for p=0.10 → n >= ln(0.10)/ln(0.90) ≈ 21.854
DETECT_N0 = 22
SAMPLE_SEED = 11041

SYNTH_CLASS = "SYNTH-EPSILON"
SYNTH_POPULATION = [f"SYNTH-{i:04d}" for i in range(1, 41)]
SYNTH_SAMPLE = SYNTH_POPULATION[:20]


@dataclass
class ExpansionDecision:
    class_id: str
    eligible_n: int
    discrepancy_n: int
    rate: float | None
    threshold: float
    comparison: str
    fired: bool
    reason: str
    requeued_ids: list[str]
    additional_ids: list[str]
    additional_count: int
    skipped_blocked: list[str]
    already_expanded: bool

    def as_json(self) -> dict[str, Any]:
        d = asdict(self)
        if d["rate"] is not None:
            d["rate"] = float(d["rate"])
        return d


def eligible_sample(sample_ids: list[str], blocked_ids: list[str]) -> list[str]:
    blocked = set(blocked_ids)
    return [i for i in sample_ids if i not in blocked]


def discrepancy_rate(
    discrepancy_ids: list[str], eligible_ids: list[str]
) -> tuple[float | None, int]:
    if not eligible_ids:
        return None, 0
    el = set(eligible_ids)
    counted = [i for i in discrepancy_ids if i in el]
    return len(counted) / len(eligible_ids), len(counted)


def exceeds(rate: float | None, threshold: float = THRESHOLD) -> bool:
    """Strict greater-than. None (no eligible sample) does not fire."""
    if rate is None:
        return False
    return rate > threshold


def finite_sample_n(population_n: int, n0: int = DETECT_N0) -> int:
    """Census a class no larger than n0; otherwise FPC of the power n0."""
    if population_n <= 0:
        return 0
    if population_n <= n0:
        return population_n
    n = n0 / (1.0 + (n0 - 1) / population_n)
    return min(population_n, max(1, int(math.ceil(n))))


def expand_ids(
    population_ids: list[str],
    sample_ids: list[str],
    *,
    fired: bool,
    already_expanded: bool,
) -> tuple[list[str], list[str]]:
    if already_expanded or not fired:
        return [], []
    sample = set(sample_ids)
    requeued = list(population_ids)
    additional = [i for i in population_ids if i not in sample]
    return requeued, additional


def evaluate(
    *,
    class_id: str,
    population_ids: list[str],
    sample_ids: list[str],
    discrepancy_ids: list[str] | None = None,
    blocked_ids: list[str] | None = None,
    rate_value: float | None = None,
    already_expanded: bool = False,
    threshold: float = THRESHOLD,
) -> ExpansionDecision:
    blocked = list(blocked_ids or [])
    eligible = eligible_sample(list(sample_ids), blocked)
    disc = [i for i in (discrepancy_ids or []) if i not in set(blocked)]
    computed, disc_n = discrepancy_rate(disc, eligible)
    rate = computed if rate_value is None else float(rate_value)
    if rate_value is not None:
        disc_n = -1
    if already_expanded:
        fired = False
        reason = "already-expanded-no-reenqueue"
    elif rate_value is None and not eligible:
        fired = False
        reason = "no-eligible-sample"
    elif exceeds(rate, threshold):
        fired = True
        reason = "rate-exceeds-threshold"
    else:
        fired = False
        reason = "rate-at-or-below-threshold"
    requeued, additional = expand_ids(
        list(population_ids),
        list(sample_ids),
        fired=fired,
        already_expanded=already_expanded,
    )
    return ExpansionDecision(
        class_id=class_id,
        eligible_n=len(eligible),
        discrepancy_n=disc_n,
        rate=rate,
        threshold=threshold,
        comparison=COMPARISON,
        fired=fired,
        reason=reason,
        requeued_ids=requeued,
        additional_ids=additional,
        additional_count=len(additional),
        skipped_blocked=blocked,
        already_expanded=already_expanded,
    )


def epsilon_pair(
    threshold: float = THRESHOLD, eps: float = EPSILON
) -> tuple[ExpansionDecision, ExpansionDecision]:
    minus = evaluate(
        class_id=SYNTH_CLASS,
        population_ids=list(SYNTH_POPULATION),
        sample_ids=list(SYNTH_SAMPLE),
        rate_value=threshold - eps,
        threshold=threshold,
    )
    plus = evaluate(
        class_id=SYNTH_CLASS,
        population_ids=list(SYNTH_POPULATION),
        sample_ids=list(SYNTH_SAMPLE),
        rate_value=threshold + eps,
        threshold=threshold,
    )
    return minus, plus


def integer_pair(
    threshold: float = THRESHOLD,
) -> tuple[ExpansionDecision, ExpansionDecision]:
    pop = list(SYNTH_POPULATION)
    sample = list(SYNTH_SAMPLE)
    below = evaluate(
        class_id=SYNTH_CLASS,
        population_ids=pop,
        sample_ids=sample,
        discrepancy_ids=sample[:1],
        threshold=threshold,
    )
    above = evaluate(
        class_id=SYNTH_CLASS,
        population_ids=pop,
        sample_ids=sample,
        discrepancy_ids=sample[:3],
        threshold=threshold,
    )
    return below, above


def exactly_at(threshold: float = THRESHOLD) -> ExpansionDecision:
    pop = list(SYNTH_POPULATION)
    sample = list(SYNTH_SAMPLE)
    return evaluate(
        class_id=SYNTH_CLASS,
        population_ids=pop,
        sample_ids=sample,
        discrepancy_ids=sample[:2],
        threshold=threshold,
    )


def blocked_flips_decision(threshold: float = THRESHOLD) -> dict[str, Any]:
    """2 discrepancies, 10 BLOCKED, sample 20: include=0.10 silent, exclude=0.20 fire."""
    pop = list(SYNTH_POPULATION)
    sample = list(SYNTH_SAMPLE)
    blocked = sample[10:20]
    disc = sample[:2]
    naive = evaluate(
        class_id=SYNTH_CLASS,
        population_ids=pop,
        sample_ids=sample,
        discrepancy_ids=disc,
        blocked_ids=[],
        threshold=threshold,
    )
    policy = evaluate(
        class_id=SYNTH_CLASS,
        population_ids=pop,
        sample_ids=sample,
        discrepancy_ids=disc,
        blocked_ids=blocked,
        threshold=threshold,
    )
    return {
        "naive_include_blocked": naive.as_json(),
        "policy_exclude_blocked": policy.as_json(),
        "decision_flipped": naive.fired != policy.fired,
    }


def cascade_control() -> dict[str, Any]:
    a_pop = [f"A-{i:02d}" for i in range(12)]
    b_pop = [f"B-{i:02d}" for i in range(12)]
    a_sample = a_pop[:6]
    b_sample = b_pop[:6]
    first = evaluate(
        class_id="A",
        population_ids=a_pop,
        sample_ids=a_sample,
        discrepancy_ids=a_sample[:3],
    )
    second_a = evaluate(
        class_id="A",
        population_ids=a_pop,
        sample_ids=a_sample,
        discrepancy_ids=a_sample[:3],
        already_expanded=True,
    )
    b = evaluate(
        class_id="B",
        population_ids=b_pop,
        sample_ids=b_sample,
        discrepancy_ids=[],
    )
    leaked_b = [i for i in first.requeued_ids if i.startswith("B-")]
    return {
        "a_fired": first.fired,
        "a_additional_count": first.additional_count,
        "a_requeue_second": second_a.requeued_ids,
        "b_fired": b.fired,
        "b_requeued": b.requeued_ids,
        "a_leaked_b_ids": leaked_b,
        "bounded": (
            first.fired
            and not second_a.fired
            and second_a.requeued_ids == []
            and not b.fired
            and b.requeued_ids == []
            and leaked_b == []
        ),
    }


def decisions_differ(a: ExpansionDecision, b: ExpansionDecision) -> bool:
    return json.dumps(a.as_json(), sort_keys=True) != json.dumps(
        b.as_json(), sort_keys=True
    )
