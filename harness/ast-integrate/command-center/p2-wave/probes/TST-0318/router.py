"""Budgeted top-k capability router for TST-0318.

Policies:
  budgeted — trigger-score top-k; inject descriptions until TOKEN_BUDGET.
  flood    — inject the entire installed catalogue (perfect offer-recall, over budget).
  starve   — inject nothing (zero cost, zero offer-recall).

Cost is the whitespace token count of the concatenated injected descriptions,
counted AFTER injection. repertoire.json ``token_cost`` is a decoy estimate
and must not be used as the reported cost (catalog: measured per task, not
estimated).
"""
from __future__ import annotations

from typing import Any

FALLBACK_ID = "fallback.none"
TOKEN_BUDGET = 80
TOP_K = 2
Policy = str
POLICIES = ("budgeted", "flood", "starve")


def count_tokens(text: str) -> int:
    """Measured injected-token cost: whitespace tokens of the live payload."""
    if not text or not text.strip():
        return 0
    return len(text.split())


def estimated_token_cost(caps: list[dict[str, Any]]) -> int:
    """Sum of decoy ``token_cost`` fields. Must not equal measured cost on flood."""
    return sum(int(c.get("token_cost") or 0) for c in caps)


def payload_for(caps: list[dict[str, Any]]) -> str:
    return "\n".join(str(c.get("description") or "") for c in caps)


def score_capability(prompt: str, cap: dict[str, Any]) -> tuple[int, list[str]]:
    if cap.get("is_fallback"):
        return 0, []
    hay = prompt.lower()
    fired = [t for t in (cap.get("triggers") or []) if str(t).lower() in hay]
    return len(fired), fired


def _fallback(capabilities: list[dict[str, Any]]) -> dict[str, Any]:
    for c in capabilities:
        if c.get("id") == FALLBACK_ID or c.get("is_fallback"):
            return c
    raise KeyError(FALLBACK_ID)


def _ranked_matches(
    prompt: str, capabilities: list[dict[str, Any]]
) -> list[tuple[int, int, str, list[str], dict[str, Any]]]:
    scored: list[tuple[int, int, str, list[str], dict[str, Any]]] = []
    for cap in capabilities:
        if cap.get("is_fallback"):
            continue
        n, fired = score_capability(prompt, cap)
        longest = max((len(t) for t in fired), default=0)
        scored.append((n, longest, str(cap["id"]), fired, cap))
    scored.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
    return scored


def _clip_to_budget(ordered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    injected: list[dict[str, Any]] = []
    for cap in ordered:
        trial = payload_for(injected + [cap])
        if injected and count_tokens(trial) > TOKEN_BUDGET:
            break
        injected.append(cap)
    return injected


def inject(
    prompt: str,
    capabilities: list[dict[str, Any]],
    policy: Policy = "budgeted",
) -> dict[str, Any]:
    """Return offered set, measured cost, and top-1 selection."""
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}")

    if policy == "starve":
        return {
            "policy": policy,
            "offered_ids": [],
            "top1_id": FALLBACK_ID,
            "fired_triggers": [],
            "confident": False,
            "reason": "starve-inject-nothing",
            "payload": "",
            "injected_token_cost": 0,
            "estimated_token_cost": 0,
            "budget_limit": TOKEN_BUDGET,
            "budget_ok": True,
        }

    if policy == "flood":
        offered = list(capabilities)
        payload = payload_for(offered)
        measured = count_tokens(payload)
        return {
            "policy": policy,
            "offered_ids": [str(c["id"]) for c in offered],
            "top1_id": str(offered[0]["id"]) if offered else FALLBACK_ID,
            "fired_triggers": [],
            "confident": True,
            "reason": "flood-whole-catalogue",
            "payload": payload,
            "injected_token_cost": measured,
            "estimated_token_cost": estimated_token_cost(offered),
            "budget_limit": TOKEN_BUDGET,
            "budget_ok": measured <= TOKEN_BUDGET,
        }

    ranked = _ranked_matches(prompt, capabilities)
    matches = [row[4] for row in ranked if row[0] > 0][:TOP_K]
    fired = ranked[0][3] if ranked and ranked[0][0] > 0 else []
    if not matches:
        matches = [_fallback(capabilities)]
        reason = "no-trigger-match"
        confident = False
        top1 = FALLBACK_ID
    else:
        reason = "trigger-table-topk"
        confident = True
        top1 = str(matches[0]["id"])

    injected = _clip_to_budget(matches)
    payload = payload_for(injected)
    measured = count_tokens(payload)
    return {
        "policy": policy,
        "offered_ids": [str(c["id"]) for c in injected],
        "top1_id": top1,
        "fired_triggers": fired,
        "confident": confident,
        "reason": reason,
        "payload": payload,
        "injected_token_cost": measured,
        "estimated_token_cost": estimated_token_cost(injected),
        "budget_limit": TOKEN_BUDGET,
        "budget_ok": measured <= TOKEN_BUDGET,
    }


def route(
    prompt: str,
    capabilities: list[dict[str, Any]],
    policy: Policy = "budgeted",
) -> dict[str, Any]:
    """Alias used by probes; same record as inject()."""
    return inject(prompt, capabilities, policy=policy)
