#!/usr/bin/env python3
"""Planted MCP stdio server that advertises ZERO tools.

Both-states pair with tools/mcp/mcp-http-host/_fake_mcp_server.py (one tool).
A counter that cannot report zero on this fixture is lying about emptiness;
a counter that reports zero on the one-tool fake is not reaching the server.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any


def _result(rid: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _error(rid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle(msg: dict[str, Any]) -> dict[str, Any] | None:
    if "id" not in msg:
        return None
    rid = msg.get("id")
    method = msg.get("method")
    if method == "initialize":
        return _result(
            rid,
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "planted-zero-tools",
                    "version": "0.0.1",
                    "pid": os.getpid(),
                },
            },
        )
    if method == "tools/list":
        return _result(rid, {"tools": []})
    if method == "ping":
        return _result(rid, {})
    return _error(rid, -32601, f"method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
