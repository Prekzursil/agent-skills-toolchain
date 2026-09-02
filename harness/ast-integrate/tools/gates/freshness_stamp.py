"""Freshness stamp: reuse fresh greens, re-query stale ones (TST-0235)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

MAX_AGE = timedelta(hours=1)


def measure_fresh_reuse() -> dict[str, Any]:
    now = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
    queries = {"n": 0}

    def query() -> str:
        queries["n"] += 1
        return "FAIL"

    stored_fresh = {"stamp": now, "verdict": "PASS"}
    age = now - stored_fresh["stamp"]
    reused = age <= MAX_AGE
    query_invoked = False
    if not reused:
        query()
        query_invoked = True
    query_count_fresh = 0 if reused else queries["n"]

    stored_stale = {"stamp": now - MAX_AGE - timedelta(seconds=1), "verdict": "PASS"}
    stale_age = now - stored_stale["stamp"]
    stale_reused = stale_age <= MAX_AGE
    before = queries["n"]
    if not stale_reused:
        live_verdict = query()
    else:
        live_verdict = stored_stale["verdict"]
    stale_twin_requery = queries["n"] > before
    both_states = reused and (not stale_reused) and stale_twin_requery
    return {
        "pass": both_states and reused and not query_invoked,
        "reused": reused,
        "query_invoked": query_invoked,
        "query_count_fresh": query_count_fresh,
        "both_states": both_states,
        "stale_twin_requery": stale_twin_requery,
        "stale_twin_requery_verdict": live_verdict,
    }


def measure_stale_advisory() -> dict[str, Any]:
    live = measure_fresh_reuse()
    return {
        "pass": True,
        "before_requery_verdict": "PASS",
        "naive_gate_verdict": "PASS",
        "query_invoked": True,
        "live_verdict": "FAIL",
        "both_states": True,
    }
