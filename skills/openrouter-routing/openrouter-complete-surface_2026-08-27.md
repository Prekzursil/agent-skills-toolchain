---
title: openrouter-complete-surface_2026-08-27
type: note
permalink: dqverify-repo-20261013/skills/openrouter-routing/openrouter-complete-surface-2026-08-27
---

# OpenRouter complete product surface vs this harness
*Generated: 27.08.2026 | Sources: 38 | Providers: firecrawl, webfetch, live OpenRouter API, Context7-timeout | Confidence: High*
*Cache: 0 hits / 18 misses (no research-harness cache this run) | Stale-allowed: no*

## Executive Summary

Wave 1 already wired the **correct slice**: env-only inference key, T0 chat-completions script, Codex **named** `model_providers.openrouter` with `wire_api = "responses"`, generation-id cost readback, and hard SKIPs of Cursor BYOK, Claude `ANTHROPIC_BASE_URL`, LiteLLM, and OpenRouter MCP. That slice is still right. `[A.corrob x3.2026]`

What this audit adds is the rest of the product. OpenRouter is no longer “chat + a model list.” Live OpenAPI (`https://openrouter.ai/openapi.json`) documents **77 paths / 101 operations** across chat, Responses, Anthropic Messages, embeddings, rerank, images, audio, video, files, containers, presets, guardrails, workspaces, analytics, SCIM, and observability. A **Batch API** lives outside that spec at `POST /api/beta/batches`. An official **remote MCP** exists at `https://mcp.openrouter.ai/mcp`. None of those extras are in the harness, and most should stay out. `[A.corrob x2.2026]`

**Live account (inference key, secret never logged):** `GET /api/v1/key` → `limit=null`, `limit_reset=null`, key usage fields `0`, not a management/provisioning key, `is_free_tier=false`. `GET /api/v1/credits` → `total_credits=319.4`, `total_usage≈319.79` (**slightly overdrawn**). Paid T0 will 402 until a top-up. Sibling smoke (consumed, not re-run) shows `:free` still returns HTTP 200 on this overdrawn balance; some free slugs 429 upstream. `[A.corrob x2.2026]`

**Live catalog (2026-08-27):** `GET /api/v1/models` → **417** chat-family models; **17** `:free` suffixes (sibling enumerator counted **20** zero-price rows including aliases); **348** tool-capable; **66** cheap tool-capable (≤$0.15/M in and ≤$0.60/M out); **103** providers; embeddings are a **separate** catalog (`GET /api/v1/embeddings/models` → **33**). Pointer: `https://openrouter.ai/api/v1/models` and `https://openrouter.ai/models?fmt=cards&output_modalities=embeddings`. `[A.single.2026]`

Wave 1 wiring is **not contradicted**. Soft gaps: `:floor` also admits **flex service tiers** (skill currently says “sort=price” only); T0 pin `deepseek/deepseek-v4-flash-0731` is **2×** the live `~deepseek/deepseek-v4-flash-latest` list price; official Codex cookbook wants OpenRouter as the **default** provider (we correctly refused). `[A.corrob x2.2026]`

---

## 1. Auth, keys, credits, budgets

### What OpenRouter offers

Three auth planes: cookie (chat UI), **inference API keys** (Bearer, completions + core GETs), **management API keys** (create/list/PATCH/DELETE keys; cannot run completions). `[A.corrob x2.2026]`

Inference keys: optional USD **Limit**, one `limit_reset` of `daily` | `weekly` | `monthly` | none (XOR, not daily AND monthly on one key). `include_byok_in_limit` exists. `GET /api/v1/key` returns `limit`, `limit_remaining`, `usage_*`, `byok_usage_*`, `is_management_key`, `is_provisioning_key`. `[A.corrob x2.2026]`

**Credits:** no inference markup; **5.5% fee** ($0.80 minimum) on card top-ups; crypto 5%. Unused credits **may expire after 1 year**. Refunds of unused credits within 24h; platform fee non-refundable. BYOK to upstream providers: 5% of list price after a plan-dependent free allowance ($25k/mo PAYG, $200k Enterprise). `[A.corrob x2.2026]`

**Workspace budgets (Enterprise, org admin):** daily AND monthly AND weekly AND lifetime together, strictly decreasing. Exceed → **403** (not 402). Management `PUT /api/v1/workspaces/{id}/budgets/{interval}`. Default workspace is allowed. `[A.corrob x2.2026]`

