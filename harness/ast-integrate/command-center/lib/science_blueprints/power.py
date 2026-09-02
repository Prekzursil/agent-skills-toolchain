"""Power thresholds. Per-run override is refused."""
from __future__ import annotations


class PerRunThresholdTuneError(ValueError):
    pass


THRESHOLD_ID = "imp-0251-science-stats-v1"
THRESHOLD_VERSION = "1.0.0"


def load_thresholds() -> dict:
    """Return the frozen, library-owned power/alpha threshold spec.

    The spec is identified (``id``/``version``) so a review can cite which
    threshold it was scored against; it is never tuned per run (see
    :class:`PerRunThresholdTuneError`).
    """
    return {
        "id": THRESHOLD_ID,
        "version": THRESHOLD_VERSION,
        "min_power": 0.8,
        "alpha": 0.05,
        "two_sided": True,
        "frozen": True,
        "not_tuned_per_run": True,
        "source": "library",
    }
