"""Tests for hub.budget: cost estimation and the daily USD cap gate."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hub import errors  # noqa: E402
from hub.budget import BudgetGate, estimate_cost  # noqa: E402
from hub.ledger import Ledger  # noqa: E402
from tests import conftest_hub as helpers  # noqa: E402

ledger = helpers.ledger

USAGE = {"prompt_tokens": 1_000_000, "completion_tokens": 500_000}


def model_row(basis: str, input_per_1m: Any = 1.0, output_per_1m: Any = 2.0) -> dict:
    return {
        "endpoint": "hf-router",
        "cost": {
            "inputPer1M": input_per_1m,
            "outputPer1M": output_per_1m,
            "basis": basis,
        },
    }


def endpoint_row(cap: float | None, basis: str = "table_estimate") -> dict[str, Any]:
    return {"budget": {"dailyUsdCap": cap, "costBasis": basis}}


def spend(book: Ledger, endpoint: str, *amounts: float | None) -> None:
    for amount in amounts:
        book.record(
            {
                "endpoint": endpoint,
                "model": "m",
                "status": "ok",
                "cost_usd": amount,
                "cost_basis": "table_estimate",
            }
        )


def test_estimate_cost_local_zero_quota_unknown() -> None:
    assert estimate_cost(model_row("local_zero", 0, 0), USAGE) == (0.0, "local_zero")
    assert estimate_cost(model_row("quota", None, None), USAGE) == (None, "quota")
    assert estimate_cost(model_row("unknown_price"), USAGE) == (None, "unknown_price")
    assert estimate_cost({"endpoint": "x"}, USAGE) == (None, "unknown_price")
    assert estimate_cost({"cost": {}}, USAGE) == (None, "unknown_price")


def test_estimate_cost_table_estimate_from_prices() -> None:
    usd, basis = estimate_cost(model_row("table_estimate", 1.0, 2.0), USAGE)
    assert (usd, basis) == (2.0, "table_estimate")
    zero, basis = estimate_cost(
        model_row("provider_reported", 0, 0),
        {"prompt_tokens": 5, "completion_tokens": 7},
    )
    assert (zero, basis) == (0.0, "table_estimate")
    partial, basis = estimate_cost(model_row("table_estimate", 3.0, 6.0), {})
    assert (partial, basis) == (0.0, "table_estimate")


def test_estimate_cost_null_prices_or_missing_usage_give_none() -> None:
    assert estimate_cost(model_row("table_estimate", None, 2.0), USAGE) == (
        None,
        "table_estimate",
    )
    assert estimate_cost(model_row("provider_reported", 1.0, None), USAGE) == (
        None,
        "provider_reported",
    )
    assert estimate_cost(model_row("table_estimate"), None) == (None, "table_estimate")


def test_estimate_cost_prefers_provider_reported_figures() -> None:
    row = model_row("provider_reported", 1.0, 2.0)
    assert estimate_cost(row, USAGE, reported_usd=0.123) == (0.123, "provider_reported")
    assert estimate_cost(row, {"prompt_tokens": 1, "cost": 0.05}) == (
        0.05,
        "provider_reported",
    )
    assert estimate_cost(row, {"prompt_tokens": 1, "cost": "0.05"}) == (
        0.000001,
        "table_estimate",
    )
    assert estimate_cost(model_row("local_zero"), USAGE, reported_usd=9.0) == (
        0.0,
        "local_zero",
    )


def test_budget_gate_unlimited_when_cap_is_null(ledger: Ledger) -> None:
    gate = BudgetGate(ledger)
    spend(ledger, "cursor-auth2api", None, None)
    assert gate.check("cursor-auth2api", endpoint_row(None, "quota")) is None
    status = gate.status("cursor-auth2api", endpoint_row(None, "quota"))
    assert status == {
        "endpoint": "cursor-auth2api",
        "daily_usd_cap": None,
        "spent_today_usd": None,
        "remaining_usd": None,
        "cost_basis": "quota",
        "blocked": False,
    }


def test_budget_gate_never_blocks_a_cent_early(ledger: Ledger) -> None:
    gate = BudgetGate(ledger)
    row = endpoint_row(2.0)
    assert gate.check("hf-router", row) is None
    spend(ledger, "hf-router", 1.0, 0.99)
    assert gate.check("hf-router", row) is None
    status = gate.status("hf-router", row)
    assert status["spent_today_usd"] == 1.99
    assert status["remaining_usd"] == pytest.approx(0.01)
    assert status["blocked"] is False
    spend(ledger, "hf-router", 0.01)
    err = gate.check("hf-router", row)
    assert isinstance(err, errors.HubError)
    assert err.klass == errors.BUDGET_EXCEEDED
    assert err.retryable is False
    assert err.endpoint == "hf-router"
    assert "2.00" in err.message
    status = gate.status("hf-router", row)
    assert status["blocked"] is True
    assert status["remaining_usd"] == 0.0
    assert status["spent_today_usd"] == 2.0


def test_budget_gate_exactly_at_cap_blocks(ledger: Ledger) -> None:
    gate = BudgetGate(ledger)
    spend(ledger, "openrouter", 0.5, 0.5)
    assert gate.check("openrouter", endpoint_row(1.0, "provider_reported")) is not None
    assert gate.check("openrouter", endpoint_row(1.0000001)) is None
    spend(ledger, "openrouter", 0.5)
    over = gate.status("openrouter", endpoint_row(1.0))
    assert over["remaining_usd"] == 0.0
    assert over["spent_today_usd"] == 1.5


def test_budget_gate_ignores_other_endpoints_and_null_rows(ledger: Ledger) -> None:
    gate = BudgetGate(ledger)
    spend(ledger, "openrouter", 5.0)
    spend(ledger, "hf-router", None)
    row = endpoint_row(2.0)
    assert gate.check("hf-router", row) is None
    status = gate.status("hf-router", row)
    assert status["spent_today_usd"] is None
    assert status["remaining_usd"] == 2.0
    assert status["blocked"] is False
    assert gate.status("hf-router", {})["cost_basis"] is None
