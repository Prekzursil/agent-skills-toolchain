---
title: CyberStrike Sliver HTTP MCP 2026-09-03
type: note
permalink: main/tools/cyber-strike-sliver-http-mcp-2026-09-03
tags:
- decision
- fact
- cyberstrike
- sliver
---

# CyberStrike Sliver HTTP MCP 2026-09-03

- [decision] G-7 A: keep Sliver in the default CS session, but front both MCPs as loopback Streamable HTTP so the TUI does not spawn stdio children.
- [fact] Official `sliver` MCP: `http://127.0.0.1:31380/mcp` via pinned `mcp-proxy@6.7.11` at `D:\\opt\\cs-mcp\\node_modules\\mcp-proxy`. MUST pass `--host 127.0.0.1` (package default is `::`). Task `SliverClientMcpHttp`.
- [fact] Complementary `sliver-full` MCP: `http://127.0.0.1:31381/mcp` via FastMCP `transport=streamable-http` (`D:\\opt\\cs-mcp\\sliver-full-http.py`) in the sliver-mcp 0.2.4 venv (mcp 1.29.1 + uvicorn). Task `SliverFullMcpHttp`.
- [fact] `SliverLoopbackDaemon` (`127.0.0.1:31337`) kept. Initialize POST 200: serverInfo Sliver MCP v1.7.6 and sliver-mcp 1.29.1. `cyberstrike mcp list` shows both connected as remote URLs.
- [fact] RAM: one resident sliver-client + one python HTTP + one node proxy, shared across CS sessions. Not zero RAM — no per-TUI fork.

Related: [[CyberStrike global aggressive agent prompt 2026-09-03]] [[CyberStrike HexStrike full and Sliver MCP 2026-09-02]]