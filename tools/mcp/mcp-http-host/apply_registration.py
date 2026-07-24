#!/usr/bin/env python3
"""apply_registration.py - flip a hub's ~/.mcp.json entry from stdio to shared HTTP.

APPLY-WHEN-CLOSED. MCP config changes take effect only on a Claude restart, and
``~/.claude.json`` is rewritten by any live session every ~30s, so this tool
deliberately edits the CANONICAL ``~/.mcp.json`` (the no-drift source the owner
promotes into ``~/.claude.json``) - never ``~/.claude.json`` directly. Run it
with Claude CLOSED, then promote / restart.

It swaps the named server's entry from
``{"type": "stdio", "command": ..., "args": [...]}`` to a shared-transport entry.
``--transport http`` (the default) writes
``{"type": "http", "url": "http://127.0.0.1:<port>/mcp"}`` and ``--transport sse``
writes ``{"type": "sse", "url": "http://127.0.0.1:<port>/sse"}`` - the SSE endpoint
the mcp-proxy bridge (``run_host.ps1 -Bridge mcp-proxy``) serves alongside the
streamable-HTTP one. Either way the entry MUST carry ``"type"`` or Claude Code reads
a bare ``url`` as a stdio misconfig. The path defaults per transport (``/mcp`` for
http, ``/sse`` for sse) and can be overridden with ``--path``. It NEVER touches
``accounts.json`` or any secret. Dry-run by default; ``--apply`` writes after a
timestamped ``.bak-*`` backup; ``--revert-from`` restores one.

Examples::

    # preview (default, writes nothing)
    python apply_registration.py --server search-hub --port 8900
    # apply for real (Claude closed), backing up first
    python apply_registration.py --server search-hub --port 8900 --apply
    # register the SSE transport instead of streamable-http
    python apply_registration.py --server search-hub --port 8900 --transport sse --apply
    # undo
    python apply_registration.py --revert-from ~/.mcp.json.bak-20260723-120000
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
import time
from typing import Any

DEFAULT_TARGET = os.path.expanduser("~/.mcp.json")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_HTTP_PATH = "/mcp"
DEFAULT_SSE_PATH = "/sse"
DEFAULT_PATH = DEFAULT_HTTP_PATH  # back-compat alias: the http default path


def http_entry(host: str, port: int, path: str) -> dict[str, str]:
    """The Claude Code ``http`` (Streamable-HTTP) server entry (``type`` is mandatory)."""
    return {"type": "http", "url": f"http://{host}:{port}{path}"}


def sse_entry(host: str, port: int, path: str) -> dict[str, str]:
    """The Claude Code ``sse`` server entry (mcp-proxy serves ``/sse`` too; ``type`` mandatory)."""
    return {"type": "sse", "url": f"http://{host}:{port}{path}"}


_ENTRY_BUILDERS = {"http": http_entry, "sse": sse_entry}


def build_entry(transport: str, host: str, port: int, path: str) -> dict[str, str]:
    """Return the server entry for ``transport`` (``http`` streamable or ``sse``)."""
    try:
        builder = _ENTRY_BUILDERS[transport]
    except KeyError:
        raise ValueError(
            f"unknown transport {transport!r} (choose http or sse)"
        ) from None
    return builder(host, port, path)


def default_path(transport: str) -> str:
    """Conventional endpoint path per transport: ``/sse`` for sse, else ``/mcp``."""
    return DEFAULT_SSE_PATH if transport == "sse" else DEFAULT_HTTP_PATH


def load_config(target: str) -> dict[str, Any]:
    with open(target, encoding="utf-8") as handle:
        return json.load(handle)


def apply_change(
    config: dict[str, Any], server: str, new_entry: dict[str, str]
) -> dict[str, Any]:
    """Return a NEW config with ``server`` repointed to ``new_entry`` (no mutation)."""
    servers = config.get("mcpServers", {})
    if server not in servers:
        raise KeyError(f"server {server!r} not found in mcpServers ({sorted(servers)})")
    updated = copy.deepcopy(config)
    updated["mcpServers"][server] = new_entry
    return updated


def _write_config(target: str, config: dict[str, Any]) -> None:
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _backup(target: str) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = f"{target}.bak-{stamp}"
    shutil.copy2(target, dest)
    return dest


def revert(target: str, backup_path: str) -> None:
    shutil.copy2(backup_path, target)


def _run(args: argparse.Namespace) -> int:
    if args.revert_from:
        revert(args.target, args.revert_from)
        print(f"reverted {args.target} from {args.revert_from}")
        return 0

    config = load_config(args.target)
    path = args.path if args.path is not None else default_path(args.transport)
    new_entry = build_entry(args.transport, args.host, args.port, path)
    try:
        current = config.get("mcpServers", {})[args.server]
    except KeyError:
        print(f"error: server {args.server!r} not in {args.target}", file=sys.stderr)
        return 1
    if current == new_entry:
        print(f"no change: {args.server} is already {json.dumps(new_entry)}")
        return 0

    print(f"server : {args.server}")
    print(f"  from : {json.dumps(current)}")
    print(f"  to   : {json.dumps(new_entry)}")
    if not args.apply:
        print("(dry-run - pass --apply to write; add nothing else)")
        return 0

    backup_path = None if args.no_backup else _backup(args.target)
    _write_config(args.target, apply_change(config, args.server, new_entry))
    if backup_path:
        print(f"backup : {backup_path}")
    print(
        f"applied: {args.target} updated. Restart Claude (and promote to ~/.claude.json) to take effect."
    )
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Flip a hub's ~/.mcp.json entry stdio->http (apply-when-closed)."
    )
    parser.add_argument(
        "--target", default=DEFAULT_TARGET, help="config file (default: ~/.mcp.json)"
    )
    parser.add_argument("--server", help="server key to repoint, e.g. search-hub")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument(
        "--port", type=int, help="port the shared bridge (mcp-proxy / host) serves on"
    )
    parser.add_argument(
        "--path",
        default=None,
        help="endpoint path (default: /mcp for http, /sse for sse)",
    )
    parser.add_argument(
        "--transport",
        choices=("http", "sse"),
        default="http",
        help="register as streamable-http (default) or sse; mcp-proxy serves both",
    )
    parser.add_argument(
        "--apply", action="store_true", help="write the change (default is dry-run)"
    )
    parser.add_argument(
        "--no-backup", action="store_true", help="skip the timestamped backup"
    )
    parser.add_argument("--revert-from", help="restore --target from this backup file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if not args.revert_from and (not args.server or args.port is None):
        print(
            "error: --server and --port are required (or use --revert-from)",
            file=sys.stderr,
        )
        return 2
    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
