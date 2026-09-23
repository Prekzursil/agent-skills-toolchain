"""Per-call cost estimates and the daily USD cap for inference-hub endpoints.

:func:`estimate_cost` turns a model row plus the upstream ``usage`` block into
``(usd | None, basis)``. :class:`BudgetGate` compares what the ledger says an
endpoint spent today against ``budget.dailyUsdCap``: ``None`` means unlimited,
and the gate trips exactly AT the cap, never a cent early (1.99 of 2.00 passes,
2.00 blocks). Quota-billed and local endpoints never carry USD and so never
block on USD.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hub.errors import BUDGET_EXCEEDED, HubError
from hub.ledger import Ledger

__all__ = ["USD_BASES", "BudgetGate", "estimate_cost"]

USD_BASES: frozenset[str] = frozenset({"provider_reported", "table_estimate"})
_PRECISION = 9


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def estimate_cost(
    model_row: Mapping[str, Any],
    usage: Mapping[str, Any] | None,
    *,
    reported_usd: float | None = None,
) -> tuple[float | None, str]:
    """``(usd, basis)`` for one call.

    ``local_zero`` rows cost 0.0; ``quota`` / ``unknown_price`` rows have no USD
    figure. A figure the provider reported (``reported_usd`` or ``usage.cost``)
    wins with basis ``provider_reported``; otherwise the row's per-million
    prices give a ``table_estimate``; null prices or missing usage give None.
    """
    cost = model_row.get("cost") or {}
    basis = str(cost.get("basis") or "unknown_price")
    if basis == "local_zero":
        return 0.0, basis
    if basis not in USD_BASES:
        return None, basis
    reported = _number(reported_usd)
    if reported is None and usage is not None:
        reported = _number(usage.get("cost"))
    if reported is not None:
        return round(reported, _PRECISION), "provider_reported"
    input_price = _number(cost.get("inputPer1M"))
    output_price = _number(cost.get("outputPer1M"))
    if usage is None or input_price is None or output_price is None:
        return None, basis
    prompt_tokens = _number(usage.get("prompt_tokens")) or 0.0
    completion_tokens = _number(usage.get("completion_tokens")) or 0.0
    usd = (prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000
    return round(usd, _PRECISION), "table_estimate"


class BudgetGate:
    """Daily USD cap check backed by the ledger's ``sum_cost_today``."""

    def __init__(self, ledger: Ledger) -> None:
        self._ledger = ledger

    @staticmethod
    def _cap_and_basis(
        endpoint_row: Mapping[str, Any],
    ) -> tuple[float | None, str | None]:
        budget = endpoint_row.get("budget") or {}
        cap = _number(budget.get("dailyUsdCap"))
        basis = budget.get("costBasis")
        return cap, (str(basis) if basis is not None else None)

    def _spent(self, endpoint_id: str) -> float | None:
        spent = self._ledger.sum_cost_today(endpoint_id)
        return None if spent is None else round(spent, _PRECISION)

    def check(
        self, endpoint_id: str, endpoint_row: Mapping[str, Any]
    ) -> HubError | None:
        """None when the call may proceed, else a ``BUDGET_EXCEEDED`` error."""
        cap, _basis = self._cap_and_basis(endpoint_row)
        if cap is None:
            return None
        spent = self._spent(endpoint_id) or 0.0
        if spent < cap:
            return None
        return HubError(
            BUDGET_EXCEEDED,
            f"daily USD cap {cap:.2f} reached for endpoint {endpoint_id}: "
            f"spent {spent:.4f} today",
            endpoint=endpoint_id,
        )

    def status(
        self, endpoint_id: str, endpoint_row: Mapping[str, Any]
    ) -> dict[str, Any]:
        cap, basis = self._cap_and_basis(endpoint_row)
        spent = self._spent(endpoint_id)
        remaining: float | None = None
        blocked = False
        if cap is not None:
            remaining = round(max(0.0, cap - (spent or 0.0)), _PRECISION)
            blocked = (spent or 0.0) >= cap
        return {
            "endpoint": endpoint_id,
            "daily_usd_cap": cap,
            "spent_today_usd": spent,
            "remaining_usd": remaining,
            "cost_basis": basis,
            "blocked": blocked,
        }
