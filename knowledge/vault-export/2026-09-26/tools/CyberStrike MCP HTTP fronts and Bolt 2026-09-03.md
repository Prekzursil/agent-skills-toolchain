---
title: CyberStrike MCP HTTP fronts and Bolt 2026-09-03
type: note
permalink: main/tools/cyber-strike-mcp-http-fronts-and-bolt-2026-09-03
tags:
- cyberstrike
- mcp
- bolt
- http
---

- [decision] Remaining CyberStrike stdio MCPs are now loopback Streamable HTTP via mcp-proxy (G-7 pattern). CS json has **zero** `type: local` entries. Search-hub / Tavily / Exa / onions stay on Grok only — not in CS.
- [fact] `cyberstrike mcp list` 03.09.2026: **10/10 connected** as remotes — github-security `:31410`, cve `:31411`, osint `:31412`, hexstrike-ai `:31413`, sliver `:31380`, sliver-full `:31381`, firecrawl `:31414`, basic-memory `:8765`, hacktricks `:31415`, metasploit `:31416`. Each initialize HTTP 200.
- [fact] Supervisor scheduled task `CsMcpHttpFronts` (AtLogOn) runs `D:\opt\cs-mcp\start-cs-mcp-http.ps1`. Search-hub was removed from that supervisor so CS cannot spawn it.
- [fact] Backup: `~/.config/cyberstrike/cyberstrike.json.bak-2026-09-03-http-mcp`.
- [decision] G-3 B Bolt deployed loopback-only: digest `ghcr.io/cyberstrikeus/bolt@sha256:90ef2d10a8e255369981e7ce2eb7b89e1ac337ad6a5cf9f21f803c8585eea277`, container `bolt-lab` `127.0.0.1:3001`, `/health` 200, CS `bolt.bolt-lab` url+timeout 900000. Token in `D:\opt\bolt\admin.token` (never print). Pairing still needs owner `/bolt` after `cyberstrike-engage` because API `:4096` was down (no live TUI).
- [fact] Live TUI does not hot-reload json. Owner must restart from `cyberstrike-engage` to drop old stdio children and pick HTTP remotes + Bolt URL.

[[CyberStrike Sliver HTTP MCP 2026-09-03]] [[Grok PR 310 search-hub live 2026-09-03]]