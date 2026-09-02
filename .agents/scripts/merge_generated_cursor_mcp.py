#!/usr/bin/env python3
"""Merge agents-managed MCP servers into Cursor's ~/.cursor/mcp.json.

Reads .agents/agents.json (source of truth) and merges the registry servers
into the live .cursor/mcp.json — using clean names (no agents__ prefix),
preserving manually-configured non-registry servers, and skipping servers
already provided by installed Cursor plugins.

Cursor is not a first-class target in mcp_control_plane (VALID_TARGETS is
{claude, codex}), so this merge mirrors the *claude* target selection: Cursor
should expose the same custom/local MCP surface as Claude Code.

Cursor-specific rendering differences vs the Claude merge:
- Credential references use Cursor's interpolation syntax ``${env:NAME}``
  (plain ``${NAME}`` is passed through literally by Cursor and would clobber
  inherited environment values).
- A timestamped backup of mcp.json is taken by default before writing
  (disable with --no-backup).
- G-6=6B allowlist (``CURSOR_ENABLED_SERVERS``): merge emits **only** these
  names. Parked catalog is ``.agents/mcp-cursor-parked-31.json``, not mcp.json.
  ``sync_shared_state.ps1`` must not re-insert the 31 even as ``disabled``.
- The registry is the only source of an entry's body; the live file is never
  read back as a fallback source (see ``merge_cursor_mcp_servers``).
- ``--check`` reports drift between the live file and what this merge would
  render, and writes nothing — the read-only probe for off-registry hand edits.
- An http server may declare ``x_cursor.stdio_bridge`` (``command`` + ``args``):
  Cursor then runs that per-session stdio shim with ``--url <registry url>``
  appended instead of dialing the URL itself. Used for ``basic-memory``, whose
  shared daemon restarts near-daily and whose stale session Cursor's own client
  never heals (``.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md``). Claude and
  Codex renderers ignore the key. Rendering is OS-independent, so ``--check``
  agrees on this entry from Linux as well.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import platform
import re
import shutil
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import mcp_control_plane as control


DEFAULT_PROJECT_ROOT = pathlib.Path(r"C:\Users\Prekzursil")
DEFAULT_LIVE_CONFIG = DEFAULT_PROJECT_ROOT / ".cursor" / "mcp.json"
DEFAULT_AGENTS_CONFIG = DEFAULT_PROJECT_ROOT / ".agents" / "agents.json"

# Servers intentionally left plugin-managed in Cursor. The tavily marketplace
# plugin is explicitly enabled in ~/.cursor/settings.json and mounts the same
# server; rendering it here would double-mount it.
CURSOR_PLUGIN_PROVIDED_SERVERS = frozenset({"tavily"})

# Registry servers deliberately NOT exposed to Cursor. These are present in
# .claude.json but explicitly denied in Claude's settings.json permissions;
# Cursor has no deny mechanism, so parity means not mounting them at all.
CURSOR_DENIED_SERVERS = frozenset({"markitdown", "meta-tool"})

# G-6=6B (2026-08-27): Cursor mcp.json emits only this keep-list.
# The 31 parked servers live in ``.agents/mcp-cursor-parked-31.json`` (4D MOVE
# imports from there; do not Enable in Cursor). Mixpanel stays absent.
# A later ``sync_shared_state.ps1`` Cursor merge must not re-insert the 31
# even as ``disabled: true``.
CURSOR_ENABLED_SERVERS = frozenset(
    {
        "agent-mail",
        "basic-memory",
        "chrome-devtools",
        "context7",
        "firecrawl",
        "playwright",
    }
)

ENV_REF_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")

IS_WINDOWS = platform.system() == "Windows"


def load_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def to_cursor_reference(value: Any) -> Any:
    """Rewrite ``${NAME}`` env references to Cursor's ``${env:NAME}`` syntax."""
    if not isinstance(value, str):
        return value
    return ENV_REF_RE.sub(lambda m: f"${{env:{m.group(1)}}}", value)


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


