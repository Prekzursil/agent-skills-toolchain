---
title: burp-mcp-always-on-hardening-mcp-health-fixes-2026-09-19
type: note
permalink: main/burp-mcp-always-on-hardening-mcp-health-fixes-2026-09-19
---


- [fact] (later same day) CyberStrike dashboard showed burp/dbx-ai failed+disabled: burp was stale runtime state from the kill-test window (config enabled:true, SSE verified; CyberStrike bundles official MCP SDK SSE client — compatible with root-path SSE; fix = toggle/reconnect or restart TUI). dbx-ai had been PRUNED by the SSOT reconciler (non-front stdio key). Fixed properly: dbx-ai is now a supervised loopback front `http://127.0.0.1:31120/mcp` (FastMCP 4.0.5 in pinned venv .venv-dbxaifront → stdio server), lib catalog Band Full, SSOT fronts.dbx-ai + specialized, watchdog deep-probes 31101/31120. System fastmcp 3.4.2 and pipx mcp-proxy are import-broken vs current mcp pkg — use pinned-venv pattern for bridges.