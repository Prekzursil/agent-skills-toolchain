"""Cross-source verification — real impl replacing the Phase-1 stub (WU-2J).

Given >=2 independent source values for the SAME (compound, target, metric,
assay_context), reconcile units to the canonical scale from module I, then FLAG
disagreement beyond a numeric/relative tolerance.

Disagreement tolerance (PINNED):
  * relative rule = flag when the max/min ratio of normalized affinities across
    >=2 independent sources exceeds **3x** (0.5 log10 unit ~ 3.16x), OR
  * absolute floor for near-zero values (when min normalized value is below
    :data:`NEAR_ZERO_FLOOR_NM`, compare absolute spread against
    :data:`NEAR_ZERO_ABS_TOL_NM` instead of the ratio).

Unit reconciliation: all sources are reconciled to the canonical unit from I
(pKi/Ki <-> nM) BEFORE comparison via :func:`~wearables.normalize.normalize_datum`.

Comparison grouping: only Data sharing the SAME (compound_id, target_id, metric,
target_context) are compared. Mismatched ``assay_context`` is NOT compared
(different rows) — they fall into different groups and are never cross-flagged.

Outputs are DERIVED: a flagged Datum is re-stamped ``source_class="derived"``
so the egress guard denies it to third-party LLMs unless explicitly downgraded.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict

from .datum import Datum
from .normalize import NormalizationError, canonical_metric, normalize_datum

# Relative tolerance: flag when max/min ratio of normalized values exceeds 3x.
RATIO_TOLERANCE: float = 3.0
# Below this normalized (nM) value a measurement is "near-zero" and the ratio
# rule becomes numerically unstable -> use an absolute spread test instead.
NEAR_ZERO_FLOOR_NM: float = 1e-3
# Absolute spread (nM) tolerated among near-zero values before flagging.
NEAR_ZERO_ABS_TOL_NM: float = 1e-3

DISAGREEMENT_PREFIX = "disagreement"


def _group_key(datum: Datum) -> tuple[str, str, str, str]:
    """The identity over which independent sources are cross-compared.

    The metric is CANONICALIZED (``pKi`` -> ``Ki``) before it enters the key.
    Grouping runs BEFORE :func:`verify_group` reconciles units, so keying on the
    raw string would put a GtoPdb ``pKi`` row and a ChEMBL ``Ki`` row in two
    single-source groups — each below the >=2-source bar — and a real
    cross-source disagreement between the same endpoint would never be flagged.
    """
    return (
        datum.compound_id,
        datum.target_id,
        canonical_metric(datum.metric),
        datum.target_context,
    )


def _normalized(datum: Datum) -> Datum:
    """Reconcile a Datum to the canonical nM scale (idempotent if already nM).

    A Datum that cannot be normalized (no reported value) is returned as-is; it
    simply carries a ``None`` canonical value and is excluded from the ratio.
    """
    if datum.unit == "nM" and datum.value is not None:
        return datum
    try:
        return normalize_datum(datum)
    except NormalizationError:
        return datum


def _spread_flag(values: list[float]) -> str | None:
    """Return a quantified disagreement flag, or ``None`` if within tolerance."""
    lo = min(values)
    hi = max(values)
    if lo <= NEAR_ZERO_FLOOR_NM:
        # Near-zero: ratio is unstable -> absolute spread test.
        if (hi - lo) > NEAR_ZERO_ABS_TOL_NM:
            return f"{DISAGREEMENT_PREFIX}: abs spread {hi - lo:.3g}nM"
        return None
    ratio = hi / lo
    if ratio > RATIO_TOLERANCE:
        return f"{DISAGREEMENT_PREFIX}: spread {ratio:.2g}x"
    return None


def verify_group(data: list[Datum]) -> list[Datum]:
    """Verify ONE already-grouped set of >=2 Data sharing a group key.

    Reconciles units, computes the spread, and (when beyond tolerance) returns
    every member re-stamped with the disagreement flag and
    ``source_class="derived"``. Within tolerance / fewer than 2 distinct sources
    -> returned unchanged.
    """
    reconciled = [_normalized(d) for d in data]
    distinct_sources = {d.source for d in reconciled}
    if len(distinct_sources) < 2:
        return reconciled

    values = [d.value for d in reconciled if d.value is not None]
    if len(values) < 2:
        return reconciled

    flag = _spread_flag(values)
    if flag is None:
        return reconciled

    flagged: list[Datum] = []
    for d in reconciled:
        new_flags = d.flags if flag in d.flags else d.flags + (flag,)
        flagged.append(dataclasses.replace(d, flags=new_flags, source_class="derived"))
    return flagged


def verify(data: list[Datum]) -> list[Datum]:
    """Cross-source-verify a heterogeneous list of Data.

    Groups by (compound, target, metric, assay_context); mismatched
    ``assay_context`` lands in a different group and is never cross-flagged.
    Returns a flat list in stable input order with disagreements flagged.
    """
    groups: dict[tuple[str, str, str, str], list[Datum]] = defaultdict(list)
    order: list[tuple[str, str, str, str]] = []
    for d in data:
        key = _group_key(d)
        if key not in groups:
            order.append(key)
        groups[key].append(d)

    out: list[Datum] = []
    for key in order:
        out.extend(verify_group(groups[key]))
    return out
