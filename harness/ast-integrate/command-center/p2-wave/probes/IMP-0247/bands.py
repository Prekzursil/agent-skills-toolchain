"""Sherman-Kent confidence lexicon for IMP-0247 product blueprints.

Single source of truth. Blueprints attach ranges only via attach(); probe 2
checks live claims against this table. Ranges follow the estate lexicon
cited by IMP-0247 / BLD-0031 / AGENTS.md 7:

  almost-certain  90-99
  likely          55-80
  roughly-even    40-55
  unlikely        20-40
  remote           1-20

Gaps (e.g. 81-89) are deliberate: not every integer has a name.
"""
from __future__ import annotations

from typing import Mapping

# Inclusive integer percent bounds.
BANDS: dict[str, tuple[int, int]] = {
    "remote": (1, 20),
    "unlikely": (20, 40),
    "roughly-even": (40, 55),
    "likely": (55, 80),
    "almost-certain": (90, 99),
}

BAND_NAMES: tuple[str, ...] = tuple(BANDS)

# Hedges that are NOT a calibrated band. "likely" in "likely fine" is a hedge.
UNBANDED_HEDGES: tuple[str, ...] = (
    "likely fine",
    "should work",
    "looks fine",
    "likely fine",
    "probably fine",
    "should be fine",
    "looks good",
    "will be fine",
)


def attach(band: str) -> dict[str, object]:
    if band not in BANDS:
        raise KeyError(f"undeclared confidence band: {band!r}")
    lo, hi = BANDS[band]
    return {"confidence_band": band, "p_low": lo, "p_high": hi}


def range_of(band: str) -> tuple[int, int]:
    if band not in BANDS:
        raise KeyError(f"undeclared confidence band: {band!r}")
    return BANDS[band]


def claim_matches_declared(claim: Mapping[str, object]) -> bool:
    band = claim.get("confidence_band")
    if not isinstance(band, str) or band not in BANDS:
        return False
    lo, hi = BANDS[band]
    return claim.get("p_low") == lo and claim.get("p_high") == hi


def quantize_probability(p: float) -> str:
    """Map p in (0, 1] onto a declared band. Gap values snap to nearest
    midpoint; ties take the more conservative (lower) band.
    """
    if p <= 0 or p > 1:
        raise ValueError(f"probability out of (0, 1]: {p}")
    pct = min(99, max(1, int(round(100 * p))))
    for name, (lo, hi) in BANDS.items():
        if lo <= pct <= hi:
            return name
    best = "remote"
    best_dist = 10**9.0
    for name, (lo, hi) in BANDS.items():
        mid = (lo + hi) / 2.0
        dist = abs(pct - mid)
        if dist < best_dist - 1e-9:
            best, best_dist = name, dist
        elif abs(dist - best_dist) <= 1e-9:
            if mid < (BANDS[best][0] + BANDS[best][1]) / 2.0:
                best, best_dist = name, dist
    return best


def band_from_strength(strength: float) -> str:
    """Evidence-strength in [0, 1] uses the same cut-points as BANDS."""
    if strength < 0 or strength > 1:
        raise ValueError(f"strength out of [0, 1]: {strength}")
    return quantize_probability(max(0.01, min(0.99, strength)))
