from __future__ import annotations

from typing import Any


def load_example() -> dict[str, Any]:
    return {"question": "what shipped?", "window": "last-week"}


def run_outcome_retrospective() -> dict[str, Any]:
    ex = load_example()
    return {"ok": True, "example": ex, "deliberation_executed": False}
