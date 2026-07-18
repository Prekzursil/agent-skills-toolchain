"""Unit/assay normalization to ONE canonical scale (WU-1I).

Canonical scale = ``nM`` (concentration). Pure functions convert
pIC50/pKi <-> molar concentration <-> nM/uM. The assay-context flag is
preserved, and ``value_as_reported`` / ``unit_as_reported`` are ALWAYS kept
(UX contract — never discarded).
"""

from __future__ import annotations

import dataclasses
import math

from .datum import Datum

# Multiplicative factor to convert a concentration unit to nM.
_TO_NM_FACTOR: dict[str, float] = {
    "m": 1e9,
    "mm": 1e6,
    "um": 1e3,
    "nm": 1.0,
    "pm": 1e-3,
}
# p-scale (negative log10 molar) metric/unit tokens.
_P_UNITS: frozenset[str] = frozenset({"pic50", "pki", "pec50", "pkd"})


class NormalizationError(ValueError):
    """Raised when a value/unit cannot be normalized to the canonical scale."""


def _canon_unit(unit: str) -> str:
    """Normalize a unit token: lowercase, unicode micro-sign -> 'u'."""
    return str(unit).strip().lower().replace("µ", "u").replace("μ", "u")


def to_nm(value: float, unit: str) -> float:
    """Convert a concentration ``value`` in ``unit`` to nanomolar."""
    token = _canon_unit(unit)
    if token not in _TO_NM_FACTOR:
        raise NormalizationError(f"unknown concentration unit {unit!r}")
    return value * _TO_NM_FACTOR[token]


def nm_from_p(p_value: float) -> float:
    """Convert a p-scale value (e.g. pKi 9.0) to a nM concentration."""
    # p = -log10(M); M = 10**-p; nM = M * 1e9.
    return (10.0 ** (-p_value)) * 1e9


def p_from_nm(nm_value: float) -> float:
    """Convert a nM concentration back to a p-scale value."""
    if nm_value <= 0:
        raise NormalizationError("p-scale undefined for non-positive concentration")
    molar = nm_value * 1e-9
    return -math.log10(molar)


def _is_p_unit(unit: str) -> bool:
    return _canon_unit(unit) in _P_UNITS


def normalize_datum(datum: Datum) -> Datum:
    """Return a new Datum with ``value``/``unit`` on the canonical nM scale.

    ``value_as_reported`` and ``unit_as_reported`` are preserved verbatim;
    when ``unit_as_reported`` was never set, it is backfilled from the
    original ``unit`` so the as-reported pair is always complete.
    """
    if datum.value_as_reported is None:
        raise NormalizationError("cannot normalize a Datum with no value_as_reported")

    reported_unit = (
        datum.unit_as_reported if datum.unit_as_reported is not None else datum.unit
    )

    if _is_p_unit(datum.unit):
        canonical = nm_from_p(datum.value_as_reported)
    else:
        canonical = to_nm(datum.value_as_reported, datum.unit)

    return dataclasses.replace(
        datum,
        value=canonical,
        unit="nM",
        unit_as_reported=reported_unit,
    )
