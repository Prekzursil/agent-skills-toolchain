"""Deterministic first-stage capability router for TST-0084.

Policies:
  full            — search the entire installed repertoire (SUT; :10950)
  usage-pruned    — drop capabilities with usage_count < threshold (forbidden)
  popularity-greedy — ignore the prompt; always pick the highest usage_count

Selection never uses usage_count as a score. No match → fallback.none with
confidence 0 (not a confident wrong pick).
"""
from __future__ import annotations

from typing import Any

FALLBACK_ID = "fallback.none"
CONFIDENT_THRESHOLD = 0.5
PRUNE_USAGE_THRESHOLD = 10

Policy = str


def _caps_for_policy(capabilities: list[dict[str, Any]], policy: Policy) -> list[dict[str, Any]]:
    if policy == "usage-pruned":
        keep = []
        for cap in capabilities:
            if cap.get("is_fallback"):
                keep.append(cap)
                continue
            if int(cap.get("usage_count") or 0) >= PRUNE_USAGE_THRESHOLD:
                keep.append(cap)
        return keep
    return list(capabilities)


def score_capability(prompt: str, cap: dict[str, Any]) -> tuple[int, list[str]]:
    if cap.get("is_fallback"):
        return 0, []
    hay = prompt.lower()
    fired = [t for t in (cap.get("triggers") or []) if str(t).lower() in hay]
    return len(fired), fired


def _popularity_pick(capabilities: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = [
        c
        for c in capabilities
        if not c.get("is_fallback")
    ]
    if not ranked:
        return next(c for c in capabilities if c.get("id") == FALLBACK_ID)
    return max(ranked, key=lambda c: (int(c.get("usage_count") or 0), str(c.get("id") or "")))


def route(
    prompt: str,
    capabilities: list[dict[str, Any]],
    policy: Policy = "full",
) -> dict[str, Any]:
    """Return a computed selection dict. confidence in [0, 1]."""
    pool = _caps_for_policy(capabilities, policy)
    by_id = {str(c["id"]): c for c in capabilities}

    if policy == "popularity-greedy":
        chosen = _popularity_pick(pool)
        return {
            "capability_id": chosen["id"],
            "confidence": 1.0,
            "confident": True,
            "reason": "popularity-greedy-max-usage",
            "fired_triggers": [],
            "policy": policy,
            "token_cost": int(chosen.get("token_cost") or 0),
            "usage_count": int(chosen.get("usage_count") or 0),
        }

    scored: list[tuple[int, int, str, list[str], dict[str, Any]]] = []
    for cap in pool:
        n, fired = score_capability(prompt, cap)
        longest = max((len(t) for t in fired), default=0)
        scored.append((n, longest, str(cap["id"]), fired, cap))

    # Highest trigger count, then longest fired trigger, then lexical id.
    # usage_count is intentionally absent from the key.
    best_n, best_len, best_id, fired, cap = max(
        scored, key=lambda row: (row[0], row[1], row[2])
    )
    if best_n <= 0:
        fb = by_id[FALLBACK_ID]
        return {
            "capability_id": FALLBACK_ID,
            "confidence": 0.0,
            "confident": False,
            "reason": "no-trigger-match",
            "fired_triggers": [],
            "policy": policy,
            "token_cost": int(fb.get("token_cost") or 0),
            "usage_count": int(fb.get("usage_count") or 0),
        }

    confidence = min(1.0, 0.5 + 0.25 * (best_n - 1))
    return {
        "capability_id": best_id,
        "confidence": round(confidence, 4),
        "confident": confidence >= CONFIDENT_THRESHOLD,
        "reason": "trigger-table",
        "fired_triggers": fired,
        "policy": policy,
        "token_cost": int(cap.get("token_cost") or 0),
        "usage_count": int(cap.get("usage_count") or 0),
    }
