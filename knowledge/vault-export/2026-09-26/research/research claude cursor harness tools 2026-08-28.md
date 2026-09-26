---
title: research claude cursor harness tools 2026-08-28
type: report
permalink: main/research/research-claude-cursor-harness-tools-2026-08-28
status: active
valid_as_of: '2026-08-28'
tags:
- research-report
- High
- firecrawl
- context7
---

# research claude cursor harness tools 2026-08-28

- [decision] auth2api as ANTHROPIC_BASE_URL cannot drive Claude Code's Read/Bash/MCP tool loop; Cursor's chat backend is an agent frame (ask_question), not a raw tool-calling API.
- [fact] Live probe 28.08.2026 POST http://127.0.0.1:8317/v1/messages model claude-sonnet-5 with client tool get_weather → stop_reason tool_use but name=ask_question; model text said no get_weather.
- [fact] Cursor staff (deanrie Jul/Aug 2026) say unofficial proxies to private client endpoints violate ToS; CLI/SDK/Cloud Agents always run Cursor harness; no public /v1/chat/completions.
- [fact] LiteLLM-class Anthropic gateways DO keep Claude Code tools if they preserve tool_use/tool_result; ENABLE_TOOL_SEARCH is a context knob, not the Cursor fix.
- [fact] cursor2api "tools" are prompt-injection against the docs-page /api/chat API, not StreamUnifiedChatWithTools; G-5 fence: do not copy that shim onto :8317.
- [requirement] To keep Claude harness + spend Cursor quota: native claude + cursor-agent as MCP (G-36 one cursor-agent). To get Cursor models with an agent loop: cursor-agent / agent acp, not claude-cursor.
- relates_to [[estate-locks-2026-08-27]]
See also [[Cursor RAM vs Claude Grok CLI — measured 2026-08-28]]
Full report: C:\\Users\\Prekzursil\\Cowork\\output\\research-claude-cursor-harness-tools_2026-08-28.md

## Executive Summary
Claude Code's agent loop is client-side. Cursor does not expose a raw Anthropic model API. Live probe on this box confirmed ask_question-only tool_use. Invert architecture (Claude host + Cursor MCP) is the path that preserves hooks/memory/tools.

## Sources
1. https://forum.cursor.com/t/using-cursor-frontier-models-like-composer-2-5-in-external-harnesses-e-g-codex/164676
2. https://cursor.com/docs/cli/acp
3. https://code.claude.com/docs/en/llm-gateway-protocol
4. Cowork/output/cli-bridges-windows_2026-08-25.md
5. Live :8317 probe 2026-08-28