def cursor_stdio_bridge(server: Mapping[str, Any]) -> dict[str, Any] | None:
    """The ``x_cursor.stdio_bridge`` override, or None when Cursor dials the URL."""
    x_cursor = server.get("x_cursor")
    if not isinstance(x_cursor, Mapping):
        return None
    bridge = x_cursor.get("stdio_bridge")
    return dict(bridge) if isinstance(bridge, Mapping) else None


def build_cursor_server(name: str, server: dict[str, Any]) -> dict[str, Any] | None:
    """Convert an agents.json server definition to a .cursor/mcp.json entry."""
    transport = server.get("transport", "stdio")

    if transport == "http":
        bridge = cursor_stdio_bridge(server)
        if bridge is not None:
            # Cursor runs a per-session stdio shim that dials the registry URL.
            # The URL is appended here, never repeated in the registry, so the
            # shim can only ever point at the daemon the registry declares.
            command, args = wrap_for_windows(
                str(bridge["command"]),
                [str(a) for a in bridge.get("args", [])] + ["--url", server["url"]],
            )
            return {"command": command, "args": args}
        entry: dict[str, Any] = {
            "url": server["url"],
        }
        headers = dict(server.get("headers", {}))
        x_codex = server.get("x_codex", {})
        bearer_env = (
            x_codex.get("bearer_token_env_var") if isinstance(x_codex, dict) else None
        )
        if bearer_env and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer ${{{bearer_env}}}"
        if headers:
            entry["headers"] = {
                key: to_cursor_reference(value) for key, value in headers.items()
            }
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
        entry["env"] = {key: to_cursor_reference(value) for key, value in env.items()}

    if server.get("cwd"):
        entry["cwd"] = server["cwd"]

    return entry


def cursor_excluded_servers() -> frozenset[str]:
    return CURSOR_PLUGIN_PROVIDED_SERVERS | CURSOR_DENIED_SERVERS


def stamp_cursor_g3d(entry: Mapping[str, Any], name: str) -> dict[str, Any]:
    """Emit a keep-list block enabled. Non-keepers are filtered before this."""
    stamped = dict(entry)
    if name in CURSOR_ENABLED_SERVERS:
        stamped.pop("disabled", None)
    return stamped


