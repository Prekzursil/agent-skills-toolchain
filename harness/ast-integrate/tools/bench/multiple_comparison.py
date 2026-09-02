"""Family-wise and false-discovery-rate corrections for a tournament (TST-0299).

Run forty candidates against one baseline at ``alpha = 0.05`` and about two of them look
like winners by chance.  ``correct_family`` therefore takes the *whole* family of p-values
and applies both corrections at once:

* Benjamini-Hochberg (:func:`benjamini_hochberg`) controls the false-discovery rate and
  names the discoveries worth a follow-up run.
* Holm (:func:`holm`) controls the family-wise error rate; it is the step-down Bonferroni
  a certification gate consumes.

Apply BH (discovery) and Holm (family-wise) to the full family.  Correcting a post-hoc
subset - only the candidates that already looked good - is the mistake the reported
``family_size`` exists to expose, so every result carries it next to both the corrected and
the uncorrected verdict counts.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

METHOD_BH = "benjamini-hochberg"
METHOD_HOLM = "holm"
CORRECTION_METHODS: tuple[str, ...] = (METHOD_BH, METHOD_HOLM)
DEFAULT_ALPHA = 0.05


class FamilyError(ValueError):
    """Raised for an empty family, an invalid p-value or alpha, or mismatched ids."""


def _validate(ps: Sequence[float], alpha: float) -> list[float]:
    if (
        isinstance(alpha, bool)
        or not isinstance(alpha, (int, float))
        or not (0.0 < float(alpha) < 1.0)
    ):
        raise FamilyError(f"alpha must be in (0, 1), got {alpha!r}")
    if len(ps) == 0:
        raise FamilyError("a comparison family needs at least one p-value")
    out: list[float] = []
    for idx, p in enumerate(ps):
        if isinstance(p, bool):
            raise FamilyError(f"p-value {idx} is a boolean")
        try:
            fp = float(p)
        except (TypeError, ValueError) as exc:
            raise FamilyError(f"p-value {idx} is not numeric: {p!r}") from exc
        if not math.isfinite(fp) or fp < 0.0 or fp > 1.0:
            raise FamilyError(f"p-value {idx} is outside [0, 1]: {p!r}")
        out.append(fp)
    return out


def _order(ps: Sequence[float]) -> list[int]:
    """Indices sorted by p ascending; ties broken by position so the result is deterministic."""
    return sorted(range(len(ps)), key=lambda i: (ps[i], i))


def benjamini_hochberg(
    ps: Sequence[float], alpha: float = DEFAULT_ALPHA
) -> dict[str, Any]:
    """Benjamini-Hochberg step-up procedure over the whole family.

    Rejects the ``k`` smallest p-values where ``k`` is the largest rank with
    ``p_(k) <= k / m * alpha``.  ``adjusted`` holds the BH q-values (monotone from the top).
    """
    p = _validate(ps, alpha)
    m = len(p)
    order = _order(p)
    k_star = 0
    for rank, idx in enumerate(order, 1):
        if p[idx] <= rank / m * alpha:
            k_star = rank
    rejected = [False] * m
    for rank, idx in enumerate(order, 1):
        if rank <= k_star:
            rejected[idx] = True
    adjusted = [1.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        running = min(running, min(1.0, m / rank * p[idx]))
        adjusted[idx] = running
    return {
        "method": METHOD_BH,
        "alpha": float(alpha),
        "family_size": m,
        "rejected": rejected,
        "adjusted": adjusted,
        "rejected_count": k_star,
        "critical_p": p[order[k_star - 1]] if k_star else None,
    }


def holm(ps: Sequence[float], alpha: float = DEFAULT_ALPHA) -> dict[str, Any]:
    """Holm step-down procedure over the whole family.

    Walking p-values upward, ``p_(i)`` is rejected while ``p_(i) <= alpha / (m - i + 1)``;
    the first failure stops every later rejection.  ``adjusted`` holds the Holm-adjusted
    p-values (monotone from the bottom, capped at 1).
    """
    p = _validate(ps, alpha)
    m = len(p)
    order = _order(p)
    rejected = [False] * m
    adjusted = [1.0] * m
    running = 0.0
    stopped = False
    for rank, idx in enumerate(order, 1):
        running = max(running, min(1.0, (m - rank + 1) * p[idx]))
        adjusted[idx] = running
        if not stopped and p[idx] <= alpha / (m - rank + 1):
            rejected[idx] = True
        else:
            stopped = True
    return {
        "method": METHOD_HOLM,
        "alpha": float(alpha),
        "family_size": m,
        "rejected": rejected,
        "adjusted": adjusted,
        "rejected_count": sum(rejected),
    }


def correct_family(
    ps: Sequence[float],
    ids: Sequence[str] | None = None,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, Any]:
    """Apply BH (discovery) and Holm (family-wise) to the full family.

    Returns one row per comparison with the uncorrected verdict and both corrected
    verdicts side by side, plus the family size and all three verdict counts.
    """
    p = _validate(ps, alpha)
    m = len(p)
    if ids is None:
        ids = [f"cmp-{i:02d}" for i in range(m)]
    ids = [str(i) for i in ids]
    if len(ids) != m:
        raise FamilyError(f"{len(ids)} ids for {m} p-values")
    if len(set(ids)) != m:
        raise FamilyError("comparison ids must be unique within a family")
    bh = benjamini_hochberg(p, alpha)
    ho = holm(p, alpha)
    p_rank = {idx: rank for rank, idx in enumerate(_order(p), 1)}
    rows: list[dict[str, Any]] = []
    for i in range(m):
        rows.append(
            {
                "id": ids[i],
                "rank": i,
                "p_rank": p_rank[i],
                "p_uncorrected": p[i],
                "uncorrected_significant": p[i] <= alpha,
                "bh_rejected": bh["rejected"][i],
                "holm_rejected": ho["rejected"][i],
                "p_bh_adjusted": bh["adjusted"][i],
                "p_holm_adjusted": ho["adjusted"][i],
            }
        )
    return {
        "family_size": m,
        "alpha": float(alpha),
        "correction_methods": list(CORRECTION_METHODS),
        "comparisons": rows,
        "uncorrected_discovery_count": sum(
            1 for r in rows if r["uncorrected_significant"]
        ),
        "bh_discovery_count": sum(1 for r in rows if r["bh_rejected"]),
        "holm_certified_count": sum(1 for r in rows if r["holm_rejected"]),
        "uncorrected_ids": [r["id"] for r in rows if r["uncorrected_significant"]],
        "bh_ids": [r["id"] for r in rows if r["bh_rejected"]],
        "holm_ids": [r["id"] for r in rows if r["holm_rejected"]],
    }


__all__ = [
    "CORRECTION_METHODS",
    "DEFAULT_ALPHA",
    "FamilyError",
    "METHOD_BH",
    "METHOD_HOLM",
    "benjamini_hochberg",
    "correct_family",
    "holm",
]
