#!/usr/bin/env python3
"""Minimal MCP stdio backend used by the hub integration tests.

Usage: ``python fake_backend.py <name> <comma,separated,tool,names>``

It enumerates the given tools and, on ``tools/call``, echoes back the tool NAME
it actually received (so a test can prove the hub rewrote a collision-renamed
name back to its original before forwarding) plus the arguments.
"""

from __future__ import annotations

import json
import sys


def _out(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "fake"
    tools = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else []
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw.startswith("{"):
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        method = msg.get("method")
        mid = msg.get("id")
        if method == "initialize":
            _out(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": name, "version": "1"},
                    },
                }
            )
        elif method == "tools/list":
            _out(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "tools": [
                            {
                                "name": t,
                                "description": f"{name} {t}",
                                "inputSchema": {"type": "object", "properties": {}},
                            }
                            for t in tools
                        ]
                    },
                }
            )
        elif method == "tools/call":
            params = msg.get("params") or {}
            _out(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {
                                        "backend": name,
                                        "received_name": params.get("name"),
                                        "arguments": params.get("arguments"),
                                    }
                                ),
                            }
                        ]
                    },
                }
            )
        elif method and method.startswith("notifications/"):
            continue
        elif mid is not None:
            _out(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "error": {"code": -32601, "message": "unsupported"},
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
