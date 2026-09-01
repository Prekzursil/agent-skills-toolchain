#!/usr/bin/env python3
"""Merge agents-managed MCP servers into Claude Code's .claude.json.

Reads .agents/agents.json (source of truth), filters servers targeting
"claude", and merges them into the live .claude.json — using clean names
(no agents__ prefix), preserving manually-configured standalone servers,
and skipping servers already provided by Claude plugins.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import platform
import shutil
from datetime import datetime
from typing import Any

import mcp_control_plane as control


DEFAULT_PROJECT_ROOT = pathlib.Path(r"C:\Users\Prekzursil")
DEFAULT_LIVE_CONFIG = DEFAULT_PROJECT_ROOT / ".claude.json"
DEFAULT_AGENTS_CONFIG = DEFAULT_PROJECT_ROOT / ".agents" / "agents.json"

# Servers intentionally left plugin-managed in Claude.
# For full direct parity, several plugin-backed servers are also rendered into
# .claude.json from .agents so Codex and Claude expose the same custom/local MCP
# surface. Keep only the servers here that should remain plugin-only.
PLUGIN_PROVIDED_SERVERS = control.CLAUDE_PLUGIN_PROVIDED_SERVERS

IS_WINDOWS = platform.system() == "Windows"


def load_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    control.atomic_write_json(path, payload)


def needs_cmd_wrapper(command: str) -> bool:
    """Check if a command needs cmd /c wrapper on Windows."""
    if not IS_WINDOWS:
        return False
    bare = command.strip().lower()
    return bare in ("npx", "npm", "node") or bare.startswith("npx ")


def wrap_for_windows(command: str, args: list[str]) -> tuple[str, list[str]]:
    """Wrap npx/npm commands with cmd /c on Windows."""
    if needs_cmd_wrapper(command):
        return "cmd", ["/c", command] + args
    return command, args


def build_claude_server(name: str, server: dict[str, Any]) -> dict[str, Any] | None:
    """Convert an agents.json server definition to a .claude.json mcpServers entry."""
    transport = server.get("transport", "stdio")

    if transport == "http":
        # HTTP/SSE servers use url directly
        entry: dict[str, Any] = {
            "type": "http",
            "url": server["url"],
        }
        headers = dict(server.get("headers", {}))
        x_codex = server.get("x_codex", {})
        bearer_env = x_codex.get("bearer_token_env_var") if isinstance(x_codex, dict) else None
        if bearer_env and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer ${{{bearer_env}}}"
        if headers:
            entry["headers"] = headers
        return entry

    # stdio transport
    command = server.get("command", "")
    args = [str(a) for a in server.get("args", [])]

    command, args = wrap_for_windows(command, args)

    entry = {
        "command": command,
        "args": args,
    }

    env = server.get("env", {})
    if env:
        entry["env"] = env

    if server.get("cwd"):
        entry["cwd"] = server["cwd"]

    return entry


def build_managed_servers_from_agents(agents_config: dict) -> dict[str, dict[str, Any]]:
    selected = control.select_target_servers(
        agents_config,
        "claude",
        plugin_provided=PLUGIN_PROVIDED_SERVERS,
    )
    rendered = {
        name: build_claude_server(name, server)
        for name, server in selected.items()
    }
    result = {name: entry for name, entry in rendered.items() if entry is not None}
    control.assert_exact_target_parity(
        agents_config,
        "claude",
        result,
        plugin_provided=PLUGIN_PROVIDED_SERVERS,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge agents-managed MCP servers into Claude Code's .claude.json"
    )
    parser.add_argument("--live", default=str(DEFAULT_LIVE_CONFIG),
                        help="Path to live .claude.json")
    parser.add_argument("--agents-config", default=str(DEFAULT_AGENTS_CONFIG),
                        help="Path to .agents/agents.json")
    parser.add_argument("--write", action="store_true",
                        help="Write merged config back to .claude.json")
    parser.add_argument("--backup", action="store_true",
                        help="Create a backup before writing (off by default)")
    args = parser.parse_args()

    live_path = pathlib.Path(args.live)
    agents_config_path = pathlib.Path(args.agents_config)

    agents_config = load_json(agents_config_path)
    live_config = load_json(live_path)
    control.validate_registry(agents_config)

    servers = agents_config.get("mcp", {}).get("servers", {})
    mcp_servers = live_config.setdefault("mcpServers", {})
    generated = build_managed_servers_from_agents(agents_config)

    added = []
    updated = []
    skipped_plugin = []
    skipped_disabled = []
    skipped_no_target = []

    for name, server in sorted(servers.items()):
        if name not in generated:
            if name in PLUGIN_PROVIDED_SERVERS:
                skipped_plugin.append(name)
            elif not server.get("enabled", True):
                skipped_disabled.append(name)
            else:
                skipped_no_target.append(name)
            mcp_servers.pop(name, None)
            continue

        entry = generated[name]
        if name in mcp_servers:
            updated.append(name)
        else:
            added.append(name)

        mcp_servers[name] = entry

    mcp_servers.pop("memory", None)

    if args.write:
        if args.backup:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = live_path.with_suffix(f".json.bak-{ts}")
            shutil.copy2(live_path, backup_path)

        dump_json(live_path, live_config)

    print(
        "SUCCESS:mcp-claude-merge "
        f"managed={len(generated)} added={len(added)} updated={len(updated)} "
        f"plugin_skips={len(skipped_plugin)} write={str(args.write).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
