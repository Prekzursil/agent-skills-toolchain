"""Live router cost and quality curves for ADV-0115."""
from __future__ import annotations

import time
from typing import Any

import common as C
import flood_detector as FD

from router.injection_budget import (  # noqa: E402
    HARD_CEILING_TOKENS,
    adversarial_k40,
    budget_inject,
    naive_inject,
)
from router.tokenizer import char_quarter_estimate, count_tokens  # noqa: E402


def _time_arm(caps, arm: str, trials: int, warmup: int) -> dict[str, Any]:
    def run_once():
        if arm == "disabled":
            return {
                "measured_tokens": 0,
                "selected": 0,
                "refused": 0,
                "payload": "",
            }
        if arm == "naive":
            decision = naive_inject(caps)
        else:
            decision = budget_inject(caps)
        return {
            "measured_tokens": int(decision.measured_tokens),
            "selected": len(decision.selected_ids),
            "refused": len(decision.refused),
            "payload": decision.payload,
        }

    for _ in range(warmup):
        run_once()
    samples_ms: list[float] = []
    last = None
    for _ in range(trials):
        t0 = time.perf_counter_ns()
        last = run_once()
        samples_ms.append((time.perf_counter_ns() - t0) / 1_000_000.0)
    assert last is not None
    measured = int(last["measured_tokens"])
    payload = last["payload"]
    tokenizer_count = count_tokens(payload) if payload else 0
    return {
        "arm": arm,
        "measured_tokens": measured,
        "tokenizer_count": tokenizer_count,
        "char_quarter_estimate": char_quarter_estimate(payload) if payload else 0,
        "selected": last["selected"],
        "refused": last["refused"],
        "flood_red": C.flood_red(measured),
        "latency_ms": C.summarize_ms(samples_ms),
        "samples_ms": [round(x, 6) for x in samples_ms],
    }


def cost_curve(live: list[dict[str, str]] | None = None) -> dict[str, Any]:
    live = live if live is not None else C.live_platform_records()
    points: list[dict[str, Any]] = []
    for n in C.SIZES:
        caps = C.catalogue_for_cost(n, live)
        n_hot = sum(1 for c in caps if c.score >= C.SCORE_THRESHOLD)
        disabled = _time_arm(caps, "disabled", C.N_TRIALS, C.WARMUP)
        naive = _time_arm(caps, "naive", C.N_TRIALS, C.WARMUP)
        budgeted = _time_arm(caps, "budgeted", C.N_TRIALS, C.WARMUP)
        added_p50 = budgeted["latency_ms"]["p50"] - disabled["latency_ms"]["p50"]
        points.append(
            {
                "catalogue_size": n,
                "n_above_threshold": n_hot,
                "disabled": disabled,
                "naive": naive,
                "budgeted": budgeted,
                "added_latency_p50_ms": added_p50,
                "token_delta_budgeted_minus_disabled": (
                    budgeted["measured_tokens"] - disabled["measured_tokens"]
                ),
            }
        )
    budgeted_tokens = [p["budgeted"]["measured_tokens"] for p in points]
    naive_tokens = [p["naive"]["measured_tokens"] for p in points]
    first_naive_flood = next(
        (p["catalogue_size"] for p in points if p["naive"]["flood_red"]), None
    )
    bounded_ever_flood = any(p["budgeted"]["flood_red"] for p in points)
    return {
        "sizes": list(C.SIZES),
        "trials": C.N_TRIALS,
        "ceiling": HARD_CEILING_TOKENS,
        "points": points,
        "budgeted_token_curve": budgeted_tokens,
        "naive_token_curve": naive_tokens,
        "first_naive_flood_size": first_naive_flood,
        "bounded_crossed_ceiling": bounded_ever_flood,
        "dispersion_reported": True,
    }


def quality_curve(
    live: list[dict[str, str]] | None = None,
    tasks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    live = live if live is not None else C.live_platform_records()
    tasks = tasks if tasks is not None else C.load_task_set()
    points: list[dict[str, Any]] = []
    for n in C.SIZES:
        rows = C.catalogue_for_quality(n, tasks, live)
        hits = 0
        disabled_hits = 0
        rotated_hits = 0
        injected_tokens: list[int] = []
        for i, task in enumerate(tasks):
            caps = C.score_for_task(rows, task)
            disabled_choice = C.answer_from_injection(task, [])
            if disabled_choice == task["gold_id"]:
                disabled_hits += 1
            decision = budget_inject(caps)
            injected_tokens.append(int(decision.measured_tokens))
            selected = [
                c for c in caps if c.capability_id in set(decision.selected_ids)
            ]
            choice = C.answer_from_injection(task, selected)
            if choice == task["gold_id"]:
                hits += 1
            rotated_gold = tasks[(i + 1) % len(tasks)]["gold_id"]
            if choice == rotated_gold:
                rotated_hits += 1
        n_tasks = len(tasks)
        points.append(
            {
                "catalogue_size": n,
                "n_tasks": n_tasks,
                "hits": hits,
                "accuracy": hits / n_tasks,
                "disabled_hits": disabled_hits,
                "disabled_accuracy": disabled_hits / n_tasks,
                "rotated_hits": rotated_hits,
                "rotated_accuracy": rotated_hits / n_tasks,
                "injected_tokens_p50": C.percentile(
                    [float(x) for x in injected_tokens], 50
                ),
                "injected_tokens_max": max(injected_tokens),
                "flood_red_any": any(C.flood_red(t) for t in injected_tokens),
            }
        )
    gold_acc = [p["accuracy"] for p in points]
    rotated_acc = [p["rotated_accuracy"] for p in points]
    disabled_acc = [p["disabled_accuracy"] for p in points]
    return {
        "sizes": list(C.SIZES),
        "n_tasks": len(tasks),
        "points": points,
        "gold_accuracy_curve": gold_acc,
        "rotated_accuracy_curve": rotated_acc,
        "disabled_accuracy_curve": disabled_acc,
        "rotated_degrades": max(rotated_acc) < min(gold_acc),
        "disabled_below_gold": max(disabled_acc) < min(gold_acc),
        "quality_degraded_with_size": gold_acc[-1] < gold_acc[0] - 1e-9,
    }


def skills_context_precedent() -> dict[str, Any]:
    caps = adversarial_k40()
    naive = naive_inject(caps)
    budgeted = budget_inject(caps)
    naive_tokens = count_tokens(naive.payload)
    budgeted_tokens = count_tokens(budgeted.payload)
    return {
        "k": 40,
        "ceiling": HARD_CEILING_TOKENS,
        "naive_tokens": naive_tokens,
        "budgeted_tokens": budgeted_tokens,
        "naive_equals_char_quarter": naive_tokens == char_quarter_estimate(naive.payload),
        "overflow_reproduced": naive_tokens > HARD_CEILING_TOKENS,
        "overflow_prevented": (
            naive_tokens > HARD_CEILING_TOKENS and budgeted_tokens <= HARD_CEILING_TOKENS
        ),
        "budgeted_within_ceiling": budgeted_tokens <= HARD_CEILING_TOKENS,
        "refused": len(budgeted.refused),
    }


def build_measurements() -> dict[str, Any]:
    live = C.live_platform_records()
    tasks = C.load_task_set()
    cost = cost_curve(live)
    quality = quality_curve(live, tasks)
    flood = FD.both_states()
    precedent = skills_context_precedent()
    return {
        "live_n": len(live),
        "live_kinds": sorted({r["kind"] for r in live}),
        "cost": cost,
        "quality": quality,
        "flood": flood,
        "precedent": precedent,
        "ceiling": HARD_CEILING_TOKENS,
    }
