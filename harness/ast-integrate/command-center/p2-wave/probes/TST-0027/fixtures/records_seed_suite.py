"""Planted control: a property-like suite that records its seed in the result."""

from __future__ import annotations

import random
from typing import Any


def run_property(seed: str = "planted-good") -> dict[str, Any]:
    rng = random.Random(seed)
    sample = [rng.randint(1, 50) for _ in range(8)]
    return {"seed": seed, "verdict": "pass", "checksum": sum(sample)}
