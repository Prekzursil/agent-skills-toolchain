"""Admit/refuse a new MCP tier from the process table (IMP-0472)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcp_process_guard.process_table import census
from mcp_process_guard.scope import inert_root_disables, would_spawn_names


@dataclass
class TierDecision:
    action: str
    extra: int
    current_mcp: int
    predicted: int
    at_ceiling: bool
    below_ceiling: bool
    would_spawn: tuple[str, ...]
    inert_root_disables: tuple[str, ...]
    transport_recommended: str


def evaluate_new_tier(
    rows: list[dict],
    cfg: dict[str, Any],
    *,
    budget: int,
    transport: str,
) -> TierDecision:
    snap = census(rows, source="guard")
    spawn = would_spawn_names(cfg)
    inert = inert_root_disables(cfg)
    extra = 0
    if transport == "stdio-per-session":
        extra = len(spawn)
    predicted = snap.mcp_count + extra
    at_ceiling = predicted >= budget and extra > 0
    below = predicted < budget
    if transport == "shared-long-lived":
        extra = 0
        predicted = snap.mcp_count
        at_ceiling = False
        below = predicted <= budget
        action = "permit" if predicted <= budget else "refuse"
        rec = "shared-long-lived"
    elif at_ceiling:
        action = "refuse"
        rec = "shared-long-lived"
    else:
        action = "permit"
        rec = transport
    return TierDecision(
        action=action,
        extra=extra if transport == "stdio-per-session" else 0,
        current_mcp=snap.mcp_count,
        predicted=predicted,
        at_ceiling=at_ceiling,
        below_ceiling=below,
        would_spawn=spawn,
        inert_root_disables=inert,
        transport_recommended=rec,
    )
