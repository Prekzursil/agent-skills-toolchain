"""Planted paired-run scenarios for the three-outcome gate."""
from __future__ import annotations

from typing import Any


def _pair(n: int, delta: float, secondary_delta: float = 0.0) -> list[dict[str, Any]]:
    rows = []
    for i in range(n):
        control = 1.0
        rows.append(
            {
                "i": i,
                "control": control,
                "treatment": control + delta,
                "secondary_control": 1.0,
                "secondary_treatment": 1.0 + secondary_delta,
            }
        )
    return rows


def noop_cases(n: int) -> list[dict[str, Any]]:
    return _pair(n, 0.0, 0.0)


def underpowered_cases(n: int) -> list[dict[str, Any]]:
    return _pair(n, 0.25, 0.0)


def improvement_cases(n: int) -> list[dict[str, Any]]:
    return _pair(n, 0.25, 0.02)


def secondary_regression_cases(n: int) -> list[dict[str, Any]]:
    return _pair(n, 0.25, -0.30)
