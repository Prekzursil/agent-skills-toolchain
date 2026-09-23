"""Golden tests for graders.cost (three-plus-two provenance classes; quota is never 0)."""

from __future__ import annotations

import pytest
from graders.cost import (
    LOCAL_ZERO,
    PROVENANCE_CLASSES,
    PROVIDER_REPORTED,
    QUOTA,
    TABLE_ESTIMATE,
    UNKNOWN_PRICE,
    aggregate,
    cost_usd,
    provenance_class,
)


def test_provenance_constants_match_registry_cost_basis_values() -> None:
    assert set(PROVENANCE_CLASSES) == {
        "provider_reported",
        "table_estimate",
        "unknown_price",
        "local_zero",
        "quota",
    }


def test_declared_basis_wins() -> None:
    assert provenance_class({"cost_basis": "quota"}) == QUOTA
    assert provenance_class({"basis": "local_zero"}) == LOCAL_ZERO
    assert provenance_class({"cost": {"basis": "table_estimate"}}) == TABLE_ESTIMATE


def test_declared_basis_must_be_known() -> None:
    with pytest.raises(ValueError):
        provenance_class({"cost_basis": "free-forever"})


def test_inferred_basis_from_row_shape() -> None:
    assert provenance_class({"usage": {"cost": 0.0012}}) == PROVIDER_REPORTED
    assert (
        provenance_class({"price": {"inputPer1M": 1.0, "outputPer1M": 2.0}})
        == TABLE_ESTIMATE
    )
    assert provenance_class({"quota_units": 1}) == QUOTA
    assert provenance_class({"local": True}) == LOCAL_ZERO
    assert provenance_class({}) == UNKNOWN_PRICE


def test_cost_usd_quota_is_none_never_zero() -> None:
    row = {
        "cost_basis": "quota",
        "quota_units": 1,
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    assert cost_usd(row) is None
    assert cost_usd(row) != 0


def test_cost_usd_unknown_price_is_none() -> None:
    assert (
        cost_usd({"cost_basis": "unknown_price", "usage": {"prompt_tokens": 10}})
        is None
    )


def test_cost_usd_local_zero_is_zero() -> None:
    assert cost_usd({"cost_basis": "local_zero"}) == 0.0


def test_cost_usd_provider_reported_reads_usage_cost() -> None:
    assert (
        cost_usd({"cost_basis": "provider_reported", "usage": {"cost": 0.0042}})
        == 0.0042
    )
    assert cost_usd({"cost_basis": "provider_reported", "usage": {}}) is None
    assert cost_usd({"cost_basis": "provider_reported"}) is None


def test_cost_usd_table_estimate_arithmetic() -> None:
    row = {
        "cost_basis": "table_estimate",
        "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 500_000},
        "price": {"inputPer1M": 0.5, "outputPer1M": 2.0},
    }
    assert cost_usd(row) == pytest.approx(0.5 + 1.0)
    nested = {
        "cost_basis": "table_estimate",
        "usage": {"prompt_tokens": 2_000_000, "completion_tokens": 0},
        "cost": {"inputPer1M": 0.25, "outputPer1M": 1.0},
    }
    assert cost_usd(nested) == pytest.approx(0.5)


def test_cost_usd_table_estimate_without_prices_is_none() -> None:
    assert (
        cost_usd({"cost_basis": "table_estimate", "usage": {"prompt_tokens": 1}})
        is None
    )
    partial = {
        "cost_basis": "table_estimate",
        "usage": {"prompt_tokens": 1},
        "price": {"inputPer1M": None},
    }
    assert cost_usd(partial) is None


def test_aggregate_mixes_classes_and_keeps_quota_separate() -> None:
    rows = [
        {"cost_basis": "provider_reported", "usage": {"cost": 0.01}},
        {"cost_basis": "quota", "quota_units": 3},
        {"cost_basis": "quota"},
        {"cost_basis": "local_zero"},
        {"cost_basis": "unknown_price"},
    ]
    summary = aggregate(rows)
    assert summary["usd_total"] == pytest.approx(0.01)
    assert summary["usd_known_rows"] == 2
    assert summary["null_rows"] == 3
    assert summary["quota_units"] == 4
    assert summary["by_class"] == {
        "provider_reported": 1,
        "quota": 2,
        "local_zero": 1,
        "unknown_price": 1,
    }
    assert summary["n"] == 5


def test_aggregate_empty() -> None:
    assert aggregate([]) == {
        "n": 0,
        "usd_total": 0.0,
        "usd_known_rows": 0,
        "null_rows": 0,
        "quota_units": 0,
        "by_class": {},
    }
