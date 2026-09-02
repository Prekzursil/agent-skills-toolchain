#!/usr/bin/env python3
"""Hand recompute of one stratum's two rates from raw counts (not compute_rates)."""
from __future__ import annotations


def stratum_id_of(claim: dict) -> str:
    return "|".join(
        [
            str(claim.get("severity") or ""),
            str(claim.get("subsystem") or ""),
            str(claim.get("author_vendor") or ""),
            str(claim.get("claim_type") or ""),
        ]
    )


def hand_recompute(records: list[dict], frame: dict, stratum_id: str) -> dict:
    """Count CONFIRMED / BLOCKED / all by looping the raw tables."""
    claim_ids = {
        str(c.get("claim_id"))
        for c in (frame.get("claims") or [])
        if stratum_id_of(c) == stratum_id
    }
    recs = [r for r in records if str(r.get("claim_id")) in claim_ids]
    n_confirmed = 0
    n_blocked = 0
    for rec in recs:
        v = rec.get("verdict")
        if v == "CONFIRMED":
            n_confirmed += 1
        elif v == "BLOCKED":
            n_blocked += 1
    n_all = len(recs)
    n_without = n_all - n_blocked
    rate_with = f"{n_confirmed}/{n_all}" if n_all else None
    rate_without = f"{n_confirmed}/{n_without}" if n_without else None
    return {
        "stratum_id": stratum_id,
        "n_confirmed": n_confirmed,
        "n_blocked": n_blocked,
        "n_all": n_all,
        "n_without_blocked": n_without,
        "rate_with_blocked_in_denominator": rate_with,
        "rate_without_blocked": rate_without,
        "method": "hand-count loop over raw records; does not call compute_rates",
    }
