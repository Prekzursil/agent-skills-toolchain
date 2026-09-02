"""Declared quota used as an admission input (IMP-0221)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Quota:
    tokens_per_window: float
    window_s: float

    def rate_per_s(self) -> float:
        if self.window_s <= 0:
            return float(self.tokens_per_window)
        return float(self.tokens_per_window) / float(self.window_s)
