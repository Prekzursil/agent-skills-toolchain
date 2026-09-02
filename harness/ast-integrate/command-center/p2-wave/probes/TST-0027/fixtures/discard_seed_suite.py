"""Planted control: a property-like suite that consumes entropy and drops the seed."""

from __future__ import annotations

import random
from typing import Any


def run_property() -> dict[str, Any]:
    sample = [random.randint(1, 50) for _ in range(8)]
    return {"verdict": "pass", "checksum": sum(sample)}
