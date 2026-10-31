from __future__ import annotations

from typing import Any


def load_example() -> dict[str, Any]:
    return {"sku": "council-runtime", "tier": "standard"}


def run_pricing_packaging() -> dict[str, Any]:
    return {"ok": True, "example": load_example(), "deliberation_executed": False}
