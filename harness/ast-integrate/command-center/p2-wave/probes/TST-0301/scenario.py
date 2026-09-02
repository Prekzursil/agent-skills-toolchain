"""Shared comparison fixtures for TST-0301 probes."""
from __future__ import annotations

from copy import deepcopy

BASELINE = {
    "oracle_pass_rate": 0.80,
    "outcome_check_rate": 0.75,
    "wall_clock_ms": 10000,
    "tokens_in": 4000,
    "tokens_out": 1200,
    "tool_calls": 8,
    "estimated_spend_usd": 0.40,
    "run_to_run_sd": 0.02,
}

# Primary win (+0.05). Every secondary is either improved, equal, or strictly
# inside its margin — except when a probe overrides one field.
CANDIDATE_WIN = {
    "oracle_pass_rate": 0.85,
    "outcome_check_rate": 0.74,  # 0.01 worse; margin 0.02
    "wall_clock_ms": 11000,  # +1000 ms; margin 2000
    "tokens_in": 4200,  # +200; margin 500
    "tokens_out": 1300,  # +100; margin 500
    "tool_calls": 9,  # +1; margin 3
    "estimated_spend_usd": 0.42,  # +0.02; margin 0.05
    "run_to_run_sd": 0.025,  # +0.005; margin 0.01
}

STARTED_AFTER_DECISION = "2026-08-20T00:00:00Z"


def comparison(cid: str, candidate: dict, bound_sha: str, *, started_at=STARTED_AFTER_DECISION) -> dict:
    return {
        "id": cid,
        "started_at": started_at,
        "baseline": deepcopy(BASELINE),
        "candidate": deepcopy(candidate),
        "margin_table_sha256": bound_sha,
    }
