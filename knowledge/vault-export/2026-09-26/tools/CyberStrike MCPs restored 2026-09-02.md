---
title: CyberStrike MCPs restored 2026-09-02
type: note
permalink: main/tools/cyber-strike-mcps-restored-2026-09-02
tags:
- cyberstrike
- metasploit
- sliver
- mcp
---

- [decision] CyberStrike MCP map restored 02.09.2026: hexstrike-ai, cve, github-security, osint, sliver, sliver-full, metasploit — all seven `cyberstrike mcp list` connected.
- [decision] Metasploit dangerous actions stay ENABLED (`--enable-dangerous-actions` + `MSF_MCP_DANGEROUS_ACTIONS=true` + `mcp.dangerous_actions: true` in `D:/opt/metasploit/mcp_config.yaml`). Owner asked to keep them.
- [fact] Official Windows Framework is 6.5.3-20260826060514 at `D:/metasploit-framework` (MSI FastUnzip ignored INSTALLDIR; lives on D: not C:). Wrapper `D:/metasploit-framework/bin/msfmcpd.bat` plus stdio launcher `D:/opt/metasploit/msfmcpd-stdio.cmd`.
- [fact] Rapid7 `msfrpcd -S` **disables** SSL (flag name inverted). Live loopback RPC is 127.0.0.1:55553 plaintext; MCP yaml `ssl: false`. Do not assume -S means enable.
- [fact] Sliver v1.7.6 FULL re-grabbed to `D:/opt/sliver` (server 339883008 + client 60745216) with junction `~/.local/opt/sliver`. Operator `cyberstrike` loopback 127.0.0.1:31337. Daemon kept alive by user scheduled task `SliverLoopbackDaemon` because agent Job Objects kill Start-Process children.
- [fact] CVE/OSINT/GitHub-security pinned under `D:/opt/cs-mcp` (no `npx -y` cold start). Launchers `cve-mcp.cmd`, `github-security-mcp.cmd`, `osint-mcp-server.cmd`.
- [fact] TUI at 127.0.0.1:4096 may not hot-reload json; space-toggle or restart CyberStrike after this write.
- [fact] MSF RPC user is `msf`; password in User env `MSF_API_PASSWORD`. `msfrpcd -P` puts the secret on the process command line (Windows Rapid7 limitation). Local blast radius only; do not rotate.
- [decision] No internet-facing Sliver/MSF listeners. Loopback only. No third-party implants generated.

Related: [[cyber-strike-hex-strike-full-and-sliver-mcp-2026-09-02]] [[cyber-strike-ai-providers-2026-09-02]]