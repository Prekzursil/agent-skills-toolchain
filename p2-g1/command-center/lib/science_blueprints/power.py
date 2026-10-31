"""Power thresholds. Per-run override is refused."""
from __future__ import annotations


class PerRunThresholdTuneError(ValueError):
    pass


def load_thresholds() -> dict:
    return {"min_power": 0.8, "alpha": 0.05, "source": "library"}