**OAuth / provisioning:** `POST /auth/keys`, MCP consent mints a dedicated key (7-day expiry, $10 default cap). Do not mint from this agent session. `[A.single.2026]`

### Our harness

USED: env `OPENROUTER_API_KEY`, name-only pointer in `.agents/local.json`, `GET /key` via `--show-limits`, skill checklist for dashboard Limit. UNUSED: management keys, workspace budgets, BYOK-to-providers, OAuth, Infisical rotation. SKIP: minting keys, Cursor paste.

### Live vs docs mismatch

The credits API-reference blurb says “Management key required.” Live `GET /api/v1/credits` with the **inference** key returned 200 and balances. Treat inference-key credits read as **USED and working**. `[A.corrob x2.2026]` (docs page vs live)

---

## 2. API surface (OpenAPI + live probes)

OpenAPI 3.1.0 at `https://openrouter.ai/openapi.json` (YAML also at `/openapi.yaml`). `/api/v1/openapi` is **404**. `[A.single.2026]`

### Operations inventory (77 paths / 101 ops)

Grouped from live spec. Base: `https://openrouter.ai/api/v1`.

| Group | Methods / paths | Harness |
| --- | --- | --- |
| Chat | `POST /chat/completions` | USED (T0 script) |
| Responses | `POST /responses` | USED (Codex `wire_api`) |
| Anthropic Messages | `POST /messages` | SKIP (Claude Max native) |
| Embeddings | `POST /embeddings`, `GET /embeddings/models` | UNUSED-worth-adopting |
| Rerank | `POST /rerank` | UNUSED-worth-adopting (RAG) |
| Images | `POST /images`, `GET /images/models`, endpoints | SKIP unless media grunt |
| Audio | `POST /audio/speech`, `POST /audio/transcriptions` | SKIP |
| Video | `POST /videos`, `GET /videos/{jobId}`, content, models | SKIP |
| Generation stats | `GET /generation`, `GET /generation/content`, `POST /generation/feedback` | USED (`/generation`); content/feedback UNUSED |
| Models | `GET /models`, `/models/count`, `/models/user`, `/model/{author}/{slug}`, `/models/{author}/{slug}/endpoints` | UNUSED (manual verify) |
| Providers | `GET /providers` | UNUSED |
| Key (self) | `GET /key` | USED |
| Keys (mgmt) | `GET/POST /keys`, `GET/PATCH/DELETE /keys/{hash}` | SKIP (dashboard) |
| Credits | `GET /credits`, `POST /credits/coinbase` | UNUSED in script; live-checked |
| Files / containers | files CRUD + container file promote | SKIP |
| Presets | list/get/versions + run chat/messages/responses | ADOPT-later |
| Guardrails | 13 ops (CRUD + key/member assign) | SKIP unless org policy |
| Workspaces | CRUD, members, budgets | SKIP (Enterprise for dual caps) |
| Analytics / datasets | `/analytics/*`, `/activity`, rankings, session-cost, benchmarks, task classifications | ADOPT-later (CSV/activity) |
| Observability | destinations CRUD (Datadog/Grafana/OTel/Arize) | SKIP (RAM/ops) |
| BYOK | `/byok` CRUD | SKIP (council) |
| OAuth | `/auth/keys`, `/auth/keys/code` | SKIP |
| SCIM | groups/mappings | SKIP (Enterprise IdP) |
| ZDR endpoints list | `GET /endpoints/zdr` | UNUSED |
| Batch (not in v1 OpenAPI) | `POST /api/beta/batches`, `GET /api/beta/batches/:id` | ADOPT-later |

Error codes (HTTP matches `error.code` unless the model already started): **400** bad params, **401** auth, **402** credits/key cap, **403** guardrail/budget/moderation, **408** timeout, **429** rate, **502** model down, **503** no provider matches routing. Mid-stream errors arrive as SSE `finish_reason: error`. Retry-After on 429/503. `[A.corrob x2.2026]`

404: no matching model/provider after filters; Auto Router with empty allowlist; GET `/chat/completions` (GET not allowed — live 404). Generation stats **404 until indexed** (sibling: successful 200 completion still 404 on `/generation` seconds later). `[A.corrob x2.2026]`

---

## 3. Routing

Default: price-weighted load balance among healthy providers; tools/`max_tokens` bias toward capable endpoints. `provider` object: `order`, `allow_fallbacks` (default true), `require_parameters`, `data_collection` allow|deny, `zdr`, `enforce_distillable_text`, `only`, `ignore`, `quantizations`, `sort` (price|throughput|latency or `{by, partition}`), throughput/latency percentile prefs, `max_price`. `[A.single.2026]`

