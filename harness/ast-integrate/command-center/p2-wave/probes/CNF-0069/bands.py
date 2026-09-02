"""Sherman-Kent band-to-probability mapping used by CNF-0069.

Estate-written intervals (catalog + P2-BUILD reports):
  almost-certain  90-99%
  likely          55-80%

The catalog vocabulary also names roughly-even / unlikely / remote
(AUD-0142 / ADV-0108 family). Those three intervals are reconstructed
from CIA Sherman-Kent practice and tagged as such; they are not silently
presented as estate-measured.
"""
from __future__ import annotations

BAND_ORDER = (
    "almost-certain",
    "likely",
    "roughly-even",
    "unlikely",
    "remote",
)

# Point probability for Brier is the midpoint of the declared interval.
MAPPING = {
    "almost-certain": {
        "lo": 0.90,
        "hi": 0.99,
        "p": 0.945,
        "interval_source": "estate: P2-BUILD-ROUND1.md C10 and catalog 'almost-certain 90-99%'",
    },
    "likely": {
        "lo": 0.55,
        "hi": 0.80,
        "p": 0.675,
        "interval_source": "estate: P2-BUILD-ROUND1.md C10, SYN-0035 'likely' 55-80%",
    },
    "roughly-even": {
        "lo": 0.45,
        "hi": 0.55,
        "p": 0.50,
        "interval_source": "reconstructed: Sherman-Kent 'chances about even' (estate sources do not pin a numeric interval)",
    },
    "unlikely": {
        "lo": 0.20,
        "hi": 0.45,
        "p": 0.325,
        "interval_source": "reconstructed: Sherman-Kent 'probably not' band (estate sources do not pin a numeric interval)",
    },
    "remote": {
        "lo": 0.01,
        "hi": 0.10,
        "p": 0.055,
        "interval_source": "reconstructed: Sherman-Kent 'almost certainly not' / remote (estate sources do not pin a numeric interval)",
    },
}

SETTLED = frozenset({"CONFIRMED", "REFUTED"})
UNSETTLED = frozenset({"PARTIAL", "NOT-CHECKED", "BLOCKED", "UNSETTLED", None})


def p_of(band: str) -> float:
    spec = MAPPING.get(band)
    if spec is None:
        raise KeyError(f"unknown band: {band}")
    return float(spec["p"])
