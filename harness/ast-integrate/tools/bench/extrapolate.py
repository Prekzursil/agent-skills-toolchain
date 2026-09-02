"""Error-bar extrapolation for overlap vs judged-only (TST-0309)."""
from __future__ import annotations

from typing import Any

from bench.kappa import wilson_interval


def disagreement_rate(a: list[str], b: list[str]) -> dict[str, Any]:
    n = min(len(a), len(b))
    disagreements = sum(1 for i in range(n) if a[i] != b[i])
    rate = disagreements / n if n else 0.0
    return {"n": n, "disagreements": disagreements, "rate": rate, "disagreement_rate": rate}


def extrapolate_error_bar(
    *,
    overlap_errors: int,
    overlap_n: int,
    judged_only_n: int,
    direction: str,
    false_match: int,
    false_mismatch: int,
) -> dict[str, Any]:
    lo, hi = wilson_interval(overlap_errors, overlap_n)
    return {
        "judged_only_n": judged_only_n,
        "overlap_n": overlap_n,
        "overlap_errors": overlap_errors,
        "direction": direction,
        "false_match": false_match,
        "false_mismatch": false_mismatch,
        "wilson95": (lo, hi),
    }