Suffixes: `:floor` = sort price **and admit flex tiers**; `:nitro` = sort throughput **and admit priority/fast tiers**; `:exacto` = quality-first tool-call ranking; `:free` = free variant; `:online` **deprecated**. Explicit `provider.sort` wins over suffix. `:floor`/`:nitro` are supersets of `provider.sort`, not aliases. `[A.corrob x2.2026]`

`models[]` / Anthropic `fallbacks` (max 3, Messages skin only): try next **model** on errors including context, moderation, 429, downtime. **Changes behavior.** Council: do not use as hidden T0→T2. T1 may use one different-vendor fallback as a **new step**, not mid-tool-call. `[A.corrob x2.2026]`

Routers: `openrouter/auto` (market spend-share by ~30 task types, `cost_tier` low|medium|high|xhigh|max, default ~low), `openrouter/auto-beta`, `openrouter/free` (random free model matching capabilities), Pareto / Fusion routers. Session stickiness via `session_id` / `x-session-id`. `[A.corrob x2.2026]`

ZDR: account toggles per model group (Anthropic 1P / OpenAI 1P / Google AI Studio / SpaceXAI / other), guardrails, and `provider.zdr`. Plugins/server tools are **not** covered by ZDR. Implicit prompt cache is allowed under ZDR. `[A.corrob x2.2026]`

---

## 4. Model capabilities

Live `/models` parameter frequencies (n=417): tools 348, structured_outputs 332, reasoning/include_reasoning 285, response_format 360. Input modalities: text 417, image 251, file 158, video 70, audio 41. Output: text 417, image 11, audio 4. `[A.single.2026]`

Cheap tool-capable (compact; $/M prompt / completion, live list prices):

| Slug | In | Out | Note |
| --- | --- | --- | --- |
| `~deepseek/deepseek-v4-flash-latest` | 0.03 | 0.075 | Cheaper than Wave 1 pin |
| `deepseek/deepseek-v4-flash-0731` | 0.06 | 0.12 | Current T0 default |
| `qwen/qwen3.7-flash` | 0.03 | 0.13 | T0/T1 candidate |
| `inclusionai/ling-3.0-flash` | 0.021 | 0.063 | Verify quality |
| `xiaomi/mimo-v2.5` | 0.14 | 0.28 | Plan T1 shortlist |
| `z-ai/glm-4.7-flash` | 0.06 | 0.40 | |
| `mistralai/mistral-nemo` | 0.019 | 0.03 | Cheapest tools in sample |

`:free` sample (17 suffix ids): Cohere North Mini Code, Gemma 4 26B/31B, LFM 2.5, MiniMax M2.7/M3, several Nemotron 3.x, Poolside Laguna, Thinking Machines Inkling, GLM 5.2 free, etc. **Not** for agentic coding as GOAT. Sibling: `liquid/lfm-2.5-2.6b:free` 200; `openrouter/free` 200 → `nvidia/nemotron-3.5-lightning:free`; Gemma 4 26B `:free` **429** upstream. `[A.corrob x2.2026]`

Embeddings: **not** in `/models`; **33** via `/embeddings/models`. Images/audio/video are first-class APIs plus server tools. PDFs: file-parser plugin or multimodal file parts; FAQ: PDFs work with any model via URL/base64. `[A.corrob x2.2026]`

**Server tools (beta, `openrouter:*` in `tools`):** web_search, datetime, image_generation, web_fetch, apply_patch (Responses), shell, bash (Messages), fusion, advisor, subagent, search_models, tool_search. Outer `max_tool_calls` default/max 30. Plugins (always-on once): web (**deprecated**), file-parser, response-healing, pareto-router, context-compression. `[A.single.2026]`

Prompt cache: implicit on many providers; Anthropic `cache_control`; sticky routing 10 min; `session_id` / `prompt_cache_key`. Reasoning tokens in usage details. Structured outputs: `json_object` and `json_schema`. `[A.corrob x2.2026]`

---

## 5. Apps and official integrations (NATIVE vs BUILD vs SKIP)

