"""Written Sherman-Kent band intervals for SYN-0035.

AGENTS.md section 7 is absent on this worktree. These intervals are the
written definition under test, frozen here so they cannot be fitted to
observed hit rates.

  * Five-name lexicon (catalog ADV-0108 / SYN-0014 / SYN-0035):
    almost-certain / likely / roughly-even / unlikely / remote.
  * 'likely' is the catalog-cited 55-80 percent (SYN-0035 question,
    RES-0152, ADV-0108 control 'likely (55-80%)').
  * The other four ranges are the overlapping Sherman-Kent table recorded
    in command-center/analysis/forecast_gate.py BAND_RANGES.

forecast_gate.py records likely as (0.60, 0.87). That is a different
table and is not used as the written definition for this unit.
"""

from __future__ import annotations

BAND_ORDER: tuple[str, ...] = (
    "remote",
    "unlikely",
    "roughly-even",
    "likely",
    "almost-certain",
)

WRITTEN_INTERVALS: dict[str, tuple[float, float]] = {
    "almost-certain": (0.87, 0.99),
    "likely": (0.55, 0.80),
    "roughly-even": (0.40, 0.60),
    "unlikely": (0.13, 0.40),
    "remote": (0.01, 0.13),
}

# Midpoint of the written interval; this is the probability used for Brier.
POINT_P: dict[str, float] = {
    name: (lo + hi) / 2.0 for name, (lo, hi) in WRITTEN_INTERVALS.items()
}

MIN_N_TO_SCORE = 5

WRITTEN_DEFINITION_SOURCE = (
    "catalog-cited likely (55-80%); remaining four from forecast_gate.py "
    "BAND_RANGES; AGENTS.md section 7 absent on this worktree"
)


def normalize_band(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    band = raw.strip().lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "almostcertain": "almost-certain",
        "almost-certainly": "almost-certain",
        "probable": "likely",
        "probably": "likely",
        "chances-about-even": "roughly-even",
        "even": "roughly-even",
        "probably-not": "unlikely",
        "almost-certainly-not": "remote",
    }
    band = aliases.get(band, band)
    return band if band in WRITTEN_INTERVALS else None
