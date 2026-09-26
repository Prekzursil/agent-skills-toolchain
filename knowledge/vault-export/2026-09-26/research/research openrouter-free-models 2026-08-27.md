---
title: research openrouter-free-models 2026-08-27
type: report
permalink: main/research/research-openrouter-free-models-2026-08-27
tags:
- research-report
- High
- firecrawl
- context7
- openrouter-api
---

# OpenRouter free / $0 models for sidecar smoke: Research Report
*Generated: 2026-08-27 | Sources: 16 | Providers: firecrawl, context7, live OpenRouter API, web | Confidence: High*
*Cache: 0 hits / 12 misses | Stale-allowed: no*

## Executive Summary

OpenRouter still publishes a live catalog of zero-price models. A GET /api/v1/models call on 2026-08-27 returned 417 models, of which 20 have pricing.prompt and pricing.completion of 0 (17 :free chat variants, the openrouter/free router, and two Lyria audio previews). Official docs say a negative account balance may 402 even free models. On this account, that did not happen at the current slight overdraft: two free completions returned HTTP 200 with later GET /generation total_cost=0, while paid deepseek/deepseek-v4-flash-0731 had already 402'd. Wave 0 cheap smoke is therefore PASS via the free path. Paid 3-model bake-off stays skipped until credits exist. Do not treat random :free slugs as agentic-coding models.

Disk copy: C:\\Users\\Prekzursil\\.agents\\skills\\openrouter-routing\\openrouter-free-models_2026-08-27.md

## Live smoke 2026-08-27

- liquid/lfm-2.5-2.6b:free HTTP 200, gen-1787793797-2WelxSMIM1z6ZjFYfWFv, total_cost=0 (Liquid)
- openrouter/free HTTP 200, resolved nvidia/nemotron-3.5-lightning:free, gen-1787793804-F2TQPdT2frdTAk6BC3FR, total_cost=0 (Nvidia)
- google/gemma-4-26b-a4b-it:free HTTP 429 upstream, not 402

## T0 routing

- Test slug while paid 402: liquid/lfm-2.5-2.6b:free (allowlist; not for agentic coding)
- Paid cheap when credits exist: deepseek/deepseek-v4-flash-0731 plus :floor
- deep-research: T0 summarization of already-fetched sources MAY use sidecar; web/deep_read stay on MCP. :online deprecated.
- gem-hunt: no OpenRouter MCP, LiteLLM, Cursor BYOK, LangGraph, vector-DB, Sentry duplicate, trained critic.

## Limits

:free = 20 RPM; 50 RPD if lifetime purchases under $10 else 1000 RPD. This key is_free_tier=false, limit=null. GET /credits needs management key (absent).

## Key takeaways

- Wave 0 cheap smoke PASS on the free path.
- Paid bake-off skipped until credits.
- Official docs still warn negative balance MAY 402 free models; this slight overdraft did not.
- Remaining user clicks: add credits; set per-key Limit + Daily reset.