def merge_cursor_mcp_servers(
    live_servers: Mapping[str, Any],
    generated: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    """Merge registry-rendered servers into live mcpServers with G-6=6B allowlist.

    Only ``CURSOR_ENABLED_SERVERS`` are emitted. Parked servers stay in
    ``.agents/mcp-cursor-parked-31.json``. A later sync cannot re-insert the
    31 even as ``disabled: true``. Mixpanel stays absent.

    The registry is the ONLY source of an entry's body. The live file supplies
    key order and nothing else: a keep-list name the registry does not generate
    is dropped, never adopted. Adopting it was how an off-registry hand edit —
    measured 2026-09-01 as a stdio wrapper in front of the shared
    ``basic-memory`` HTTP daemon — could outlive a sync, with
    ``stamp_cursor_g3d`` then stripping ``disabled`` and force-enabling it.
    """
    merged: dict[str, Any] = {}
    for name in live_servers:
        if name not in CURSOR_ENABLED_SERVERS or name not in generated:
            continue
        merged[name] = stamp_cursor_g3d(generated[name], name)
    for name, entry in generated.items():
        if name not in CURSOR_ENABLED_SERVERS:
            continue
        if name not in merged:
            merged[name] = stamp_cursor_g3d(entry, name)
    return merged


def build_managed_servers_from_agents(agents_config: dict) -> dict[str, dict[str, Any]]:
    selected = control.select_target_servers(
        agents_config,
        "claude",
        plugin_provided=cursor_excluded_servers(),
    )
    rendered = {
        name: build_cursor_server(name, server) for name, server in selected.items()
    }
    result = {name: entry for name, entry in rendered.items() if entry is not None}
    control.assert_exact_target_parity(
        agents_config,
        "claude",
        result,
        plugin_provided=cursor_excluded_servers(),
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge agents-managed MCP servers into Cursor's .cursor/mcp.json"
    )
    parser.add_argument(
        "--live", default=str(DEFAULT_LIVE_CONFIG), help="Path to live .cursor/mcp.json"
    )
    parser.add_argument(
        "--agents-config",
        default=str(DEFAULT_AGENTS_CONFIG),
        help="Path to .agents/agents.json",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write merged config back to .cursor/mcp.json",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip the timestamped backup before writing",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Report drift between the live file and the registry; write nothing. "
            "Run this on the same OS that renders the file: the npx 'cmd /c' wrapper "
            "is Windows-only, so a Linux run reports the npx servers as false drift"
        ),
    )
    args = parser.parse_args()

    if args.check and args.write:
        parser.error("--check is read-only and cannot be combined with --write")

    live_path = pathlib.Path(args.live)
    agents_config_path = pathlib.Path(args.agents_config)

    agents_config = load_json(agents_config_path)
    live_config = load_json(live_path) if live_path.exists() else {}
    control.validate_registry(agents_config)

    servers = agents_config.get("mcp", {}).get("servers", {})
    mcp_servers = live_config.get("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        mcp_servers = {}
    generated = build_managed_servers_from_agents(agents_config)

    added = []
    updated = []
    skipped_plugin = []
    skipped_denied = []
    skipped_disabled = []
    skipped_no_target = []
    skipped_parked = []

    for name, server in sorted(servers.items()):
        if name not in generated:
            if name in CURSOR_PLUGIN_PROVIDED_SERVERS:
                skipped_plugin.append(name)
            elif name in CURSOR_DENIED_SERVERS:
                skipped_denied.append(name)
            elif not server.get("enabled", True):
                skipped_disabled.append(name)
            else:
                skipped_no_target.append(name)
            continue

        if name not in CURSOR_ENABLED_SERVERS:
            skipped_parked.append(name)
            continue

        if name in mcp_servers:
            updated.append(name)
        else:
            added.append(name)

    merged = merge_cursor_mcp_servers(mcp_servers, generated)
    bridged = sorted(
        name
        for name in merged
        if cursor_stdio_bridge(servers.get(name, {})) is not None
    )

    if args.check:
        drifted = sorted(
            name
            for name in set(merged) | set(mcp_servers)
            if merged.get(name) != mcp_servers.get(name)
        )
        if drifted:
            # Names only: entries carry ${env:...} references, never values.
            print(
                "FAILED:mcp-cursor-check "
                f"live={live_path} drift={len(drifted)} servers={','.join(drifted)}"
            )
            return 1
        print(
            f"SUCCESS:mcp-cursor-check live={live_path} drift=0 managed={len(merged)}"
        )
        return 0

    live_config["mcpServers"] = merged
    enabled = [
        name
        for name, entry in merged.items()
        if not (isinstance(entry, dict) and entry.get("disabled") is True)
    ]
    disabled = [
        name
        for name, entry in merged.items()
        if isinstance(entry, dict) and entry.get("disabled") is True
    ]

    if args.write:
        if live_path.exists() and not args.no_backup:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = live_path.with_suffix(f".json.bak-{ts}")
            shutil.copy2(live_path, backup_path)

        control.atomic_write_json(live_path, live_config)

    print(
        "SUCCESS:mcp-cursor-merge "
        f"managed={len(generated)} added={len(added)} updated={len(updated)} "
        f"enabled={len(enabled)} disabled={len(disabled)} "
        f"plugin_skips={len(skipped_plugin)} denied_skips={len(skipped_denied)} "
        f"parked_skips={len(skipped_parked)} bridged={len(bridged)} "
        f"write={str(args.write).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
