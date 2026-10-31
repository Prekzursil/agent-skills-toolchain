"""ETA model library — p50/p90 RANGE + provenance (grill S8).

Every model returns an :class:`~core.models.EtaEstimate` of *seconds remaining*:

* linear-frac          — from the completed fraction and elapsed time.
* ewma-throughput      — from remaining units and a smoothed units/sec rate.
* per-phase-weighted   — from weighted expected work across ordered phases.
* steady-state-window  — from a recent window of throughput samples.

Two hard rules from the grill:

* **No hidden clamps (S6a).** An out-of-range input (overshoot / negative
  remaining) is never silently capped; it WIDENS the p90 band so the caller can
  see the model is uncertain, and the point estimate collapses to 0 (the job
  should already be done) rather than a fabricated positive countdown.
* **Honest unknown total (S8).** When the denominator is unknown/non-positive,
  the estimate is not estimable (``p50 == p90 == None``, provenance NONE) and the
  caller must show elapsed+rate instead of a fake percentage.
"""

from __future__ import annotations

from statistics import median

from .models import EtaEstimate, Provenance

# Default multiplicative spread applied to p50 to obtain the p90 upper bound.
_DEFAULT_WIDEN = 0.5

_NONE = EtaEstimate(p50=None, p90=None, provenance=Provenance.NONE)


def _overshoot(overrun_seconds: float, provenance: Provenance) -> EtaEstimate:
    """Out-of-range result: p50 collapses to 0, p90 carries the overrun band."""
    return EtaEstimate(p50=0.0, p90=abs(overrun_seconds), provenance=provenance)


def linear_frac_eta(
    fraction: float | None,
    elapsed_s: float,
    *,
    widen: float = _DEFAULT_WIDEN,
) -> EtaEstimate:
    """ETA from completed ``fraction`` (done/total, NOT clamped) and elapsed time."""
    if fraction is None:
        return _NONE
    if elapsed_s <= 0 or fraction <= 0:
        # No measurable rate yet — honest unknown, not a guess.
        return _NONE
    if fraction >= 1.0:
        # Complete (or overshoot): 0 remaining; overshoot widens via the band.
        return _overshoot((fraction - 1.0) * elapsed_s, Provenance.MEASURED)
    remaining_frac = 1.0 - fraction
    p50 = elapsed_s * remaining_frac / fraction
    return EtaEstimate(p50=p50, p90=p50 * (1.0 + widen), provenance=Provenance.MEASURED)


def ewma_throughput_eta(
    done: float,
    total: float | None,
    throughput: float | None,
    *,
    widen: float = _DEFAULT_WIDEN,
) -> EtaEstimate:
    """ETA from remaining units and a smoothed ``throughput`` (units/sec)."""
    if total is None or throughput is None or throughput <= 0:
        return _NONE
    remaining = total - done
    if remaining < 0:
        return _overshoot(remaining / throughput, Provenance.MEASURED)
    p50 = remaining / throughput
    return EtaEstimate(p50=p50, p90=p50 * (1.0 + widen), provenance=Provenance.MEASURED)


def per_phase_weighted_eta(
    phase: str,
    done_in_phase: float,
    phases: list[tuple[str, float]],
    throughput: float | None,
    *,
    widen: float = _DEFAULT_WIDEN,
) -> EtaEstimate:
    """ETA across ordered ``phases`` of ``(name, expected_units)``.

    Sums the remaining units of the current phase plus every later phase. An
    unknown current phase is an honest unknown; an in-phase overshoot widens the
    band instead of being clamped.
    """
    if throughput is None or throughput <= 0:
        return _NONE
    names = [name for name, _ in phases]
    if phase not in names:
        return _NONE
    idx = names.index(phase)
    _, current_units = phases[idx]
    remaining_units = current_units - done_in_phase
    for _, later_units in phases[idx + 1 :]:
        remaining_units += later_units
    if remaining_units < 0:
        return _overshoot(remaining_units / throughput, Provenance.MEASURED)
    p50 = remaining_units / throughput
    return EtaEstimate(p50=p50, p90=p50 * (1.0 + widen), provenance=Provenance.MEASURED)


def steady_state_window_eta(
    recent_rates: list[float],
    remaining_units: float | None,
    *,
    widen: float = _DEFAULT_WIDEN,
) -> EtaEstimate:
    """ETA from a window of recent throughput samples.

    The window's spread (max/median) inflates the p90 band, so a jittery recent
    rate yields a wider, more honest range than a steady one.
    """
    if remaining_units is None or not recent_rates:
        return _NONE
    rate = median(recent_rates)
    if rate <= 0:
        return _NONE
    if remaining_units < 0:
        return _overshoot(remaining_units / rate, Provenance.MEASURED)
    p50 = remaining_units / rate
    spread = max(recent_rates) / rate  # >= 1.0 by construction
    p90 = p50 * (1.0 + widen) * spread
    return EtaEstimate(p50=p50, p90=p90, provenance=Provenance.MEASURED)


def prior_eta(
    prior_duration_s: float | None,
    elapsed_s: float,
    *,
    widen: float = _DEFAULT_WIDEN,
) -> EtaEstimate:
    """ETA from a historical prior duration (provenance PRIOR, grill S8).

    Never slides the finish clock forward on a stall: once elapsed exceeds the
    prior the job is *overdue*, so p50 collapses to 0 and the overrun widens p90
    rather than pretending there is still ``prior - elapsed`` time left.
    """
    if prior_duration_s is None or prior_duration_s <= 0:
        return _NONE
    remaining = prior_duration_s - elapsed_s
    if remaining <= 0:
        return _overshoot(remaining, Provenance.PRIOR)
    return EtaEstimate(
        p50=remaining, p90=remaining * (1.0 + widen), provenance=Provenance.PRIOR
    )
