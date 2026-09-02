"""Shadow-mode deny-log: record what a tighter grant WOULD have blocked."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.permission_diff import covered_by_set  # noqa: E402


def _covered(perm: str, grant: Iterable[str]) -> bool:
    grant_l = [str(p) for p in grant]
    try:
        return covered_by_set(perm, grant_l)
    except ValueError:
        return perm in grant_l


def deny_events(
    capability_id: str,
    current: Iterable[str],
    proposed: Iterable[str],
    observed_calls: Iterable[str],
) -> list[dict[str, Any]]:
    """Calls allowed now that the proposed grant would refuse."""
    cur = list(current)
    prop = list(proposed)
    events: list[dict[str, Any]] = []
    for idx, call in enumerate(observed_calls):
        name = str(call)
        allowed_now = _covered(name, cur)
        allowed_next = _covered(name, prop)
        if allowed_now and not allowed_next:
            events.append(
                {
                    "capability_id": capability_id,
                    "call": name,
                    "index": idx,
                    "would_have_blocked": True,
                }
            )
    return events


def may_tighten(
    capability_id: str,
    current: Iterable[str],
    proposed: Iterable[str],
    observed_calls: Iterable[str],
) -> dict[str, Any]:
    events = deny_events(capability_id, current, proposed, observed_calls)
    allowed = len(events) == 0
    return {
        "capability_id": capability_id,
        "allowed": allowed,
        "would_have_blocked": len(events),
        "deny_log": events,
        "reason": (
            "zero would-have-blocked across the window"
            if allowed
            else "shadow deny-log is non-empty; refuse tighten"
        ),
    }


def drop_perm(grant: Iterable[str], perm: str) -> list[str]:
    return [p for p in grant if p != perm]


def detector_control(row: dict[str, Any], perm: str) -> dict[str, Any]:
    """Known-present path: inject one call of `perm` and require a deny event."""
    current = list(row["declared"])
    proposed = drop_perm(current, perm)
    live = list(row.get("replay_calls") or [])
    injected = live + [perm]
    live_gate = may_tighten(row["capability_id"], current, proposed, live)
    injected_gate = may_tighten(row["capability_id"], current, proposed, injected)
    fired = injected_gate["would_have_blocked"] > live_gate["would_have_blocked"]
    return {
        "capability_id": row["capability_id"],
        "injected": perm,
        "live_would_have_blocked": live_gate["would_have_blocked"],
        "injected_would_have_blocked": injected_gate["would_have_blocked"],
        "fired_on_injected": fired,
        "live_allowed": live_gate["allowed"],
        "injected_refused": not injected_gate["allowed"],
    }
