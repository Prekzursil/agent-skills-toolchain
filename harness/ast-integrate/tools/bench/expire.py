"""Expire live-source results past TTL; never-expire hermetic."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from bench.ttl import ttl_for


@dataclass
class Cite:
    status: str


def gate_accepts(result: Any, now: datetime) -> dict[str, Any]:
    ttl = ttl_for(getattr(result, "observed_class", ""))
    captured = result.captured_at
    age = (now - captured).total_seconds()
    if ttl is None:
        return {"accepted": True, "as": result.verdict, "reason": "never-expire", "age_seconds": age}
    if age > ttl:
        return {"accepted": False, "as": "NOT-CHECKED", "reason": "expired", "age_seconds": age}
    return {"accepted": True, "as": result.verdict, "reason": "fresh", "age_seconds": age}


def cite_as_current(result: Any, now: datetime) -> Cite:
    g = gate_accepts(result, now)
    if not g["accepted"]:
        return Cite(status="EXPIRED-NOT-CHECKED")
    return Cite(status="CURRENT")


def dashboard(results: Iterable[Any], now: datetime) -> dict[str, Any]:
    greens = []
    expired = 0
    for r in results:
        g = gate_accepts(r, now)
        if g["accepted"]:
            greens.append({"id": getattr(r, "result_id", ""), "age_seconds": g["age_seconds"]})
        else:
            expired += 1
    return {"greens": greens, "expired_count": expired}
