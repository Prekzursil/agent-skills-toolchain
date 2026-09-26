---
title: research leftover gems 2026-08-27
type: report
permalink: main/research/research-leftover-gems-2026-08-27
tags:
- research-report
- Medium
- firecrawl
- context7
- websearch
---

# Leftover UNLOCKED gems after 26.08.2026 locks: Research Report
*Generated: 27.08.2026 | Sources: 28 | Providers: firecrawl, context7, websearch/webfetch, basic-memory (recall) | Confidence: Medium*
*Cache: 0 hits / ~18 misses | Stale-allowed: no*
*File:* `C:\\Users\\Prekzursil\\Cowork\\output\\research-leftover-gems_2026-08-27.md`
*Cited baseline:* grill-100-gem-stack_2026-08-26.md

## Executive Summary

After G3-D (6 enabled MCP) and Goose → `:8317`, leftover **G-4** is stay-on-6 vs a multiplexer that **moves** servers out of mcp.json. Token-filter (mcp-funnel) ≠ RAM cut: still starts upstream stdio; default daemon is Unix socket `~/.mcp-funnel.sock`; Windows unverified. **McpHub** is the only vendor that documents on-demand spawn + idleTimeout 300s + Windows binary + SSE `:24680`. **mcpproxy-go** has the Windows installer (`mcpproxy-setup-*-amd64.exe`, tray, `:8080`) but lazy-start is UNVERIFIED (do not confuse with philschmid mcp-cli). mcp-funnel is the wrong tool for this box's RAM job.

Cursor `/multitask` = Agents Window (changelog 24.04.2026), Cursor-quota async subagents. Claude Code Dynamic Workflows = different product (JS harness, workflowSizeGuideline, Anthropic quota). `claude` in Cursor terminal ≠ `/multitask`.

Cursor-quota coding is already locked: Goose → `:8317`. `cursor-agent -p` reuses editor MCP. Aider is no-MCP git CLI (C-phase; auto-commit by default).

Memory: do not replace basic-memory `:8765`. ByteRover Skill ADD maybe; LynxMCP default `:8765` landmine; Mem0 SKIP replace. seshport Windows MSVC binary exists; Cursor chats out of scope; casr/seshport not found. NordPass-as-1P-mirror: official 1PUX/CSV after 1P is SSOT.

## G-4 decision table

| Option | Tokens | RAM / lazy-start | Windows | vs G3-D |
|---|---|---|---|---|
| 4A Stay on 6 | schemas of the 6 | no extra daemon | n/a | week-1 done |
| 4B mcp-funnel replace | strong filter | upstream stdio still start; UDS | unverified | SKIP unless measured drop |
| 4C managed-mcp.json | n/a | wrong container | n/a | LOCKED SKIP |
| 4D HTTP mux later | McpHub 2-tool / mcpproxy retrieve | McpHub claims idle-kill; mcpproxy lazy UNVERIFIED | both ship Win binaries | MOVE only, RAM ≥ ~8 GB, not this week |

Success test = node/python count drop on fresh Cursor start, not a token screenshot. Adding a mux **beside** the 6 undoes G3-D. Port `:24680` does not collide with `:8765`/`:8812`/`:8317`. `:8080` occupancy NOT-CHECKED.

Gates if 4A: search-hub Claude-only; Codex 4/40 as-is; Composio SKIP; RE stdio stay in the 31.

If 4D bake-off: McpHub for documented idle-kill; mcpproxy-go for Windows packaging; measure idle RSS of upstreams.

## Other leftover gems (post-G-4 / C-phase)

- Dynamic Workflows: v2.1.154+, guideline small&lt;5 / medium&lt;15 (default v2.1.219, advice not a cap). Compatible with 4A if run in Claude CLI.
- `/multitask` local = Cursor quota + MCP-clone risk; cloud Agents Window moves RAM off-box.
- Aider: no MCP flags in official options; `--no-auto-commits` for house git rule.
- ByteRover: Skill default; never MCP on this box if ADD.
- LynxMCP: `lynx manager ui --port 8765` — never bind 8765.
- seshport: Harshil-Jani; Windows `seshport-x86_64-pc-windows-msvc.exe.gz` v0.3.0; claude|codex|grok only.
- NordPass: 1P export 1PUX/CSV → NordPass import official; reverse CSV lossy.

## Methodology
Firecrawl LIVE (not 402, creditsUsed 2). Context7 LIVE. WebSearch/WebFetch LIVE. Exa/Tavily/Perplexity/SearxNG absent. Sci-Hub excluded. Sequential/≤3 fetches. Full citations in the Cowork file.
