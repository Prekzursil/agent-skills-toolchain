# OpenRouter free / $0 models for sidecar smoke: Research Report
*Generated: 2026-08-27 | Sources: 16 | Providers: firecrawl, context7, live OpenRouter API, web | Confidence: High*
*Cache: 0 hits / 12 misses | Stale-allowed: no*

## Executive Summary

OpenRouter still publishes a live catalog of zero-price models. A `GET /api/v1/models` call on 2026-08-27 returned **417** models, of which **20** have `pricing.prompt` and `pricing.completion` of `0` (17 `:free` chat variants, the `openrouter/free` router, and two Lyria audio previews). Official docs say a **negative account balance may 402 even free models** `[1][14]`. On this account, that did **not** happen at the current slight overdraft: two free completions returned HTTP **200** with later `GET /generation` `total_cost=0`, while paid `deepseek/deepseek-v4-flash-0731` had already 402'd. Wave 0 cheap smoke is therefore **PASS via the free path**. Paid 3-model bake-off stays skipped until credits exist. Do not treat random `:free` slugs as agentic-coding models.

## 1. Which models are free / $0, and what are the limits?

**Catalog (live API, 2026-08-27).** Authenticated `GET https://openrouter.ai/api/v1/models` (inference key present by name only) returned HTTP 200 and 417 rows. Filter: id ends with `:free` **or** both prompt and completion prices parse as 0. `[7][5]`

`:free` chat slugs (all `zero_price=true`, tools unless noted):

| Slug | Context | Tools in `supported_parameters` |
| --- | --- | --- |
| `cohere/north-mini-code:free` | 256000 | yes |
| `dots-studio/dots-3-note-preview:free` | 512000 | yes |
| `google/gemma-4-26b-a4b-it:free` | 262144 | yes |
| `google/gemma-4-31b-it:free` | 262144 | yes |
| `liquid/lfm-2.5-2.6b:free` | 65536 | yes |
| `minimax/minimax-m2.7:free` | 196608 | yes |
| `minimax/minimax-m3:free` | 1048576 | yes |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | 256000 | yes |
| `nvidia/nemotron-3-super-120b-a12b:free` | 262144 | yes |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 1000000 | yes |
| `nvidia/nemotron-3.5-content-safety:free` | 128000 | **no** (classifier) |
| `nvidia/nemotron-3.5-lightning:free` | 1000000 | yes |
| `poolside/laguna-s-2.1:free` | 262144 | yes |
| `poolside/laguna-xs-2.1:free` | 262144 | yes |
| `thinkingmachines/inkling-small:free` | 1048576 | yes |
| `thinkingmachines/inkling:free` | 1048576 | yes |
| `z-ai/glm-5.2:free` | 256000 | yes |

Zero-price **without** `:free` suffix:

- `openrouter/free` — Free Models Router; tools=yes; ctx 200000. `[6][11][7]`
- `google/lyria-3-clip-preview` and `google/lyria-3-pro-preview` — audio generation previews, not chat T0. `[7]`

The public collection page lists additional **embedding/rerank** free models (`nvidia/nemotron-3-embed-1b:free`, `nvidia/llama-nemotron-rerank-vl-1b-v2:free`) that did not appear in this `/models` chat list. `[11]` Do not use them for sidecar chat smoke.

**Rate limits (official, corroborated).** IDs ending in `:free`: **20 requests/minute**; **50 requests/day** if lifetime credit purchases are under **$10**, else **1000/day**. Extra keys do not raise the global cap. Paid variants have no platform request cap. 429 vs 402 are different errors. `[1][2][12][14]`

This inference key: `GET /api/v1/key` HTTP 200, `is_free_tier=false` (credits have been purchased before, so the 1000 RPD tier applies), `limit=null`, `limit_reset=null`, `limit_remaining=null`, this-key `usage=0`. Per-key daily Limit is still **NOT-CHECKED** until a dashboard click. `[8][1]`

**Data-use.** Account privacy has **separate** free vs paid training toggles. Providers that may train (examples on the official logging page: DeepSeek, Liquid, NVIDIA, Stealth, Thinking Machines) are skipped only if the matching toggle is off. `[4][2]` Poolside's free collection blurbs state that **free** Laguna traffic may be used to train. `[11]` Liquid's collection blurb says prompts/outputs may be retained and used to train, and advises against agentic coding. `[11]` Free T0 is not a secrets channel.

