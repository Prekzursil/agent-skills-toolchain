#!/usr/bin/env python3
"""Known-connected MCP stdio fixture for AUD-0060.

Exactly three tools with stable names. A zero count against this process means
the enumerator is not reaching a server that is actually connected.
"""
from __future__ import annotations

import json
import sys

TOOLS = [
    {
        "name": "aud0060_fixture_alpha",
        "description": (
            "AUD-0060 control tool alpha. Enumerator reachability marker. "
            "Not part of the live estate; spawned only by this unit's probes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "needle": {
                    "type": "string",
                    "description": "Search needle used only in the control fixture.",
                }
            },
            "required": ["needle"],
        },
    },
    {
        "name": "aud0060_fixture_beta",
        "description": (
            "AUD-0060 control tool beta. Distinct schema so serialized size "
            "is not identical across the three-tool control surface."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 99},
                "include_closed": {"type": "boolean"},
            },
        },
    },
    {
        "name": "aud0060_fixture_gamma",
        "description": (
            "AUD-0060 control tool gamma. Planted as UNUSED in the usage-trace "
            "control: mentions of this name in prose must not count as invocations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "recursive": {"type": "boolean"},
                "glob": {"type": "string"},
            },
            "required": ["path"],
        },
    },
]

EXPECTED_NAMES = [t["name"] for t in TOOLS]
EXPECTED_COUNT = len(TOOLS)


def _read() -> dict | None:
    header = b""
    stdin = sys.stdin.buffer
    while b"\r\n\r\n" not in header and b"\n\n" not in header:
        chunk = stdin.read(1)
        if not chunk:
            return None
        header += chunk
        if len(header) > 65536:
            return None
    if b"\r\n\r\n" in header:
        head, rest = header.split(b"\r\n\r\n", 1)
        sep_len = 4
    else:
        head, rest = header.split(b"\n\n", 1)
        sep_len = 2
    length = None
    for line in head.split(b"\n"):
        line = line.strip(b"\r")
        if line.lower().startswith(b"content-length:"):
            try:
                length = int(line.split(b":", 1)[1].strip())
            except ValueError:
                return None
    if length is None:
        return None
    body = rest
    # sep consumed; rest may already hold part of body
    _ = sep_len
    while len(body) < length:
        more = stdin.read(length - len(body))
        if not more:
            return None
        body += more
    try:
        return json.loads(body[:length].decode("utf-8"))
    except json.JSONDecodeError:
        return None


def _write(msg: dict) -> None:
    raw = json.dumps(msg, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw)
    sys.stdout.buffer.flush()


def main() -> int:
    while True:
        msg = _read()
        if msg is None:
            return 0
        method = msg.get("method")
        mid = msg.get("id")
        if method == "initialize":
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "aud-0060-fixture", "version": "1"},
                    },
                }
            )
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            _write({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
        elif method == "ping":
            _write({"jsonrpc": "2.0", "id": mid, "result": {}})
        elif mid is not None:
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "error": {"code": -32601, "message": f"unknown method {method}"},
                }
            )


if __name__ == "__main__":
    raise SystemExit(main())
