#!/usr/bin/env python3
"""Merge agents-managed MCP servers into ZCode's ~/.zcode/cli/config.json.

Reads .agents/agents.json (source of truth), selects servers targeting
"zcode" (including disabled ones, rendered with enabled:false so the
owner can re-enable locally without a registry round-trip), and merges
them into the live config's mcp.servers map.

Design differences vs the Claude merger (intentional):
- Disabled registry servers are KEPT as enabled:false entries, not dropped.
- The owner's per-runtime choice is recorded in SSOT via x_zcode.enabled.
- Live-only knobs (tool_timeout_sec, env_vars) on an existing entry survive
  a re-render; transport fields (command/args/env/url) come from the registry.
- Registry servers that do NOT target zcode are removed from the live config;
  zcode-local entries absent from the registry (node_repl, cua_repl, mcphub,
  plugin servers) are preserved untouched.
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
DEFAULT_LIVE_CONFIG = DEFAULT_PROJECT_ROOT / ".zcode" / "cli" / "config.json"
DEFAULT_AGENTS_CONFIG = DEFAULT_PROJECT_ROOT / ".agents" / "agents.json"

# Live-only keys preserved across re-renders of an existing managed entry.
PRESERVED_LIVE_KEYS = ("tool_timeout_sec", "env_vars")


def select_zcode_servers(agents_config: dict) -> dict[str, dict[str, Any]]:
    """All zcode-targeted servers, enabled AND disabled (unlike select_target_servers)."""
    control.validate_registry(agents_config)
    servers = agents_config.get("mcp", {}).get("servers", {})
    selected: dict[str, dict[str, Any]] = {}
    seen_singletons: set[str] = set()
    for name in sorted(servers):
        server = servers[name]
        if "zcode" not in server.get("targets", []):
            continue
        singleton_key = str(server.get("singletonKey", name))
        if singleton_key in seen_singletons:
            continue
        seen_singletons.add(singleton_key)
        selected[name] = server
    return selected


def build_zcode_server(name: str, server: dict[str, Any]) -> dict[str, Any] | None:
    """Convert an agents.json server definition to a zcode mcp.servers entry."""
    transport = server.get("transport", "stdio")

    entry: dict[str, Any] = {}
    if transport == "http":
        entry["url"] = server["url"]
        required = [e for e in server.get("requiredEnv", []) if e in server.get("credentialNames", [])]
        if required:
            entry["bearer_token_env_var"] = required[0]
    else:
        entry["command"] = server.get("command", "")
        args = [str(a) for a in server.get("args", [])]
        if args:
            entry["args"] = args
        env = server.get("env", {})
        if env:
            entry["env"] = env

    x_zcode = server.get("x_zcode", {})
    enabled = x_zcode.get("enabled", server.get("enabled", True)) if isinstance(x_zcode, dict) else server.get("enabled", True)
    if enabled is False:
        entry["enabled"] = False

    if transport == "stdio" and not entry.get("command"):
        return None
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge agents-managed MCP servers into ZCode's config.json"
    )
    parser.add_argument("--live", default=str(DEFAULT_LIVE_CONFIG))
    parser.add_argument("--agents-config", default=str(DEFAULT_AGENTS_CONFIG))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--backup", action="store_true")
    args = parser.parse_args()

    live_path = pathlib.Path(args.live)
    agents_config_path = pathlib.Path(args.agents_config)

    agents_config = json.loads(agents_config_path.read_text(encoding="utf-8"))
    live_config = json.loads(live_path.read_text(encoding="utf-8"))

    registry = agents_config.get("mcp", {}).get("servers", {})
    selected = select_zcode_servers(agents_config)

    mcp_servers = live_config.setdefault("mcp", {}).setdefault("servers", {})

    added, updated, preserved_local, removed_no_target = [], [], [], []
    for name in sorted(set(registry) | set(mcp_servers)):
        live_entry = mcp_servers.get(name)
        if name in selected:
            rendered = build_zcode_server(name, selected[name])
            if rendered is None:
                print(f"WARN: {name} rendered empty; skipped")
                continue
            if live_entry is not None:
                for key in PRESERVED_LIVE_KEYS:
                    if key in live_entry:
                        rendered[key] = live_entry[key]
                updated.append(name)
            else:
                added.append(name)
            mcp_servers[name] = rendered
        elif name in registry:
            # Registry server not targeting zcode: single-source discipline.
            if live_entry is not None:
                mcp_servers.pop(name, None)
                removed_no_target.append(name)
        else:
            preserved_local.append(name)

    expected = set(selected)
    actual = {n for n in mcp_servers if n in selected}
    if actual != expected:
        missing = sorted(expected - actual)
        print(f"FAILED:mcp-zcode-merge parity mismatch missing={missing!r}")
        return 1

    if args.write:
        if args.backup:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = live_path.with_suffix(f".json.bak-{ts}")
            shutil.copy2(live_path, backup_path)
        control.atomic_write_json(live_path, live_config)

    print(
        f"SUCCESS:mcp-zcode-merge managed={len(selected)} added={len(added)} "
        f"updated={len(updated)} local_preserved={len(preserved_local)} "
        f"removed_no_target={len(removed_no_target)} write={str(args.write).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
