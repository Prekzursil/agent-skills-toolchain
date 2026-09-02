"""Synthetic campaigns: faithful vs gamed metric."""
from __future__ import annotations

from typing import Any

FAITHFUL_METRIC = "faithful-proxy"
GAMEABLE_METRIC = "gameable-proxy"
OUTCOME_ID = "true-outcome"


def simulate_campaign(kind: str, *, n_cases: int, n_iters: int, seed: int) -> list[dict[str, Any]]:
    rows = []
    for it in range(n_iters):
        for c in range(n_cases):
            base = (c + 1) / n_cases
            if kind == "goodhart":
                metric = base + it * 0.08
                outcome = base - it * 0.05
            else:
                metric = base + it * 0.05
                outcome = base + it * 0.04
            rows.append(
                {
                    "iter": it,
                    "case": c,
                    "metrics": {
                        FAITHFUL_METRIC: base + it * 0.05,
                        GAMEABLE_METRIC: metric,
                    },
                    "outcomes": {OUTCOME_ID: outcome},
                }
            )
    return rows
