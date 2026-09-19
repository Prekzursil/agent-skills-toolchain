#!/usr/bin/env python3
"""Merge agents-managed MCP servers into Gemini CLI's settings.json.

Clone of merge_generated_claude_mcp.py adapted for the gemini target (D7,
2026-09-19 audit): reads .agents/agents.json (source of truth), filters servers
targeting "gemini", and merges them into ~/.gemini/settings.json mcpServers —
preserving manually-configured entries whose names are NOT registry rows,
popping registry rows that lost the gemini target or are disabled, and always
dropping "memory" (estate G-81: no server named memory outside basic-memory).

Entry shape follows the live gemini config's own conventions (trust:true on
every entry; http entries carry url+type; stdio entries carry command/args/env
with forward-slash paths). Backup is ALWAYS taken before writing (this surface
has no git history).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
from datetime import datetime
from typing import Any

import mcp_control_plane as control

DEFAULT_PROJECT_ROOT = pathlib.Path(r"C:\Users\Prekzursil")
DEFAULT_LIVE_CONFIG = DEFAULT_PROJECT_ROOT / ".gemini" / "settings.json"
DEFAULT_AGENTS_CONFIG = DEFAULT_PROJECT_ROOT / ".agents" / "agents.json"


def load_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fwd(value: Any) -> Any:
    """Normalize windows backslashes to forward slashes for gemini entries."""
    if isinstance(value, str):
        return value.replace("\\", "/")
    if isinstance(value, list):
        return [fwd(v) for v in value]
    if isinstance(value, dict):
        return {k: fwd(v) for k, v in value.items()}
    return value


def build_gemini_server(name: str, server: dict[str, Any]) -> dict[str, Any] | None:
    transport = server.get("transport", "stdio")
    if transport == "http":
        entry: dict[str, Any] = {"type": "http", "url": server["url"], "trust": True}
        headers = dict(server.get("headers", {}))
        if headers:
            entry["headers"] = fwd(headers)
        return entry
    command = server.get("command", "")
    if not command:
        return None
    args = [str(a) for a in server.get("args", [])]
    entry: dict[str, Any] = {"command": command, "trust": True}
    if args:
        entry["args"] = args
    env = server.get("env", {})
    if env:
        entry["env"] = fwd(env)
    return fwd(entry)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", default=str(DEFAULT_LIVE_CONFIG))
    parser.add_argument("--agents-config", default=str(DEFAULT_AGENTS_CONFIG))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    live_path = pathlib.Path(args.live)
    agents_config = load_json(pathlib.Path(args.agents_config))
    control.validate_registry(agents_config)
    live = load_json(live_path)
    servers = agents_config.get("mcp", {}).get("servers", {})
    mcp = live.setdefault("mcpServers", {})

    added, updated = [], []
    # PRESERVE-MANUAL semantics (fixed 2026-09-19 after the first run popped 27
    # curated manual servers — the claude merge's pop rule assumes a fully managed
    # surface; gemini's is a hybrid). Only registry rows that explicitly target
    # gemini are written; every other existing entry is a MANUAL entry and stays
    # untouched. The sole removal is "memory" (estate G-81).
    for name, server in sorted(servers.items()):
        targets = server.get("targets") or []
        selected = server.get("enabled", True) and "gemini" in targets
        if not selected:
            continue
        entry = build_gemini_server(name, server)
        if entry is None:
            continue
        (updated if name in mcp else added).append(name)
        mcp[name] = entry

    mcp.pop("memory", None)

    if args.write:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(live_path, live_path.with_suffix(f".json.bak-{ts}"))
        control.atomic_write_json(live_path, live)

    print(
        f"SUCCESS:mcp-gemini-merge total={len(mcp)} added={len(added)} "
        f"updated={len(updated)} write={str(args.write).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
