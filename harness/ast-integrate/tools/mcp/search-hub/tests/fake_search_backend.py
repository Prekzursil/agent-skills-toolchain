#!/usr/bin/env python3
"""Minimal MCP stdio backend for the search-hub integration tests.

Usage: ``python fake_search_backend.py <backend_id> <tool_name> <key_env>``

It reads its bound API key from ``os.environ[<key_env>]`` (the hub injects the
active/selected key's env at spawn) and, on ``tools/call``, SIMULATES the real
providers' failure modes so rotation can be exercised without live keys:

* key value contains ``exhaust`` -> an ``isError`` result carrying a hard
  HTTP-402 ``NO_MORE_CREDITS`` / "Insufficient credits" message.
* key value contains ``ratelimit`` -> an ``isError`` 429 with ``Retry-After: 30``.
* otherwise -> echoes the backend id, the tool NAME it received, and the key
  value it was spawned with (so a test can prove WHICH key served the call).
"""

from __future__ import annotations

import json
import os
import sys


def _out(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _error_text(key_value: str) -> str | None:
    low = key_value.lower()
    if "exhaust" in low:
        return "HTTP 402 Payment Required: NO_MORE_CREDITS - Insufficient credits"
    if "ratelimit" in low:
        return "HTTP 429 Too Many Requests: rate limit exceeded, Retry-After: 30"
    return None


def _call_result(backend: str, params: dict, key_value: str) -> dict:
    err = _error_text(key_value)
    if err is not None:
        return {"content": [{"type": "text", "text": err}], "isError": True}
    payload = {
        "backend": backend,
        "received_name": params.get("name"),
        "key_value": key_value,
        "arguments": params.get("arguments"),
    }
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


def main() -> int:
    backend = sys.argv[1] if len(sys.argv) > 1 else "fake"
    tool = sys.argv[2] if len(sys.argv) > 2 else "fake_tool"
    key_env = sys.argv[3] if len(sys.argv) > 3 else "FAKE_KEY"
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
                        "serverInfo": {"name": backend, "version": "1"},
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
                                "name": tool,
                                "description": f"{backend} {tool}",
                                "inputSchema": {"type": "object", "properties": {}},
                            }
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
                    "result": _call_result(
                        backend, params, os.environ.get(key_env, "")
                    ),
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