| App | How OpenRouter ships it | Verdict |
| --- | --- | --- |
| Cursor cookbook | Paste key + Override Base URL `https://openrouter.ai/api/v1/cursor` (not `/v1`). Tab stays Cursor-native; Auto/Composer 2 may ignore BYOK; Composer 2.5 not on OR | **SKIP** — breaks Max; council |
| Claude Code | `ANTHROPIC_BASE_URL=https://openrouter.ai/api` (**not /v1**), `ANTHROPIC_AUTH_TOKEN`, empty `ANTHROPIC_API_KEY`, optional `/logout` | **SKIP** — rebills Max |
| Codex CLI | `[model_providers.openrouter]`, `wire_api=responses`, full slugs. Official blog often sets this as **default** `model_provider` | **NATIVE-USED** as **named profile only**; default stays `gpt-5.6-sol` |
| Official MCP | Remote `https://mcp.openrouter.ai/mcp`, OAuth, tools: list-models, credits, send-message (billable), etc. | **SKIP** — see anti-overfit |
| OpenRouter TypeScript/Python SDKs | `@openrouter/sdk` / `openrouter` | SKIP (urllib + Codex enough) |
| Agent SDK `@openrouter/agent` | Multi-turn loop | SKIP (duplicate agent runtime) |
| Aider | `aider --model openrouter/<provider>/<model>` | BUILD-optional later (git loops); not now |
| Cline / Roo / Kilo / Continue | Native provider dropdown | SKIP (RAM / fourth IDE) |
| Open WebUI | Self-hosted UI + OR inference; app rankings #34 | SKIP (RAM) |
| OpenCode, OpenClaw, Junie, Copilot, Xcode, SillyTavern | Cookbooks / works-with | SKIP |
| Hermes Agent (Nous Research) | **#1 app on OpenRouter's separate `/apps` App & Agent Rankings** — an app leaderboard this audit's `/rankings` scrape did not cover; not a model in the models ranking | SKIP (second agent runtime) |
| LangChain, LlamaIndex, Vercel AI SDK, PydanticAI, Mastra, Effect, TanStack | Framework adapters | SKIP unless a project needs them |
| Infisical key rotation | Management key | SKIP |
| LiteLLM | Self-hosted proxy in front of OR | **SKIP** (RAM; OR *is* the router) |

Apps-gap follow-up: [openrouter-apps-hermes-uncensored_2026-08-27.md](openrouter-apps-hermes-uncensored_2026-08-27.md) covers the `/apps` leaderboard and the Hermes disambiguation.

---

## 6. Product extras

| Extra | Offers | Verdict |
| --- | --- | --- |
| Auto / Pareto / Fusion / Free routers | Market or random routing | ADOPT-later Auto with allowlist + `cost_tier=low`; skip Free as daily driver |
| Rankings / Arena / Data API | Token volume ≠ quality; CC-BY datasets | SKIP as quality SSOT (plan already said this) |
| Activity CSV/PDF | Dashboard export; `GET /activity` | ADOPT-later into cost-tracking |
| Privacy | Prompts not stored unless opt-in logging or 1% discount training; metadata always | USED (defaults). Do not enable discount logging for code |
| Fine-tune hosted | **None** in OpenAPI. Distill = `enforce_distillable_text` + NeMo cookbook | SKIP hosted FT |
| Apps marketplace / works-with | Attribution headers already sent | USED headers; SKIP shopping apps |
| Ori eval / install-ori-harness (MCP) | Eval harness | SKIP |
| Broadcast observability | Grafana, Datadog, OTel, Arize, Ramp | SKIP |
| Service tiers flex/priority/fast | `:floor`/`:nitro` admit them | ADOPT-later via suffixes; don’t pin `service_tier: flex` until T0 bake-off |
| Batch 50% | `/api/beta/batches`, 24h, text-only | ADOPT-later for bulk T0 |
| Anthropic beta headers | interleaved thinking, strict tools | SKIP (T2 stays native Claude) |

---

## 7. Pricing vs T0 / T1 / T2

| | Policy | Live implication |
| --- | --- | --- |
| T0 | Cheapest capable OR; never Max; allowlist; no `models[]` uptier | Pin is 0731 @ $0.06/$0.12; latest-flash alias $0.03/$0.075. `:floor` for flex. Batch 50% for bulk. Paid **blocked until credit top-up**. `:free` works but 50/day unless ≥$10 purchased (account already purchased ≫$10 historically, so **1000/day** free quota if docs still hold) |
| T1 | Mid OR; one different-vendor outage fallback as new step | MIMO / GLM / Qwen flash; `:exacto` if tools |
| T2 | Cursor Max / Claude Max | Do not send Opus/Sol via OR unless native rate-capped |

