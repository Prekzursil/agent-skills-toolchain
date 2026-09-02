"""Cost axis (lens 08 section 2.5): cost per task with explicit provenance.

Trust order: ``provider_reported`` (OpenRouter ``usage.cost``) > ``table_estimate`` (tokens x a
price table) > ``unknown_price`` (no price known: None) ; ``local_zero`` is a local model
(0.0); ``quota`` is a request-billed bridge (Cursor ``:8317``, HF free tier) whose USD cost is
``None`` -- NEVER 0, because a zero cost could be optimised into "free forever" (lock 3).
The five names are exactly the registry's ``budget.costBasis`` values (BUILD-CONTRACT 1.1).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

PROVIDER_REPORTED = "provider_reported"
TABLE_ESTIMATE = "table_estimate"
UNKNOWN_PRICE = "unknown_price"
LOCAL_ZERO = "local_zero"
QUOTA = "quota"
PROVENANCE_CLASSES = (
    PROVIDER_REPORTED,
    TABLE_ESTIMATE,
    UNKNOWN_PRICE,
    LOCAL_ZERO,
    QUOTA,
)

Row = Mapping[str, Any]


def _declared_basis(row: Row) -> str | None:
    cost = row.get("cost")
    nested = cost.get("basis") if isinstance(cost, Mapping) else None
    declared = row.get("cost_basis") or row.get("basis") or nested
    return str(declared) if declared is not None else None


def _price_table(row: Row) -> Mapping[str, Any] | None:
    for key in ("price", "cost"):
        table = row.get(key)
        if isinstance(table, Mapping) and "inputPer1M" in table:
            return table
    return None


def provenance_class(row: Row) -> str:
    declared = _declared_basis(row)
    if declared is not None:
        if declared not in PROVENANCE_CLASSES:
            raise ValueError(
                f"unknown cost basis {declared!r}; expected one of {PROVENANCE_CLASSES}"
            )
        return declared
    usage = row.get("usage") or {}
    if "cost" in usage:
        return PROVIDER_REPORTED
    if _price_table(row) is not None:
        return TABLE_ESTIMATE
    if "quota_units" in row:
        return QUOTA
    if row.get("local"):
        return LOCAL_ZERO
    return UNKNOWN_PRICE


def cost_usd(row: Row) -> float | None:
    """USD cost of one row; None whenever no honest dollar figure exists (quota, unknown price)."""
    basis = provenance_class(row)
    usage = row.get("usage") or {}
    if basis == LOCAL_ZERO:
        return 0.0
    if basis == PROVIDER_REPORTED:
        reported = usage.get("cost")
        return float(reported) if reported is not None else None
    if basis == TABLE_ESTIMATE:
        table = _price_table(row)
        if (
            table is None
            or table.get("inputPer1M") is None
            or table.get("outputPer1M") is None
        ):
            return None
        prompt = float(usage.get("prompt_tokens", 0))
        completion = float(usage.get("completion_tokens", 0))
        return (
            prompt * table["inputPer1M"] / 1e6 + completion * table["outputPer1M"] / 1e6
        )
    return None


def aggregate(rows: Sequence[Row]) -> dict[str, Any]:
    usd_total = 0.0
    known = 0
    null_rows = 0
    quota_units = 0
    by_class: dict[str, int] = {}
    for row in rows:
        basis = provenance_class(row)
        by_class[basis] = by_class.get(basis, 0) + 1
        usd = cost_usd(row)
        if usd is None:
            null_rows += 1
        else:
            known += 1
            usd_total += usd
        if basis == QUOTA:
            quota_units += int(row.get("quota_units", 1))
    return {
        "n": len(rows),
        "usd_total": usd_total,
        "usd_known_rows": known,
        "null_rows": null_rows,
        "quota_units": quota_units,
        "by_class": by_class,
    }
