---
title: CyberStrike MCP fleet rebuilt on McpHub self-healing aggregation 2026-09-03
type: decision
permalink: main/decisions/cyber-strike-mcp-fleet-rebuilt-on-mcp-hub-self-healing-aggregation-2026-09-03
tags:
- cyberstrike
- mcp
- mcphub
- architecture
- self-heal
- zcode
---

## Observations
- [decision] CyberStrike MCP fleet serving architecture REBUILT on McpHub (2026-09-03, owner-directed deep-research): the old detached mcp-proxy fleet (12 SSE fronts on :31410-19 + hexstrike, spawned by start-cyberstrike-mcp-http.ps1, no supervision) produced the zombie sprawl and died silently; naive restart would have restored the old problem. Chosen: McpHub v5.0.0 aggregation hub at http://127.0.0.1:24680/sse (Bearer token in ~/.McpHub/auth-token), mode=discover + idleTimeout=300 + autoRestart — lazy spawn, idle reaping, 11 MB resident with 65 configured servers. #cyberstrike #mcp
- [fact] McpHub supervisor (~/.local/opt/mcphub/mcphub-supervisor.ps1, the proven agent-mail/basic-memory self-heal pattern) now ALSO keeps sliver-full :31381 alive. TUI config (~/.config/cyberstrike/cyberstrike.json) reduced from 13 per-server fronts to 3 entries: mcphub (aggregated, token header), sliver-full (direct), basic-memory (direct). sliver (client) folded into the hub as a stdio entry. #cyberstrike
- [fact] ZCode mcphub entry flipped from cmd/npx-with-inline-token to native url + bearer_token_env_var=MCPHUB_TOKEN (User env var set) — token no longer sits in a config file. #zcode
- [fact] LESSON (process-audit): dead PPID does not imply orphan when a launcher deliberately detaches (the cs-mcp fleet launcher exits after spawning). Before killing "orphans", also check whether the process is serving a listening port. The 03.09 morning fleet kill took down the live CyberStrike TUI's 12 MCPs — restored via the McpHub consolidation above. #lesson #mcp
- [fact] cyberstrike-harness-bridge (repo tools/mcp/) evaluated and NOT chosen for live serving: no runtime entrypoint yet (inventory/test/verify scripts only); it remains the strategic gateway direction (harness_invoke, no resident children) for when it matures. #cyberstrike

## Relations
- relates_to [[ZCode SSOT integration + cyberstrike rename + bm-capture fix + space reclaim 2026-09-03]]
