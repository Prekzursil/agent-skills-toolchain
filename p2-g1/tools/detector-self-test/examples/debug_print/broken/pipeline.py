"""A tiny module that accidentally left a debug print in the hot path."""

from __future__ import annotations

from collections.abc import Iterable


def summarize(values: Iterable[float]) -> float:
    total = sum(values)
    print("DEBUG total:", total)
    return total
