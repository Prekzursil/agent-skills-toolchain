#!/usr/bin/env python3
"""A deliberately-broken MCP backend: it exits immediately without speaking the
protocol, so the hub's lazy-spawn handshake fails and must degrade gracefully
(a clear per-tool error) rather than crash the whole server."""

import sys

sys.exit(1)
