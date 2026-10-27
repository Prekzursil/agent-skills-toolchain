"""Statistical review both-states fixtures."""
from __future__ import annotations

from science_blueprints.power import PerRunThresholdTuneError, load_thresholds


def underpowered_fixture() -> dict:
    return {"id": "underpowered", "n": 8, "effect_size": 0.2, "alpha": 0.05}


def powered_fixture() -> dict:
    return {"id": "powered", "n": 128, "effect_size": 0.5, "alpha": 0.05}


def missing_effect_size_fixture() -> dict:
    return {"id": "bare", "n": 128, "alpha": 0.05}


def _power(n: float, d: float) -> float:
    # Rough two-sample power stand-in: saturates at 1, underpowered for small n*d.
    return max(0.0, min(1.0, (n ** 0.5) * abs(d) / 5.0))


def review(fixture: dict, threshold_override: float | None = None) -> dict:
    if threshold_override is not None:
        raise PerRunThresholdTuneError("per-run power threshold refused")
    spec = load_thresholds()
    d = fixture.get("effect_size")
    n = float(fixture.get("n") or 0)
    pwr = None if d is None else _power(n, float(d))
    flags = [
        {
            "id": "underpowered",
            "flagged": pwr is not None and pwr < float(spec["min_power"]),
        },
        {
            "id": "missing-effect-size",
            "flagged": d is None,
        },
    ]
    return {
        "flags": flags,
        "flagged": any(bool(f.get("flagged")) for f in flags),
        "power": pwr,
        "threshold": spec,
        "fixture_id": fixture.get("id"),
    }