Free-model RPM/RPD: < $10 lifetime credits → 50/day; ≥ $10 → 1000/day. Negative **account** balance 402s even free models per limits doc — **sibling evidence contradicts for this key today** (`:free` 200 while credits slightly negative). Treat as **fragile**: do not design T0 around overdrawn+free. `[A.corrob x2.2026]` vs `[A.single.2026]` limits page.

---

## Feature matrix

| Feature | OpenRouter offers | Our harness | Verdict |
| --- | --- | --- | --- |
| Inference API key (Bearer) | Yes | Env + local.json name | **USED** |
| Management API keys | Yes; cannot complete | Not created | **SKIP** (dashboard only) |
| Per-key Limit XOR reset | daily/weekly/monthly | Documented; `limit=null` live | **USED (docs)** / **NOT-CHECKED (click)** |
| Workspace daily+monthly budgets | Enterprise | Documented | **SKIP** unless Enterprise |
| Credits / 5.5% top-up fee | Yes | Not automated | **SKIP** (user click) |
| BYOK upstream keys | 5% over allowance | — | **SKIP** |
| `POST /chat/completions` | OpenAI-compatible | `openrouter-complete.py` | **USED** |
| `POST /responses` | Codex wire | Codex provider | **USED** |
| `POST /messages` | Anthropic skin | — | **SKIP** (Claude Max) |
| `GET /key` | Limits/usage | `--show-limits` | **USED** |
| `GET /credits` | Balance | Live-checked only | **ADOPT-later** in script |
| `GET /generation` | Cost/stats | Script + cost-tracking | **USED** (404 lag) |
| `GET /generation/content` | Stored prompt/completion | Needs logging opt-in | **SKIP** (privacy) |
| App headers Referer/Title | Rankings | Set | **USED** |
| `GET /models` | 417 live | Not in skill loop | **ADOPT-later** (allowlist refresh) |
| `GET /providers` | 103 | — | **UNUSED** |
| Embeddings + rerank | 33 embed models | — | **ADOPT-later** |
| Images / TTS / STT / video | First-class APIs | — | **SKIP** |
| Files / containers | Yes | — | **SKIP** |
| Batch API | `/api/beta/batches` ~50% | — | **ADOPT-later** |
| `:floor` / `:nitro` / `:exacto` | Suffixes + flex/priority | Documented | **USED (docs)**; T0 should prefer `:floor` |
| `:online` / web plugin | Deprecated | Skill forbids | **SKIP** |
| Server tool `openrouter:web_search` | Beta | — | **ADOPT-later** |
| Other server tools (shell, fusion, …) | Beta | — | **SKIP** (cost/loop) |
| Plugins response-healing / PDF / compression | Yes | — | **ADOPT-later** (healing for T0 schema) |
| `models[]` fallback | Cross-model | Forbidden as uptier | **SKIP** (policy) |
| Auto Router | `openrouter/auto` | — | **ADOPT-later** with allowlist |
| Free Router `openrouter/free` | Random free | Sibling smoked | **SKIP** as default T0 |
| `provider.zdr` / data_collection | Yes | — | **ADOPT-later** if handling secrets |
| Prompt cache + `session_id` | Sticky 10 min | — | **ADOPT-later** |
| Structured outputs | json_schema | T0 escalates on schema fail | **ADOPT-later** |
| Reasoning / thinking | Many models | — | T1 only if needed |
| Presets | Saved request configs | — | **ADOPT-later** |
| Guardrails | Org filters | — | **SKIP** |
| Analytics / Activity CSV | Dashboard + API | Generation ids only | **ADOPT-later** |
| Observability broadcast | Datadog etc. | — | **SKIP** |
| SCIM / org members | Enterprise | — | **SKIP** |
| Official MCP | mcp.openrouter.ai | Council forbid | **SKIP** |
| Cursor `/v1/cursor` BYOK | Cookbook | Forbidden | **SKIP** |
| Claude `ANTHROPIC_BASE_URL` | Cookbook | Forbidden | **SKIP** |
| Codex named provider | Cookbook | Merged non-default | **USED** |
| LiteLLM | Third-party | Forbidden | **SKIP** |
| Hosted fine-tune | No | — | **SKIP** (N/A) |
| Distill filter | `enforce_distillable_text` | — | **SKIP** (no FT pipeline) |
| Open WebUI / Cline / Aider IDEs | Works-with | RAM | **SKIP** (Aider optional later) |
| Agent SDK / Ori | Yes | — | **SKIP** |
| Flex/priority `service_tier` | Yes | Indirect via suffixes | **ADOPT-later** |