**Tool calling / reliability.** Most `:free` chat slugs advertise `tools` in `supported_parameters`. `[7]` That is a catalog flag, not a reliability guarantee. Official `:free` docs only promise different rate limits and availability versus paid. `[3]` The `openrouter/free` router picks a random eligible free model (image / tools / structured outputs filters). `[6][11]` Do **not** use a random `:free` slug, or `openrouter/free`, for agentic coding. `[3][11]`

**`:online`.** Deprecated. Use `openrouter:web_search` on OpenRouter itself; this workspace must **not** replace Firecrawl/Exa/native Max with that tool. `[2][5]`

## 2. Do free models work when the paid balance is slightly negative?

**Official (may 402).** Credit limits are account balance plus optional per-key caps. Exceeding them is HTTP **402**. Quote: if the account has a **negative credit balance**, you **may** see 402 errors, **including for free models**; adding credits to put the balance above zero restores them. `[1]` Secondary write-ups repeat that a negative balance can 402 free traffic. `[14][15]`

**Live (this account, 2026-08-27).** Prior paid smoke: `POST` `deepseek/deepseek-v4-flash-0731` → HTTP 402 Insufficient credits (owner context: ~319.4 purchased vs ~319.79 used). `GET /api/v1/credits` was **not** callable: it requires a management key; `OPENROUTER_MANAGEMENT_KEY` is absent (would 403). `[9]` Per-key `usage` of 0 does not contradict account-level overdraft; `GET /key` `usage` is this key's spend, not account totals. `[1][8]`

| Slug | HTTP | Notes |
| --- | --- | --- |
| `liquid/lfm-2.5-2.6b:free` | **200** | generation id `gen-1787793797-2WelxSMIM1z6ZjFYfWFv`; immediate `GET /generation` 404; retry HTTP 200, `total_cost=0`, provider Liquid, model `liquid/lfm-2.5-2.6b-20260811:free`. Short `pong` completion body was empty (likely reasoning vs 8 max tokens). `[10]` |
| `openrouter/free` | **200** | resolved to `nvidia/nemotron-3.5-lightning:free`; id `gen-1787793804-F2TQPdT2frdTAk6BC3FR`; retry `total_cost=0`, provider Nvidia. `[10]` |
| `google/gemma-4-26b-a4b-it:free` | **429** | upstream provider rate-limit (`Provider returned error`), **not** 402. `[10][1]` |

**Inference (labeled).** At this slight overdraft, **free completions did not 402**. Official "may" still stands for other overdraft sizes or future policy. If `:free` later 402s, that is expected from `[1]`, not a skill error. Do not write "free never needs credits." `[1][10]`

## 3. How T0 grunt should pick a test slug vs paid cheap

| Situation | Slug | Why |
| --- | --- | --- |
| Sidecar **test** / Wave 0 smoke while paid 402s | `liquid/lfm-2.5-2.6b:free` | Live 200, $0, small ctx, vendor says not for agentic coding. Allowlisted. |
| Optional test router | `openrouter/free` | Live 200; **random** backend — not for coding or reproducible T0. |
| **Paid cheap** T0 (credits > 0) | `deepseek/deepseek-v4-flash-0731` plus `:floor` | Existing default; 402 until topped up. Prefer `:floor` for price sort. `[2]` |
| Agentic coding / T1+ | Not `:free`, not `openrouter/free` | Rate limits, training, upstream 429s, random router. Stay on paid OpenRouter or T2 Max. |

Escalate T0→T1 on schema fail or two retries; never mid-tool-call up-tier. Allowlist before the call. Do not use OpenRouter's `models` array as a hidden upgrade path.

## 4. deep-research and gem-hunt

**deep-research (research_harness).** `web` and `deep_read` stay on Firecrawl → Exa → Tavily (and the rest of the live table). `[16]` T0 **summarization of already-fetched sources** MAY use the OpenRouter sidecar (free or paid-cheap). Do not replace search MCPs with OpenRouter `:online` or `openrouter:web_search`. `[5][16]`

**gem-hunt anti-overfit.** Do not add OpenRouter MCP, LiteLLM, Cursor BYOK, LangGraph, vector-DB, Sentry duplicate, or a trained critic. Fold T0/T1 into `openrouter-routing` + `openrouter-complete.py`. `[16]`

## Key Takeaways

