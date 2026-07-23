#!/usr/bin/env python3
"""Ad-hoc smoke: drive a REAL stdio MCP command through StdioChild and print
its serverInfo + tools count. Proves the wrapped child speaks MCP; the HTTP
host is the same StdioChild behind an HTTP endpoint.

    python smoke_stdio.py C:\\Python314\\python.exe path\\to\\hub.py
"""

from __future__ import annotations

import json
import sys

from mcp_http_host import StdioChild


def main() -> int:
    cmd = sys.argv[1:]
    if not cmd:
        print("usage: smoke_stdio.py <command...>", file=sys.stderr)
        return 2
    child = StdioChild(cmd)
    try:
        init = child.request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke", "version": "0"},
                },
            },
            timeout=45,
        )
        server_info = (init or {}).get("result", {}).get("serverInfo", init)
        print("INIT_SERVERINFO:", json.dumps(server_info))
        print("CHILD_PID:", child.pid)
        tools = child.request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, timeout=45
        )
        tool_list = (tools or {}).get("result", {}).get("tools", [])
        print("TOOLS_COUNT:", len(tool_list))
    finally:
        child.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
