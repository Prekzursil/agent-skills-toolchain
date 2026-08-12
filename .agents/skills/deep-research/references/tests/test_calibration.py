"""Self-contained Admiralty and forecast-calibration tests."""

import pytest

from research_harness.calibration import (
    AdmiraltyRating,
    Forecast,
    brier_score,
    conservative_admiralty,
    format_wep,
    wep_label,
)


def test_admiralty_axes_are_independent_and_allow_a5_and_e1():
    assert AdmiraltyRating("A", 5, "history", "implausible").code == "A5"
    assert AdmiraltyRating("E", 1, "weak history", "independently confirmed").code == "E1"


def test_unknown_evidence_defaults_conservatively_to_f6():
    assert conservative_admiralty().code == "F6"


@pytest.mark.parametrize(("reliability", "credibility"), [("G", 1), ("A", 0), ("A", 7)])
def test_invalid_admiralty_values_raise(reliability, credibility):
    with pytest.raises(ValueError):
        AdmiraltyRating(reliability, credibility, "r", "c")


def test_wep_always_keeps_numeric_probability():
    assert wep_label(0.5) == "roughly even chance"
    assert format_wep(0.8).startswith("80%")
    assert "likely" in format_wep(0.8)


def test_invalid_probability_raises():
    with pytest.raises(ValueError):
        wep_label(1.1)


def test_brier_score_uses_only_resolved_binary_forecasts():
    forecasts = (
        Forecast("certain true", 1.0, "resolved at date", True),
        Forecast("certain false", 0.0, "resolved at date", False),
        Forecast("unresolved", 0.4, "future date", None),
    )
    assert brier_score(forecasts) == 0.0


def test_maximally_wrong_forecasts_score_one():
    forecasts = (
        Forecast("wrong true", 0.0, "resolved", True),
        Forecast("wrong false", 1.0, "resolved", False),
    )
    assert brier_score(forecasts) == 1.0


def test_no_resolved_forecasts_return_none_not_fake_calibration():
    assert brier_score((Forecast("pending", 0.5, "future", None),)) is None
