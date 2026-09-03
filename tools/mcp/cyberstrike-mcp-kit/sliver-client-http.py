#!/usr/bin/env python3
"""Loopback Streamable-HTTP front for official `sliver-client mcp` (stdio).

Uses mcp.client.stdio + FastMCP-less ASGI Streamable HTTP from the SDK already
in the sliver-mcp venv. Binds 127.0.0.1:31380/mcp.
"""
from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager

HOST = os.environ.get("SLIVER_CLIENT_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("SLIVER_CLIENT_MCP_PORT", "31380"))
CFG = os.environ.get(
    "SLIVER_OPERATOR_CONFIG",
    r"C:\Users\Prekzursil\.local\opt\sliver\operators\cyberstrike_127.0.0.1.cfg",
)
CLIENT = os.environ.get(
    "SLIVER_CLIENT_EXE",
    r"C:\Users\Prekzursil\.local\opt\sliver\sliver-client.exe",
)

if HOST not in ("127.0.0.1", "localhost", "::1"):
    sys.stderr.write("sliver-client-http: host must be loopback\n")
    sys.exit(2)
if not os.path.isfile(CFG) or not os.path.isfile(CLIENT):
    sys.stderr.write("sliver-client-http: missing client exe or operator config\n")
    sys.exit(2)


def main() -> None:
    sys.stderr.write(
        "sliver-client-http.py is unused; launch sliver-client-mcp-http.cmd "
        "(node mcp-proxy on 127.0.0.1:31380).\n"
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
