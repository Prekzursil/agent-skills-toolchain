"""Hermetic candidate set for TST-0304 cost accounting."""

from __future__ import annotations

from typing import Any

from bench.cost import (
    DEFAULT_RATE_CARD,
    Quota,
    VendorUsage,
    estimate_spend_usd,
    parse_cost_record,
)

REQUIRED = (
    "tokens_in",
    "tokens_out",
    "wall_clock_ms",
    "tool_calls",
    "estimated_spend_usd",
)


def _row(
    candidate_id: str,
    quality: float,
    tokens_in: int,
    tokens_out: int,
    wall_clock_ms: int,
    tool_calls: int,
) -> dict[str, Any]:
    spend = estimate_spend_usd(tokens_in, tokens_out, tool_calls, DEFAULT_RATE_CARD)
    return {
        "run_id": f"run-{candidate_id}",
        "candidate_id": candidate_id,
        "quality": quality,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "wall_clock_ms": wall_clock_ms,
        "tool_calls": tool_calls,
        "estimated_spend_usd": spend,
    }


# A: baseline. B: +2% quality, same tokens (the "free" 2%).
# C: +2% quality, 6x tokens (the expensive 2%). D: worse and more expensive.
# E: same quality as B, 2x spend (cost-dominated).
CANDIDATE_ROWS: list[dict[str, Any]] = [
    _row("A", 1.00, 100_000, 20_000, 1_000, 2),
    _row("B", 1.02, 100_000, 20_000, 1_000, 2),
    _row("C", 1.02, 600_000, 120_000, 6_000, 12),
    _row("D", 0.90, 800_000, 200_000, 8_000, 16),
    _row("E", 1.02, 200_000, 40_000, 2_000, 4),
]


def complete_rows() -> list[dict[str, Any]]:
    return [dict(row) for row in CANDIDATE_ROWS]


def matching_vendor(row: dict[str, Any]) -> VendorUsage:
    return VendorUsage(
        run_id=str(row["run_id"]),
        tokens_in=int(row["tokens_in"]),
        tokens_out=int(row["tokens_out"]),
        source="vendor_usage_fixture",
    )


def mismatch_vendor(row: dict[str, Any]) -> VendorUsage:
    return VendorUsage(
        run_id=str(row["run_id"]),
        tokens_in=int(row["tokens_in"]) + 1_000,
        tokens_out=int(row["tokens_out"]) + 500,
        source="vendor_usage_fixture",
    )


def incomplete_rows() -> list[dict[str, Any]]:
    """One incomplete row per required field, plus null and blank spend."""
    base = dict(CANDIDATE_ROWS[0])
    out: list[dict[str, Any]] = []
    for field in REQUIRED:
        dropped = dict(base)
        dropped.pop(field)
        dropped["label"] = f"drop:{field}"
        out.append(dropped)
        nulled = dict(base)
        nulled[field] = None
        nulled["label"] = f"null:{field}"
        out.append(nulled)
    blank = dict(base)
    blank["estimated_spend_usd"] = ""
    blank["label"] = "blank:estimated_spend_usd"
    out.append(blank)
    return out


def forged_spend_row() -> dict[str, Any]:
    row = dict(CANDIDATE_ROWS[0])
    row["estimated_spend_usd"] = 99.0
    return row


def remaining_quota() -> Quota:
    # Fits A/B (120k tokens) and refuses C (720k).
    return Quota(tokens=200_000, spend_usd=2.0, wall_clock_ms=10_000, tool_calls=20)


def records():
    return [parse_cost_record(row) for row in CANDIDATE_ROWS]
