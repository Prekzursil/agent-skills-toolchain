"""Synthetic paired observations (TST-0298)."""
from __future__ import annotations

from typing import Any


def synthetic_pairs(n: int, effect: float, sd: float = 20.0, seed: int = 298) -> list[dict[str, Any]]:
    # Deterministic paired observations with mean delta ~ effect.
    rows = []
    for i in range(int(n)):
        # tiny deterministic noise, mean preserved
        noise = ((i * 17 + seed) % 11) - 5
        a = 50.0 + noise
        b = a + float(effect)
        rows.append({"id": f"case-{i:03d}", "a": a, "b": b, "delta": b - a})
    return rows