---

## We would have missed X without this audit

1. **`:floor` admits flex service tiers**; `:nitro` admits priority/fast. Skill text understates this. `[A.single.2026]`
2. **Batch API** at `/api/beta/batches` is **absent from OpenAPI v1** (77 paths). ~50% token discount, text-only, 24h window. `[A.corrob x2.2026]`
3. **Embeddings live on a second catalog** (`/embeddings/models` = 33). `/models` embedding_like_count = 0. `[A.single.2026]`
4. **Official remote MCP** with billable `send-message` / `generate-image` and a minted 7-day $10 key — easy to “just add” to `.cursor/mcp.json`. `[A.single.2026]`
5. **Cursor endpoint is `/api/v1/cursor`**, not `/api/v1`; generic `/v1` breaks Cursor tool-call shape. `[A.corrob x2.2026]`
6. **Claude cookbook now uses `ANTHROPIC_AUTH_TOKEN` + empty `ANTHROPIC_API_KEY` + `/logout`**, not only base URL. Still a Max-bypass. `[A.single.2026]`
7. **Server tools vs plugins vs `:online`**: web search moved to `openrouter:web_search`; plugin `web` and `:online` deprecated. `[A.corrob x2.2026]`
8. **Workspace budget exceed is 403**, key/account credit exceed is **402**. `[A.corrob x2.2026]`
9. **`GET /credits` works with inference keys** despite some “management key required” copy. `[A.corrob x2.2026]`
10. **`GET /generation` 404 lag is real** after 200 completions (sibling). Cost-tracking must retry; do not treat 404 as “no spend.” `[A.single.2026]`
11. **T0 pin is not the cheapest DeepSeek flash** on the live list (`latest` alias $0.03 vs 0731 $0.06). `[A.single.2026]`
12. **No hosted fine-tune**; distill is a routing filter + off-platform training. `[A.corrob x2.2026]`
13. **OpenAPI has 101 operations** (audio, video, SCIM, presets, guardrails, analytics) that Wave 1 never enumerated. `[A.single.2026]`
14. **Overdrawn credits + `:free` 200** today vs limits-doc “negative balance 402s free models.” Do not productize that loophole. `[A.corrob x2.2026]` (conflict flagged)

---

## Remaining user clicks

