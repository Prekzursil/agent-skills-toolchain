#!/usr/bin/env python3
"""Probe 2: classify dispatching from declared tool permissions.

Floor applies to dispatchers only. Body mentions of Task or mcp__codex
do not grant those tools. Linewise frontmatter scan is independent of
probe 1's mapping parse.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit_agent_roster as R  # noqa: E402

P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0063/probe2_dispatcher_classify.py"
)


def slim(agent: dict) -> dict:
    return {
        "name": agent["name"],
        "path": agent["path"],
        "kind": agent["kind"],
        "tree_id": agent["tree_id"],
        "model_tier": agent["model_tier"],
        "declared_tools": agent["declared_tools"],
        "declared_tools_linewise": agent["declared_tools_linewise"],
        "dispatching": agent["dispatching"],
        "dispatching_linewise": agent["dispatching_linewise"],
        "dispatch_reasons": agent["dispatch_reasons"],
        "below_opus_floor": agent["below_opus_floor"],
        "body_mentions_task": agent["body_mentions_task"],
    }


def main() -> int:
    inv = R.inventory()
    ctl = R.control_checks(inv)
    payload = {
        "probe": "probe2-dispatcher-classify",
        "unit_id": R.UNIT,
        "method": (
            "declared-tools field in frontmatter; spawn-tool or cross-vendor "
            "prefix => dispatching; opus floor only if dispatching"
        ),
        "command": P2,
        "production_agent_count": inv["production_agent_count"],
        "production_below_opus_floor_count": inv["production_below_opus_floor_count"],
        "control_below_opus_floor": [
            slim(a) for a in inv["control_agents"] if a["below_opus_floor"]
        ],
        "production_below_opus_floor": [
            slim(a) for a in inv["production_agents"] if a["below_opus_floor"]
        ],
        "production_dispatchers": [
            slim(a) for a in inv["production_agents"] if a["dispatching"]
        ],
        "control_agents": [slim(a) for a in inv["control_agents"]],
        "control": {
            "dispatcher_sonnet_below_floor": ctl["dispatcher_sonnet_below_floor"],
            "dispatcher_opus_on_floor": ctl["dispatcher_opus_on_floor"],
            "non_dispatcher_sonnet_not_floor": ctl["non_dispatcher_sonnet_not_floor"],
            "body_task_mention_not_dispatching": ctl[
                "body_task_mention_not_dispatching"
            ],
        },
        "pass": bool(
            ctl["dispatcher_sonnet_below_floor"]
            and ctl["dispatcher_opus_on_floor"]
            and ctl["non_dispatcher_sonnet_not_floor"]
            and ctl["body_task_mention_not_dispatching"]
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:AUD-0063-probe2 dispatcher or floor control", file=sys.stderr)
        return 1
    print("SUCCESS:AUD-0063-probe2 dispatcher classification and opus floor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