- Wave 0 cheap smoke is **PASS** on the free path (`liquid/lfm-2.5-2.6b:free` and `openrouter/free`).
- Paid DeepSeek T0 and the 3-model bake-off stay **blocked on credits**.
- Free traffic on this account did **not** 402 at the current overdraft; official docs still warn that it **may**.
- Remaining user clicks: add credits; set per-key **Limit** + Daily reset (`limit` is still null). Management key still absent.

## Sources

1. [API Credit & Rate Limits](https://openrouter.ai/docs/api/reference/limits) — tier A — firecrawl scrape (2026) — 402 including free models; 20 RPM; 50/1000 RPD
2. [OpenRouter FAQ](https://openrouter.ai/docs/faq) — tier A — firecrawl scrape (2026) — `:free`, `:online` deprecated, 50/1000 RPD
3. [Free Variant](https://openrouter.ai/docs/guides/routing/model-variants/free) — tier A — firecrawl scrape (2026)
4. [Provider Logging](https://openrouter.ai/docs/guides/privacy/provider-logging) — tier A — firecrawl scrape (2026)
5. [Web Search Server Tool](https://openrouter.ai/docs/guides/features/server-tools/web-search) — tier A — firecrawl scrape (2026) — `:online` deprecated
6. Context7 `/websites/openrouter_ai` — `openrouter/free` API example, GET /models, `:online` migration — tier A — context7 (2026)
7. Live `GET /api/v1/models` — 417 rows, 20 price=0 — tier A — OpenRouter API 2026-08-27
8. Live `GET /api/v1/key` — `is_free_tier=false`, `limit=null` — tier A — OpenRouter API 2026-08-27
9. [Get remaining credits](https://openrouter.ai/docs/api/api-reference/credits/get-remaining-credits) — tier A — official OpenAPI; management key required
10. Live `POST /api/v1/chat/completions` + delayed `GET /generation` — tier A — OpenRouter API 2026-08-27
11. [Free AI Models collection](https://openrouter.ai/collections/free-models) — tier B — firecrawl scrape (2026)
12. [OpenRouter pricing](https://openrouter.ai/pricing) — tier B — firecrawl search snippet (2026) — 50 reqs/day on Free plan
13. [aireiter.com — Fix OpenRouter 429](https://aireiter.com/blog/fix-openrouter-429) — tier B — web (2026) — 20 RPM / 50 vs 1000 RPD; 402 vs 429
14. [buldrr.com — OpenRouter Free API 2026](https://buldrr.com/openrouter-free-api-keys-free-models-simple-guide/) — tier C — web (2026) — negative balance can 402 free
15. [OmniRoute issue #6842](https://github.com/diegosouzapw/OmniRoute/issues/6842) — tier C — web — 402 blocks free models
16. Workspace skills `openrouter-routing`, `deep-research` (`research_harness/routing.py`), `gem-hunt` anti-overfit — local policy, not a web source

## Methodology

**Sub-questions:** (1) current `:free` / price-0 catalog and limits; (2) 402 on free when paid balance is slightly negative; (3) T0 test slug vs paid cheap; (4) what deep-research / gem-hunt may send to the sidecar; (5) official docs plus a second source.

**Preflight (this session):**

| Provider | Status |
| --- | --- |
| firecrawl (`firecrawl_search`, `firecrawl_scrape`) | LIVE |
| context7 (`resolve-library-id`, `query-docs`) | LIVE |
| OpenRouter HTTP API (`/models`, `/key`, `/chat/completions`, `/generation`) | LIVE (`OPENROUTER_API_KEY` present by name) |
| web search (Cursor) | LIVE |
| basic-memory MCP | `user-basic-memory` discovery **DOWN**; `project-0` `write_note` **succeeded** (title `research openrouter-free-models 2026-08-27`) |
| exa, tavily, perplexity, searxng, huggingface, scholarly-access, tooluniverse, cve-mcp | **DOWN** / not mounted in this Cursor session |
| `OPENROUTER_MANAGEMENT_KEY` | **absent** — cannot GET `/credits` or PATCH key limits |

**Cache:** research-harness disk cache was not used (0 hits / 12 misses). Coverage: `~\.coverage-thresholds.json` **absent** → **NOT-CHECKED**.

**Not done:** Sci-Hub; Cursor BYOK; OpenRouter MCP; changing Codex default (`gpt-5.6-sol`); printing `OPENROUTER_API_KEY`.
