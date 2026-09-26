---
title: research openrouter-complete-surface 2026-08-27
type: report
permalink: main/research/research-openrouter-complete-surface-2026-08-27
tags:
- research-report
- High
- firecrawl
- openrouter
- '2026-08-27'
---

# OpenRouter complete product surface vs this harness
*Generated: 27.08.2026 | Sources: 38 | Confidence: High*

Wave 1 sidecar (env key, T0 chat script, Codex named Responses provider, generation ids) is the correct slice. OpenAPI has 77 paths / 101 operations plus Batch `/api/beta/batches` and official MCP at mcp.openrouter.ai — most extras SKIP. Live: key limit=null; credits 319.4 vs usage ~319.79 (overdrawn); 417 models; 17 :free suffixes; 348 tool-capable; 33 embeddings models; 103 providers.

Does **not** contradict Wave 1. Soft gaps: `:floor` also admits flex tiers; T0 pin 0731 is 2× `~deepseek/deepseek-v4-flash-latest`; Codex cookbook wants default provider (we correctly refused).

## Top unused-but-valuable
1. Batch API ~50% (`POST /api/beta/batches`) — not in OpenAPI v1
2. Embeddings + rerank (33 models, separate catalog)
3. `session_id` / prompt-cache sticky routing
4. Server tool `openrouter:web_search` (not `:online`)
5. `:floor` flex-tier admission (skill understates)
6. Response-healing + structured outputs for T0 schema
7. Activity CSV / `GET /credits` in the T0 script
8. Cheaper live flash alias `$0.03/$0.075`
9. Auto Router with allowlist + `cost_tier=low`
10. `provider.zdr` / `data_collection=deny` if handling secrets

## Confirmed SKIP
Official MCP (Codex provider + CLI already exist); Cursor `/api/v1/cursor` BYOK; Claude `ANTHROPIC_BASE_URL`; LiteLLM; extra IDEs (Cline/Open WebUI/etc.); management keys from agents; `models[]` hidden uptier; hosted fine-tune (does not exist); SCIM/observability.

## User clicks
Top-up credits; set per-key Limit daily XOR monthly. Do not paste key into Cursor. Do not add MCP.

Full cited report: `C:\\Users\\Prekzursil\\.agents\\skills\\openrouter-routing\\openrouter-complete-surface_2026-08-27.md`

## Wave 1
Default Codex model remains gpt-5.6-sol. Profile openrouter is opt-in. No MCP/BYOK/LiteLLM/Claude base URL.

DOWN providers this run: Context7 query-docs, Exa, Tavily, Searxng, Perplexity, user-basic-memory. Firecrawl intermittent. Status.openrouter.ai: All Systems Operational.
