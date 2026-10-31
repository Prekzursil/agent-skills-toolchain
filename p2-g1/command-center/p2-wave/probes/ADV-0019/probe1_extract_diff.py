#!/usr/bin/env python3
"""Probe 1: extract instruction tokens and set-difference against live PATH/plugin inventory."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402


def path_live(name: str) -> bool:
    if name in {C.PLUGIN_NAME, C.GHOST_MCP} or name.startswith("mcp__"):
        return False
    return shutil.which(name) is not None


def plugin_live(name: str, enabled: dict[str, bool]) -> bool:
    key = name.lower()
    for pkg, on in enabled.items():
        if pkg.lower() == key or pkg.lower() == "agentbridge" and name == C.PLUGIN_NAME:
            return bool(on)
    return False


def main() -> int:
    corpus = C.load_corpus()
    plugins = C.load_plugin_state()
    enabled = C.enabled_plugins(plugins)
    dead = []
    live = []
    for rec in corpus["tokens"]:
        name = rec["name"]
        on_path = path_live(name)
        on_plugin = plugin_live(name, enabled)
        present = on_path or on_plugin
        row = {
            **rec,
            "path_live": on_path,
            "plugin_live": on_plugin,
            "present": present,
            "resolver": "shutil.which+plugin-state",
        }
        (live if present else dead).append(row)

    dead_names = [r["name"] for r in dead]
    live_names = [r["name"] for r in live]
    known_absent_flagged = all(n in dead_names for n in C.RETIRED)
    known_present_clean = C.KNOWN_PRESENT not in dead_names
    python_extracted = C.KNOWN_PRESENT in corpus["token_names"]
    ghost_cli_dead = C.GHOST_CLI in dead_names
    ghost_mcp_dead = C.GHOST_MCP in dead_names

    doc = {
        "probe": "probe1-extract-diff",
        "unit_id": C.UNIT,
        "resolver": "shutil.which (Python PATH) plus plugin-state enabled map",
        "not_get_command": True,
        "file_count": corpus["file_count"],
        "fixture_count": corpus["fixture_count"],
        "estate_count": corpus["estate_count"],
        "extracted": corpus["token_names"],
        "dead": dead,
        "live": live,
        "dead_names": dead_names,
        "live_names": live_names,
        "plugin_enabled": enabled,
        "controls": {
            "known_absent_get_budget_check_budget_flagged": known_absent_flagged,
            "known_present_python3_not_flagged": known_present_clean,
            "python3_extracted": python_extracted,
            "ghost_cli_dead": ghost_cli_dead,
            "ghost_mcp_dead": ghost_mcp_dead,
        },
    }
    print(json.dumps(doc, indent=1, sort_keys=True))
    if not python_extracted:
        print("FAILED:ADV-0019-probe1 python3 not extracted from corpus")
        return 1
    if not known_present_clean:
        print("FAILED:ADV-0019-probe1 known-present python3 was flagged")
        return 1
    if not known_absent_flagged:
        print("FAILED:ADV-0019-probe1 retired budget tools were not flagged")
        return 1
    if not ghost_cli_dead or not ghost_mcp_dead:
        print("FAILED:ADV-0019-probe1 planted ghosts not flagged")
        return 1
    print(
        "SUCCESS:ADV-0019-probe1 extract-diff "
        f"dead={','.join(dead_names)} present-control={C.KNOWN_PRESENT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
