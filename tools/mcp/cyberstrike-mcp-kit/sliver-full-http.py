#!/usr/bin/env python3
"""Loopback Streamable-HTTP front for sliver-mcp (FastMCP 1.29).

Binds 127.0.0.1:31381/mcp so CyberStrike can use type=remote instead of a
per-session stdio child. Operator config via SLIVER_OPERATOR_CONFIG.
"""
from __future__ import annotations

import os
import sys

HOST = os.environ.get("SLIVER_FULL_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("SLIVER_FULL_MCP_PORT", "31381"))
CFG = os.environ.get(
    "SLIVER_OPERATOR_CONFIG",
    r"C:\Users\Prekzursil\.local\opt\sliver\operators\cyberstrike_127.0.0.1.cfg",
)

if HOST not in ("127.0.0.1", "localhost", "::1"):
    sys.stderr.write("sliver-full-http: host must be loopback\n")
    sys.exit(2)

# Import after we know the bind; then override FastMCP settings (ctor kwargs
# beat FASTMCP_* env, so we patch the already-built instance).
from sliver_mcp import server as sliver_server  # noqa: E402

if not os.path.isfile(CFG):
    sys.stderr.write(f"sliver-full-http: missing operator config: {CFG}\n")
    sys.exit(2)

sliver_server._CONFIG_PATH = CFG
sliver_server.mcp.settings.host = HOST
sliver_server.mcp.settings.port = PORT
sliver_server.mcp.settings.streamable_http_path = "/mcp"
sliver_server.mcp.run(transport="streamable-http")
