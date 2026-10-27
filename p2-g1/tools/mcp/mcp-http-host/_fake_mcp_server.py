#!/usr/bin/env python3
"""Minimal stdio MCP server used as a deterministic test fixture.

Newline-delimited JSON-RPC over stdio (the exact wire the real hubs speak),
stdlib only.  It answers ``initialize`` / ``tools/list`` / ``tools/call`` and,
crucially, echoes its own ``os.getpid()`` in ``serverInfo.pid`` and in the
``whoami`` tool result - that is how a test proves two HTTP clients are served
by the SAME shared child process.  A JSON-RPC notification (no ``id``) gets no
reply, per the spec.
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
        return None  # notification -> no reply
    rid = msg.get("id")
    method = msg.get("method")
    if method == "initialize":
        return _result(
            rid,
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "fake-mcp",
                    "version": "0.0.1",
                    "pid": os.getpid(),
                },
            },
        )
    if method == "tools/list":
        return _result(
            rid,
            {
                "tools": [
                    {
                        "name": "whoami",
                        "description": "return this server's pid",
                        "inputSchema": {"type": "object", "properties": {}},
                    }
                ]
            },
        )
    if method == "tools/call":
        name = (msg.get("params") or {}).get("name")
        if name == "whoami":
            return _result(
                rid,
                {
                    "content": [
                        {"type": "text", "text": json.dumps({"pid": os.getpid()})}
                    ]
                },
            )
        return _error(rid, -32602, f"unknown tool: {name}")
    if method == "ping":
        return _result(rid, {})
    return _error(rid, -32601, f"method not found: {method}")


def main() -> int:
    # FAKE_NOISE=1 emits a non-JSON line before each reply, exercising the
    # host's "skip unparseable stdout line" defence.
    noise = os.environ.get("FAKE_NOISE") == "1"
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
            if noise:
                sys.stdout.write("this-is-not-json\n")
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
