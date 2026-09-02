#!/usr/bin/env python3
"""Error flag under the blind adjudication protocol.

BLOCKED rows return None and are dropped from the denominator.
"""
from __future__ import annotations


def is_blocked(row: dict) -> bool:
    return bool(row.get("blocked"))


def is_error(row: dict) -> bool | None:
    if is_blocked(row):
        return None
    return str(row["platform_verdict"]) != str(row["human_gold"])


def error_counts(rows: list[dict]) -> dict:
    usable = [r for r in rows if not is_blocked(r)]
    k = sum(1 for r in usable if is_error(r) is True)
    n = len(usable)
    n_blocked = len(rows) - n
    rate = (k / n) if n else None
    return {
        "defined": n > 0,
        "k": k,
        "n": n,
        "n_blocked": n_blocked,
        "n_all": len(rows),
        "rate": rate,
    }
