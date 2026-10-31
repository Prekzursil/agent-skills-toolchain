"""Local-runner fan-in site. Judge is the shared reducer object."""
from __future__ import annotations

from typing import Any

from completion.reducer import LIBRARY, judge


def check_unit(payload: dict[str, Any]) -> dict[str, Any]:
    result = judge(payload)
    return {
        "verdict": result.verdict,
        "library": LIBRARY,
        "site": "local-runner",
        "reason": result.reason,
        "failing_condition_ids": result.failing_condition_ids or [],
        "not_checked_ids": result.not_checked_ids or [],
    }
