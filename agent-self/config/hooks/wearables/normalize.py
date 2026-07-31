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
# p-scale (negative log10 molar) metric/unit tokens -> the LINEAR endpoint each
# one measures. ``pKi`` and ``Ki`` are the same endpoint on two scales, so once a
# value is reconciled to nM only the linear name identifies the measurement.
_P_METRIC_TO_LINEAR: dict[str, str] = {
    "pic50": "IC50",
    "pki": "Ki",
    "pec50": "EC50",
    "pkd": "Kd",
}
_P_UNITS: frozenset[str] = frozenset(_P_METRIC_TO_LINEAR)


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


def canonical_metric(metric: str) -> str:
    """Return the LINEAR endpoint name a (possibly p-scale) ``metric`` names.

    ``pKi`` -> ``Ki``, ``pIC50`` -> ``IC50``; any other token is returned
    stripped but otherwise unchanged. Callers that must decide whether two rows
    measure the SAME endpoint have to compare this, not the raw string —
    ``pKi`` and ``Ki`` are one endpoint reported on two scales.
    """
    return _P_METRIC_TO_LINEAR.get(_canon_unit(metric), str(metric).strip())


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

    # ``metric`` and ``unit`` are two independent authorities on one measurement.
    # A SOURCE-DECLARED unit governs what the number means and always wins. But
    # ``pipeline._datum_from_fetch`` DEFAULTS a missing unit to "nM" while leaving
    # ``unit_as_reported`` None, and that invented concentration unit must not
    # outrank a p-scale METRIC: otherwise a payload of {"value": 6.0,
    # "metric": "pIC50"} normalizes to 6.0 nM instead of 1000.0 nM (~167x wrong).
    is_p_scale = _is_p_unit(datum.unit) or (
        datum.unit_as_reported is None
        and _canon_unit(datum.metric) in _P_METRIC_TO_LINEAR
    )

    if is_p_scale:
        canonical = nm_from_p(datum.value_as_reported)
    else:
        canonical = to_nm(datum.value_as_reported, datum.unit)

    return dataclasses.replace(
        datum,
        value=canonical,
        unit="nM",
        unit_as_reported=reported_unit,
    )
