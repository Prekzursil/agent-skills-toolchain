#!/usr/bin/env python3
"""Probe 2 — budget: a new tier is refused at the ceiling; permitted below it.

Mechanically different from probe 1 (which only compares config scopes):
this probe injects process-table counts and asserts admit/refuse.
CONTROL: below the ceiling, startup is still permitted.
When stdio would exceed, shared long-lived reuse is preferred.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from mcp_process_guard.guard import evaluate_new_tier  # noqa: E402
from mcp_process_guard.process_table import census, synthetic_stdio_table  # noqa: E402
from mcp_process_guard.scope import fixture_inert_root_disable  # noqa: E402

SERVERS = ("alpha", "beta", "gamma")


def main() -> int:
    cfg = fixture_inert_root_disable(SERVERS)

    at_ceiling_rows = synthetic_stdio_table(4, SERVERS)  # 12 MCP
    at_ceiling = evaluate_new_tier(at_ceiling_rows, cfg, budget=12, transport="stdio-per-session")
    below_rows = synthetic_stdio_table(2, SERVERS)  # 6 MCP
    below = evaluate_new_tier(below_rows, cfg, budget=20, transport="stdio-per-session")
    mixed = synthetic_stdio_table(5, SERVERS, shared=SERVERS)  # 15+3=18
    stdio_over = evaluate_new_tier(mixed, cfg, budget=20, transport="stdio-per-session")
    shared_ok = evaluate_new_tier(mixed, cfg, budget=20, transport="shared-long-lived")

    if at_ceiling.action != "refuse" or not at_ceiling.at_ceiling:
        print("FAILED:IMP-0472-probe2 new tier was not refused at the ceiling")
        return 1
    if below.action != "permit" or not below.below_ceiling:
        print("FAILED:IMP-0472-probe2 CONTROL failed: below-ceiling startup was not permitted")
        return 1
    if stdio_over.action != "refuse" or stdio_over.transport_recommended != "shared-long-lived":
        print("FAILED:IMP-0472-probe2 stdio exceed did not prefer shared long-lived")
        return 1
    if shared_ok.action != "permit" or shared_ok.extra != 0:
        print("FAILED:IMP-0472-probe2 shared reuse was not permitted at extra=0")
        return 1

    ceiling_census = census(at_ceiling_rows, source="probe2-ceiling")
    below_census = census(below_rows, source="probe2-below")
    payload = {
        "probe": "probe2-budget",
        "unit_id": "IMP-0472",
        "ceiling": {
            "budget": 12,
            "current_mcp": at_ceiling.current_mcp,
            "extra": at_ceiling.extra,
            "predicted": at_ceiling.predicted,
            "action": at_ceiling.action,
            "at_ceiling": at_ceiling.at_ceiling,
            "multiplier": ceiling_census.multiplier,
            "transport_recommended": at_ceiling.transport_recommended,
        },
        "below_ceiling_control": {
            "budget": 20,
            "current_mcp": below.current_mcp,
            "predicted": below.predicted,
            "action": below.action,
            "below_ceiling": below.below_ceiling,
            "multiplier": below_census.multiplier,
        },
        "shared_preference": {
            "stdio_action": stdio_over.action,
            "stdio_predicted": stdio_over.predicted,
            "stdio_recommended": stdio_over.transport_recommended,
            "shared_action": shared_ok.action,
            "shared_extra": shared_ok.extra,
            "shared_predicted": shared_ok.predicted,
        },
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"ceiling_action={at_ceiling.action} below_action={below.action} "
        f"shared_action={shared_ok.action} extra_shared={shared_ok.extra}"
    )
    print("SUCCESS:IMP-0472-probe2 budget: refused at ceiling; permitted below; shared preferred")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
