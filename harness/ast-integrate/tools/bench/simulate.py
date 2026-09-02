"""Synthetic improvement campaigns (TST-0308): faithful vs gamed proxy metric.

The outcome is an independent deterministic end-state (fraction of cases whose
final artifact parses), never the metric itself. The gamed proxy is optimised
directly: its mean climbs every iteration while the end-state degrades and the
per-case coupling between proxy and outcome dissolves. The faithful proxy
tracks the end-state.
"""
from __future__ import annotations

from typing import Any

FAITHFUL_METRIC = "faithful-proxy"
GAMEABLE_METRIC = "gameable-proxy"
OUTCOME_ID = "true-outcome"
CAMPAIGN_KINDS = ("goodhart", "faithful")


def _lcg(seed: int):
    """Tiny deterministic generator in [0, 1) so campaigns replay byte-identically."""
    state = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    while True:
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        yield state / 0x7FFFFFFF


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def simulate_campaign(kind: str, *, n_cases: int, n_iters: int, seed: int) -> list[dict[str, Any]]:
    if kind not in CAMPAIGN_KINDS:
        raise ValueError(f"unknown campaign kind {kind!r}; expected one of {CAMPAIGN_KINDS}")
    if n_cases < 2 or n_iters < 1:
        raise ValueError("need at least 2 cases and 1 iteration")
    rng = _lcg(seed)
    rows: list[dict[str, Any]] = []
    for it in range(n_iters):
        # Optimiser pressure grows with iteration; the gamed proxy decouples.
        pressure = it / max(1, n_iters - 1)
        for c in range(n_cases):
            base = (c + 1) / (n_cases + 1)
            noise = next(rng) - 0.5
            faithful = _clip(base + it * 0.04 + noise * 0.02)
            if kind == "goodhart":
                # The proxy is what gets optimised: it climbs and its per-case
                # signal is replaced by optimiser noise; the true end-state slides.
                gameable = _clip((1 - pressure) * base + pressure * (0.5 + noise) + it * 0.08)
                outcome = _clip(base - it * 0.05 + noise * 0.01)
            else:
                gameable = _clip(base + it * 0.05 + noise * 0.02)
                outcome = _clip(base + it * 0.04 + noise * 0.01)
            rows.append(
                {
                    "campaign": kind,
                    "iteration": it,
                    "iter": it,
                    "case": c,
                    "case_id": f"case-{c:03d}",
                    "seed": seed,
                    "metrics": {
                        FAITHFUL_METRIC: round(faithful, 6),
                        GAMEABLE_METRIC: round(gameable, 6),
                    },
                    "outcomes": {OUTCOME_ID: round(outcome, 6)},
                    "outcome_kind": "deterministic-end-state",
                }
            )
    return rows
