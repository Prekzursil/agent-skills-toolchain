---
title: cyberstrike-full-estate-mcp-34-fronts-2026-09-19
type: decision
permalink: main/decisions/cyberstrike-full-estate-mcp-34-fronts-2026-09-19
tags:
- cyberstrike
- mcp
- ssot
- estate
- ops
---

# CyberStrike full-estate MCP mandate — 34 always-on fronts (2026-09-19)

- [decision] CyberStrike TUI keeps ALL MCPs enabled + functional always (owner mandate 2026-09-19). 34 servers wired: 12 legacy fronts + burp(:9876) + dbx-ai(:31120) + 20 new fronts on 31121-31140 (angr frida mitmproxy radare2 windbg caldera havoc mythic jb-library darknet dns-security mcp-scanner satellite steganography supply-chain hackbrowser ghidra-mcp ida-pro-mcp jadx-mcp binary-ninja-mcp).
- [fact] Root cause of "missing" servers: reconcile-cyberstrike-mcp-config.py pruned non-SPECIALIZED keys (line ~92) — 20 local/stdio entries deleted when SSOT was applied 17:1x. Fixed by registering all 20 as SSOT fronts; both reconcilers now emit enabled=True for CyberStrike (specialized emitter hard-codes True; cs reconciler default profile 'all').
- [fact] node.exe children die silently when spawned by node-under-supervisor (mcp-proxy wrap); FIX = fastmcm-front pattern (json + cmd + .venv-dbxaifront python spawning node) for the six bundled node servers. Also: Start-Process ArgumentList elements must be space-free (C:\nodejs junction created); empty Args must be explicit @().
- [fact] hexstrike-ai deep-probe dead-child (long-standing) FIXED by new RepairFront behavior: port-bound-but-child-dead now stops by Match '--port N' only and respawns (ExtraMatch kills would hit TUI's own npx built-ins — never use).
- [fact] satellite deep_front_probe can false-negative while its fastmcm child cold-boots; full handshake (initialize→tools/list) is definitive. All 34 verified functional 2026-09-19 ~19:30 (burp 27 tools, sliver-full 74, hexstrike nmap_scan, satellite Sentinel-2, etc.).
- [fact] Fronts get per-front logs now (logs/front-<name>.err/.out.log) via Start-Process redirect patch in start-cyberstrike-mcp-http.ps1.

Related: [[main/decisions/burp-mcp-always-on-hardening-mcp-health-fixes-2026-09-19]]