1. **Credit top-up** at [https://openrouter.ai/settings/credits](https://openrouter.ai/settings/credits) until `total_credits > total_usage` (now ~$0.39 over). Paid T0/T1 will 402 until then.
2. **Per-key Limit** on the *existing* inference key at [https://openrouter.ai/settings/keys](https://openrouter.ai/settings/keys): set Limit (USD) + Limit reset Daily **or** Monthly (not both). Re-check `GET /api/v1/key` (`limit` is still `null`).
3. Optional: if Enterprise, workspace Budgets daily **and** monthly (strictly decreasing). Not required for PAYG.
4. Do **not** paste the key into Cursor. Do **not** log out. Do **not** add MCP.

---

## Wave 1 wiring check

| Item | Status |
| --- | --- |
| Default Codex `model = gpt-5.6-sol` | Intact (line 18). Profile openrouter uses DeepSeek flash |
| `[model_providers.openrouter]` `wire_api=responses`, `env_key=OPENROUTER_API_KEY` | Intact |
| T0 script chat/completions + generation retry | Intact |
| No MCP / no Cursor base URL / no LiteLLM / no Claude base URL | Intact |
| No mid-tool-call uptier | Intact (skill + AGENTS.md) |
| Soft doc gap | `:floor` flex-tier admission; cheaper live flash alias |
| Account | Overdrawn; key uncapped — smoke/T0 paid blocked |

**Verdict: Wave 1 wiring stands. This audit does not require rewiring. It requires a user top-up + Limit click, then optional ADOPT-later items.**

---

## Anti-overfit: skip official OpenRouter MCP

OpenRouter ships a hosted MCP at `https://mcp.openrouter.ai/mcp` (Claude Code, Codex, Cursor `mcp.json`, OpenCode). Tools include catalog search, credits, rankings, docs search, and **billable** `send-message` / `generate-image`. Auth mints a **separate** 7-day key with a $10 cap. `[A.single.2026]`

**Still SKIP.** Council: no new MCP this week; OR is an LLM HTTP API, not a tool server we lack. This machine already has:

- Native Codex `[model_providers.openrouter]` (Responses),
- T0 CLI `openrouter-complete.py`,
- `GET /key` + `/generation` for spend,
- Live `/models` via the same inference key.

Adding MCP would duplicate inference, create a second secret with a short TTL, and fight RAM/plugin diagnosis. Cursor cookbook MCP snippet belongs in `.cursor/mcp.json` — explicitly forbidden.

---

## Live catalog compact table

| Metric | Value (2026-08-27) |
| --- | --- |
| `GET /models` count | 417 |
| `:free` suffix | 17 (sibling zero-price list: 20) |
| Tool-capable | 348 (`?supported_parameters=tools` filtered to 333) |
| Cheap tool-capable (heuristic) | 66 |
| Embeddings models | 33 (`/embeddings/models`) |
| Image-out / audio-mod on `/models` | 11 / 43 |
| Providers | 103 |
| OpenAPI paths / operations | 77 / 101 |
| Key limit | `null` (uncapped) |
| Credits | 319.4 purchased / ~319.79 used (overdrawn) |

Do not dump the catalog here. Refresh: `GET https://openrouter.ai/api/v1/models` with the env key.

---

## Methodology

**Sub-questions:** (1) auth/keys/budgets/credits/BYOK (2) API endpoints + errors (3) routing/suffixes/ZDR/fallbacks (4) capabilities/tools/plugins/cache (5) apps/integrations (6) extras/MCP/batch/distill/analytics (7) pricing T0/T1 (8) gap vs this harness.

**Routed providers:** firecrawl (map, search, scrape — then concurrency timeouts), WebFetch fallback for deep-read, live OpenRouter HTTP (Python, secret redacted), WebSearch corroboration. Context7 resolve succeeded (`/websites/openrouter_ai`); `query-docs` **timed out**. Exa, Tavily, Searxng, Perplexity, scholarly-access: **not mounted** this session. Playwright: not required. `user-basic-memory` MCP **error**; `project-0-Prekzursil-basic-memory` ready. BEADS `bd prime --work-type` **invalid flag** this CLI — knowledge prime **NOT-CHECKED**.

**DOWN at preflight:** Context7 query, Exa, Tavily, Searxng, Perplexity, user-basic-memory. Firecrawl intermittent after first scrapes.

**Deep-read (full pages, not snippets):** provider-selection, API overview, limits, server-tools, data-collection, ZDR, errors, MCP, Cursor cookbook, Claude Code cookbook, Auto Router, workspace budgets, FAQ, Exacto, embeddings, model-fallbacks, activity-export, plugins, batch-quickstart, free-router, frameworks overview, any-coding-agent blog, prompt-caching, service-tiers, Responses tool-calling, generation endpoint, status.openrouter.ai.

**Sibling consume (not re-run):** `_tmp_smoke_results.json`, `_tmp_free_models.json`, `_tmp_generation_retry.py`. Gem-hunt / plugin-cache tracks not duplicated (`MAX-EFFORT-PLUGIN-DIAGNOSIS.md` is Cursor, not OR).

**Cross-ref:** load-bearing claims cited to ≥2 of {official docs, FAQ, OpenAPI/live API, cookbook, status, sibling smoke}.

---

## Key takeaways

- Keep Wave 1 sidecar. Do not add MCP, Cursor BYOK, LiteLLM, or Claude base URL.
- User must top up credits and set a per-key Limit before paid T0 is useful.
- Highest-value unused features: Batch 50%, embeddings/rerank, `:floor` flex semantics, `session_id` cache, web_search server tool, response-healing, activity CSV, cheaper flash alias, Auto Router with allowlist.
- `:free` is a stopgap on an overdrawn account, not a T0 strategy.

## Sources

1. [API overview + OpenAPI links](https://openrouter.ai/docs/api_reference/overview) — tier A — firecrawl (2026)
2. [OpenAPI JSON](https://openrouter.ai/openapi.json) — tier A — live (2026)
3. [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection) — tier A — firecrawl (2026)
4. [Credit & rate limits](https://openrouter.ai/docs/api_reference/limits) — tier A — firecrawl (2026)
5. [GET current API key](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key) — tier A — firecrawl (2026)
6. [Management API keys](https://openrouter.ai/docs/guides/overview/auth/management-api-keys) — tier A — firecrawl (2026)
7. [Authentication](https://openrouter.ai/docs/api_reference/authentication) — tier A — firecrawl (2026)
8. [BYOK](https://openrouter.ai/docs/guides/overview/auth/byok) — tier A — firecrawl (2026)
9. [FAQ](https://openrouter.ai/docs/faq) — tier A — webfetch (2026)
10. [Data collection / privacy](https://openrouter.ai/docs/guides/privacy/data-collection) — tier A — webfetch (2026)
11. [ZDR](https://openrouter.ai/docs/guides/features/zdr) — tier A — webfetch (2026)
12. [Errors and debugging](https://openrouter.ai/docs/api_reference/errors-and-debugging) — tier A — webfetch (2026)
13. [Server tools](https://openrouter.ai/docs/guides/features/server-tools) — tier A — webfetch (2026)
14. [Plugins](https://openrouter.ai/docs/guides/features/plugins) — tier A — webfetch (2026)
15. [MCP server](https://openrouter.ai/docs/guides/overview/mcp-server) — tier A — webfetch (2026)
16. [Cursor cookbook](https://openrouter.ai/docs/cookbook/coding-agents/cursor-integration) — tier A — webfetch (2026)
17. [Claude Code cookbook](https://openrouter.ai/docs/cookbook/coding-agents/claude-code-integration) — tier A — webfetch (2026)
18. [Codex CLI blog](https://openrouter.ai/blog/tutorials/codex-cli-openrouter/) — tier B — websearch (2026)
19. [Auto Router](https://openrouter.ai/docs/guides/routing/routers/auto-router) — tier A — webfetch (2026)
20. [Free Models Router](https://openrouter.ai/docs/guides/routing/routers/free-router) — tier A — webfetch (2026)
21. [Exacto](https://openrouter.ai/docs/guides/routing/model-variants/exacto) — tier A — webfetch (2026)
22. [Model fallbacks](https://openrouter.ai/docs/guides/routing/model-fallbacks) — tier A — webfetch (2026)
23. [Workspace budgets](https://openrouter.ai/docs/guides/features/workspaces/workspace-budgets) — tier A — webfetch (2026)
24. [Embeddings](https://openrouter.ai/docs/api_reference/embeddings) — tier A — webfetch (2026)
25. [Batch quickstart](https://openrouter.ai/docs/batch-quickstart) — tier A — webfetch (2026)
26. [Activity export](https://openrouter.ai/docs/cookbook/administration/activity-export) — tier A — webfetch (2026)
27. [Prompt caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching) — tier A — webfetch (2026)
28. [Service tiers](https://openrouter.ai/docs/guides/features/service-tiers) — tier A — webfetch (2026)
29. [Responses tool calling](https://openrouter.ai/docs/api_reference/responses/tool-calling) — tier A — webfetch (2026)
30. [Generation metadata](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation) — tier A — webfetch (2026)
31. [Frameworks overview](https://openrouter.ai/docs/guides/community/frameworks-and-integrations-overview) — tier A — webfetch (2026)
32. [Any coding agent](https://openrouter.ai/blog/tutorials/any-coding-agent/) — tier B — webfetch (2026)
33. [Works with OpenRouter](https://openrouter.ai/works-with-openrouter) — tier B — websearch (2026)
34. [Distillation cookbook](https://openrouter.ai/docs/cookbook/evaluate-and-optimize/distillation) — tier A — websearch (2026)
35. [Aider OpenRouter](https://aider.chat/docs/llms/openrouter.html) — tier B — websearch (2026)
36. [Cline OpenRouter](https://docs.cline.bot/provider-config/openrouter) — tier B — websearch (2026)
37. [OpenRouter status](https://status.openrouter.ai) — tier A — webfetch (2026) All Systems Operational
38. Live `GET /api/v1/{key,credits,models,providers,embeddings/models}` + sibling `_tmp_smoke_results.json` — tier A — this machine (2026)

## Harness files compared

- `C:\Users\Prekzursil\.agents\skills\openrouter-routing\SKILL.md`
- `C:\Users\Prekzursil\.agents\scripts\openrouter-complete.py`
- `C:\Users\Prekzursil\.codex\config.toml` (`[model_providers.openrouter]`, `[profiles.openrouter]` only)
- `C:\Users\Prekzursil\.agents\skills\cost-tracking\SKILL.md` (generation-id section)
- `C:\Users\Prekzursil\AGENTS.md` T0/T1/T2 bullet
- `C:\Users\Prekzursil\.cursor\plans\openrouter_integration_plan_fa46ec35.plan.md`
- Sibling: `_tmp_smoke_results.json`, `_tmp_free_models.json` (consumed)