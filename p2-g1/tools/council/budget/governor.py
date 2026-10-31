"""Council budget governor: exhaust each dimension in isolation (IMP-0298)."""
from __future__ import annotations

from typing import Any

BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
KNOWN = frozenset(
    {
        "effort",
        "tokens",
        "tool_calls",
        "turns",
        "time",
        "experiments",
        "sources",
        "speaking_quotas",
        "minimum_engagement",
        "maximum_inactivity",
        "rebuttal_depth",
        "escalation",
    }
)


class UnknownBudgetDimensionError(ValueError):
    pass


class BudgetGovernor:
    def __init__(self, spec: dict[str, Any]) -> None:
        budgets = (spec or {}).get("budgets") or {}
        unknown = set(budgets) - KNOWN
        if unknown:
            raise UnknownBudgetDimensionError(f"unknown budget keys: {sorted(unknown)}")
        self.spec = spec
        self.budgets = budgets


def _tokens(text: str) -> int:
    return len(str(text or "").split())


def governor_token_count(text: str) -> int:
    return _tokens(text)


def marker_is_load_bearing(complete: dict[str, Any], partial: dict[str, Any]) -> dict[str, Any]:
    stripped = dict(partial)
    markers = [m for m in (stripped.get("markers") or []) if m != BUDGET_EXHAUSTED]
    stripped["markers"] = markers
    naive_complete = not markers
    return {
        "pass": bool(partial.get("markers")) and naive_complete and bool(complete.get("complete")),
        "stripped_reads_complete": naive_complete,
        "honest_partial_incomplete": not bool(partial.get("complete")),
    }


def run_fixture(*, spec: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    gov = BudgetGovernor(spec)
    exhausted: list[str] = []
    accepted: list[dict[str, Any]] = []
    text_out = []
    for ev in events:
        if exhausted:
            break
        dim = next(iter(gov.budgets))
        cfg = gov.budgets[dim]
        limit = cfg.get("limit")
        floor = cfg.get("floor")
        trip = False
        if dim == "effort":
            used = sum(int(x.get("effort") or 0) for x in accepted) + int(ev.get("effort") or 0)
            trip = used > int(limit)
        elif dim == "tokens":
            words = str(ev.get("text") or "").split()
            if len(words) > int(limit):
                trip = True
                text_out.append(" ".join(words[: int(limit)]))
            else:
                text_out.append(str(ev.get("text") or ""))
        elif dim == "tool_calls":
            used = sum(len(x.get("tool_calls") or []) for x in accepted)
            nxt = len(ev.get("tool_calls") or [])
            trip = used + nxt > int(limit)
        elif dim == "turns":
            trip = len(accepted) >= int(limit)
        elif dim == "time":
            trip = int(ev.get("duration_ms") or 0) > int(limit)
        elif dim == "experiments":
            used = sum(1 for x in accepted if x.get("experiment"))
            trip = used + (1 if ev.get("experiment") else 0) > int(limit)
        elif dim == "sources":
            used = {x.get("source") for x in accepted if x.get("source")}
            nxt = ev.get("source")
            trip = nxt is not None and nxt not in used and len(used) + 1 > int(limit)
        elif dim == "speaking_quotas":
            who = ev.get("participant")
            used = sum(1 for x in accepted if x.get("participant") == who)
            trip = used + 1 > int(limit)
        elif dim == "minimum_engagement":
            units = int(ev.get("engagement_units") or 0)
            trip = units < int(floor or 0)
        elif dim == "maximum_inactivity":
            if ev.get("kind") == "idle":
                idle = sum(1 for x in accepted if x.get("kind") == "idle") + 1
                trip = idle > int(limit)
        elif dim == "rebuttal_depth":
            trip = int(ev.get("rebuttal_depth") or 0) > int(limit)
        elif dim == "escalation":
            used = sum(int(x.get("escalation") or 0) for x in accepted)
            trip = used + int(ev.get("escalation") or 0) > int(limit)
        if trip:
            exhausted.append(dim)
            if dim == "tokens" and not text_out:
                text_out.append(" ".join(str(ev.get("text") or "").split()[: int(limit)]))
            break
        accepted.append(ev)
        if dim != "tokens":
            text_out.append(str(ev.get("text") or ""))
    return {
        "complete": not exhausted,
        "exhausted_dimensions": exhausted,
        "markers": [BUDGET_EXHAUSTED] if exhausted else [],
        "text": " ".join(t for t in text_out if t),
        "accepted": len(accepted),
    }
