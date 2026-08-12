"""Self-contained two-axis source rating and forecast calibration helpers.

Admiralty reliability (A-F) and information credibility (1-6) stay independent.
Forecast calibration is separate again: WEP labels always retain a numeric
probability, and Brier scores are computed only after binary outcomes resolve.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdmiraltyRating:
    reliability: str
    credibility: int
    reliability_reason: str
    credibility_reason: str

    def __post_init__(self) -> None:
        if self.reliability not in "ABCDEF" or len(self.reliability) != 1:
            raise ValueError("Admiralty reliability must be A-F")
        if not 1 <= self.credibility <= 6:
            raise ValueError("Admiralty credibility must be 1-6")
        if not self.reliability_reason or not self.credibility_reason:
            raise ValueError("Admiralty ratings require reasons for both axes")

    @property
    def code(self) -> str:
        return f"{self.reliability}{self.credibility}"


def conservative_admiralty() -> AdmiraltyRating:
    """Unknown source history and unevaluated claim default to F6."""
    return AdmiraltyRating(
        "F",
        6,
        "source reliability cannot yet be judged",
        "information credibility cannot yet be judged",
    )


def _validate_probability(probability: float) -> float:
    value = float(probability)
    if not 0.0 <= value <= 1.0:
        raise ValueError("probability must be within [0, 1]")
    return value


def wep_label(probability: float) -> str:
    """Map a numeric probability to this skill's explicit WEP scale."""
    value = _validate_probability(probability)
    if value < 0.05:
        return "almost no chance"
    if value < 0.20:
        return "very unlikely"
    if value < 0.45:
        return "unlikely"
    if value <= 0.55:
        return "roughly even chance"
    if value <= 0.80:
        return "likely"
    if value <= 0.95:
        return "very likely"
    return "almost certain"


def format_wep(probability: float) -> str:
    value = _validate_probability(probability)
    return f"{value:.0%} ({wep_label(value)})"


@dataclass(frozen=True, slots=True)
class Forecast:
    proposition: str
    probability: float
    resolution_criterion: str
    outcome: bool | None = None

    def __post_init__(self) -> None:
        if not self.proposition.strip():
            raise ValueError("forecast proposition is required")
        _validate_probability(self.probability)
        if not self.resolution_criterion.strip():
            raise ValueError("forecast resolution criterion is required")
        if self.outcome is not None and not isinstance(self.outcome, bool):
            raise ValueError("forecast outcome must be bool or None")


def brier_score(forecasts: tuple[Forecast, ...]) -> float | None:
    """Mean binary Brier score over resolved forecasts; unresolved are skipped."""
    resolved = [forecast for forecast in forecasts if forecast.outcome is not None]
    if not resolved:
        return None
    errors = [
        (forecast.probability - (1.0 if forecast.outcome else 0.0)) ** 2
        for forecast in resolved
    ]
    return sum(errors) / len(errors)
