#!/usr/bin/env python3
"""ADV-0053 Probe 2: empirically measure default enablement via a fresh install.

Mechanically different from Probe 1 (clause quotes). Does not read a documented
default: it creates an isolated HOME, runs the marketplace installer, and
censuses the worktree for provider clients.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from install_observe import classify_all  # noqa: E402
from stages import BUCKET_BLOCKER, BUCKET_FREE, BUCKET_OPTIN  # noqa: E402

UNIT = "ADV-0053"


def main() -> int:
    result = classify_all()
    buckets = result["buckets"]
    classified = result["classified"]
    obs = result["observation"]
    live_blockers = result["live_release_blockers"]

    planted_blocker = next(
        r for r in classified if r["id"] == "planted.restricted-default-on"
    )
    planted_optin = next(
        r for r in classified if r["id"] == "planted.restricted-opt-in-warned"
    )
    clean = next(
        r for r in classified if r["id"] == "blueprint.customer-council.compose"
    )

    mkt = obs["marketplace_install"]
    install_denied = bool(mkt["refused"]) and not mkt["placed_any_file"]
    no_home_config = obs["home_config_files"] == []
    fresh_inert = no_home_config and not obs.get("isolated_home_mcp_active")
    blocker_is_planted_only = buckets[BUCKET_BLOCKER] == ["planted.restricted-default-on"]
    optin_is_planted = "planted.restricted-opt-in-warned" in buckets[BUCKET_OPTIN]
    clean_free = clean["bucket"] == BUCKET_FREE
    planted_flagged = planted_blocker["bucket"] == BUCKET_BLOCKER
    planted_optin_ok = planted_optin["bucket"] == BUCKET_OPTIN
    three_way = result["three_way_nonempty"]
    not_flat = (
        set(buckets[BUCKET_BLOCKER]) != set(buckets[BUCKET_FREE])
        and buckets[BUCKET_BLOCKER]
        and buckets[BUCKET_OPTIN]
        and buckets[BUCKET_FREE]
    )

    ok = (
        install_denied
        and fresh_inert
        and blocker_is_planted_only
        and not live_blockers
        and planted_flagged
        and planted_optin_ok
        and optin_is_planted
        and clean_free
        and three_way
        and not_flat
        and obs["method"].startswith("isolated-HOME")
    )
    out = {
        "probe": "probe2-fresh-install-default",
        "unit_id": UNIT,
        "method": obs["method"],
        "marketplace_refused": install_denied,
        "home_config_files": obs["home_config_files"],
        "isolated_home_mcp_active": obs.get("isolated_home_mcp_active"),
        "tools_mcp_present": obs["tools_mcp_present"],
        "search_hub_tree_present": obs.get("search_hub_tree_present"),
        "github_workflows_present": obs["github_workflows_present"],
        "importable": obs["importable"],
        "env_key_present_boolean_only": obs["env_key_present_boolean_only"],
        "platform_tools_network_hits": obs["platform_tools_network_hits"],
        "any_live_provider_client": obs["any_live_provider_client"],
        "buckets": buckets,
        "live_release_blockers": live_blockers,
        "planted_blocker": planted_blocker["bucket"],
        "planted_optin": planted_optin["bucket"],
        "clean_bucket": clean["bucket"],
        "three_way_nonempty": three_way,
        "pass": ok,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"install_denied={install_denied} live_blockers={live_blockers} "
        f"blocker={buckets[BUCKET_BLOCKER]} optin={buckets[BUCKET_OPTIN]}"
    )
    if not ok:
        print(f"FAILED:{UNIT}-probe2 fresh-install default enablement")
        return 1
    print(f"SUCCESS:{UNIT}-probe2 fresh-install default enablement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
