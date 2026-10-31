---
name: openrouter-routing
description: Route cheap grunt work through OpenRouter as a spend-capped CLI/Codex
  sidecar. Use for T0/T1 model choice, :floor/:nitro/:exacto, spend caps, and generation
  ids. NEVER Cursor BYOK or Claude ANTHROPIC_BASE_URL.
permalink: dqverify-repo-20261013/skills/openrouter-routing/skill
---

# OpenRouter routing (sidecar only)

OpenRouter is a hosted OpenAI-compatible API at `https://openrouter.ai/api/v1`. It is overflow for CLI/Codex, not a local gateway and not a second Cursor stack. Do not install LiteLLM. Do not add an OpenRouter MCP.

## Key location (name only)

| Where | Role |
| --- | --- |
| Environment variable `OPENROUTER_API_KEY` (User and Machine) | Canonical secret |
| `.agents/local.json` field `env_keys.OPENROUTER_API_KEY.env_key` | Pointer by name only |
| Cursor Models / OpenAI API Key / Override Base URL | Forbidden |
| `agents.json` MCP registry / `.cursor/mcp.json` | Do not add OpenRouter |

Never print, commit, or interpolate the secret into logs, skills, or sync output. The T0 script reads the environment variable at runtime.

## Never Cursor BYOK

Do not put the OpenRouter secret into Cursor. The vendor cookbook sets Cursor's OpenAI key plus Override Base URL to `https://openrouter.ai/api/v1/cursor`. That can break native Max models; Auto / Composer 2 may ignore BYOK. Composer 2.5 is Cursor-only (not on OpenRouter). Keep Cursor Max exclusive inside Cursor.

## T0 / T1 / T2

Escalate one-way. A cheap outage must not silently spend frontier. No mid-tool-call fallback up the tier (retrying a failed cheap call on a dearer model inside the same tool step costs more than Max).

| Tier | Use | Where |
| --- | --- | --- |
| **T0 grunt** | Extract, reformat, bulk classify | Cheapest capable OpenRouter. Never Cursor Max. |
| **T1 standard** | Drafts, single-file, summaries | Mid OpenRouter. At most one different-vendor fallback for outages, not mid-tool-call retries up-tier. |
| **T2 frontier** | Architecture, multi-file, adversarial, gates | Cursor Max / Claude Max unchanged. |

- T0 to T1 on schema fail or two retries (new step, allowlisted model).
- T1 to T2 on correctness-critical scope.
- Default T0 slug (**paid**, when account balance is above zero): `deepseek/deepseek-v4-flash-0731` (verify live). Prefer `:floor` when shopping on price.
- Cheaper live alias `deepseek/deepseek-v4-flash-latest` ($0.03/$0.075 per M) vs the pin `deepseek/deepseek-v4-flash-0731` ($0.06/$0.12). The pin is deliberate (stability); the alias is cheaper but moving — verify the slug live before adopting.
- Default T0 **test** slug (sidecar smoke while paid returns 402): `liquid/lfm-2.5-2.6b:free`. See [Free / test slugs](#free--test-slugs).

Allowlist the model before the call. Do not use OpenRouter's `models` array as a hidden upgrade path. Do not pick a random `:free` slug for agentic coding.

## Suffixes

Append to a model slug ([provider routing](https://openrouter.ai/docs/guides/routing/provider-selection), [exacto](https://openrouter.ai/docs/guides/routing/model-variants/exacto)):

| Suffix | Meaning |
| --- | --- |
| `:floor` | Cheapest provider (`provider.sort` = price) **and admits flex service tiers** |
| `:nitro` | Highest throughput (`provider.sort` = throughput) and admits priority/fast tiers |
| `:exacto` | Quality-first provider order for tool-calling reliability |
| `:online` | **Deprecated.** Do not use. Web search is the OpenRouter web-search server tool. |

Explicit `provider.sort` overrides a suffix when both are set. `:floor`/`:nitro` are supersets of `provider.sort` (sort plus service-tier admission), not aliases.

## Batch (bulk T0)

`POST /api/beta/batches` runs latency-insensitive bulk grunt (classification, extraction) at roughly 50% of token price — text-only, ~24h completion window. It is **not** in OpenAPI v1 and still requires a positive credit balance. Use ad hoc for bulk T0 jobs only; do **not** wire a daemon around it.

## Claude Code footgun

Do not set `ANTHROPIC_BASE_URL` to `https://openrouter.ai/api` (that host is not `/v1`) and do not empty `ANTHROPIC_API_KEY` to point Claude at OpenRouter. That rebills Claude usage to OpenRouter and bypasses Claude Max. Leave Claude on native Max.

## Codex: named provider only

Wave 1 merges a **non-default** `[model_providers.openrouter]` into `~/.codex/config.toml`:

- `base_url = "https://openrouter.ai/api/v1"`
- `env_key = "OPENROUTER_API_KEY"`
- `wire_api = "responses"` (Codex no longer accepts `chat`)

Default Codex `model` stays ChatGPT-native. Do not make OpenRouter the default.

Opt-in: `codex --profile openrouter`, or set `model_provider = "openrouter"` for that invocation only.

OpenRouter serves `/api/v1/responses` (Codex wire). The T0 grunt script uses `/api/v1/chat/completions`.

## Spend-cap checklist (hard daily + monthly)

Agents cannot operate the OpenRouter dashboard. A normal inference credential can **read** limits via `GET /api/v1/key` (`limit`, `limit_reset`, `limit_remaining`, `usage_daily`, `usage_monthly`). Changing limits needs the dashboard or a Management API credential (`PATCH /api/v1/keys/{hash}`). Management credentials cannot run completions. Do not mint new secrets from an agent session.

One inference credential has **one** `limit_reset`: `daily`, `weekly`, `monthly`, or none — not daily and monthly on the same credential.

### A. Per-key cap (free / PAYG) — you click

1. Open [https://openrouter.ai/settings/keys](https://openrouter.ai/settings/keys) (same list: [https://openrouter.ai/keys](https://openrouter.ai/keys)).
2. Click the **existing** inference key. Do not recreate it. Do not paste it into Cursor.
3. Set **Limit** to a USD credit cap for this key.
4. Set **Limit reset** to **Daily** (midnight UTC) for a hard daily brake, **or** **Monthly** for a monthly brake — pick one.
5. Save. Confirm with `GET /api/v1/key` (script `--show-limits`).

To approximate daily + monthly on PAYG without Enterprise: set the key to **daily** (hard brake) and watch `usage_monthly` from `GET /api/v1/key`. Monthly is then observational unless you add B.

### B. Daily AND monthly hard caps together — you click

Workspace budgets can set both intervals (strictly decreasing: monthly greater than daily). Dashboard:

1. Open `https://openrouter.ai/workspaces/<slug>/settings` (Default workspace is allowed).
2. Scroll to **Budgets**.
3. Click **Add budget**, choose interval `daily`, enter a dollar amount; repeat for `monthly` (monthly must be greater than daily).
4. Click **Save**. Organization Administrator role required. Workspace budgets are documented as Enterprise.

API equivalent (management credential only): `PUT /api/v1/workspaces/{id}/budgets/daily` and `.../monthly` with a `limit_usd` body. Create a management credential only in the browser at [https://openrouter.ai/settings/management-keys](https://openrouter.ai/settings/management-keys).

If `GET /api/v1/key` shows `limit` of null, the per-key cap is not set. Treat dashboard cap as **NOT-CHECKED** until you complete A (and B if you need both windows).

## Free / test slugs

Paid T0 (`deepseek/deepseek-v4-flash-0731`) returned HTTP 402 on this account while slightly overdrawn. Free variants are for **sidecar smoke and cheap extract**, not agentic coding. Allowlist before the call. Catalog snapshot: [openrouter-free-models_2026-08-27.md](openrouter-free-models_2026-08-27.md).

Live `GET /api/v1/models` on 2026-08-27: 417 models, **20** with `pricing.prompt` and `pricing.completion` of `0` (17 `:free` chat slugs, router `openrouter/free`, plus two Lyria audio previews that are not chat T0). Re-fetch before treating this list as current.

| Role | Slug | Live result 2026-08-27 |
| --- | --- | --- |
| **T0 test** (smoke / pong / extract) | `liquid/lfm-2.5-2.6b:free` | HTTP **200**. `GET /generation` later `total_cost=0` (provider Liquid). Liquid advises against agentic coding and may train on free traffic. |
| **T0 test router** (random free; not for coding) | `openrouter/free` | HTTP **200**, resolved to `nvidia/nemotron-3.5-lightning:free`. `GET /generation` later `total_cost=0` (Nvidia). |
| Not a credit failure | `google/gemma-4-26b-a4b-it:free` | HTTP **429** upstream rate-limit (`Provider returned error`), not 402. |
| **Paid cheap** (when credits exist) | `deepseek/deepseek-v4-flash-0731` plus `:floor` | HTTP **402** Insufficient credits. Paid 3-model bake-off stays skipped until the balance is above zero. |

Official docs say a **negative account balance may 402 even free models**. This account's live test: `:free` returned 200 while paid DeepSeek 402'd. Do not claim that is true for every overdraft; if `:free` starts 402, add credits — that is not a skill lie.

Platform caps on IDs ending in `:free`: 20 requests/minute; 50 requests/day if lifetime purchases are under $10, else 1000/day. This inference key has `is_free_tier=false` and per-key `limit=null` (dashboard Limit still a user click). `GET /api/v1/credits` needs `OPENROUTER_MANAGEMENT_KEY` (absent).

Free vs paid training toggles are separate in [privacy settings](https://openrouter.ai/settings/privacy). Poolside `:free` pages state they may train on free inputs/outputs. Not for secrets. Do not use `:online` (deprecated) or OpenRouter web search in place of Firecrawl/Exa/native Max.

## Low-refusal research lane (allowlisted)

`nousresearch/hermes-4-70b` — $0.13/$0.40 per M, 131K ctx, reasoning-capable, RefusalBench SOTA. Lane: low-refusal/steerable research **chat/extraction/synthesis only** — e.g. pharmacology/harm-reduction literature queries the default hosted lanes over-refuse. Allowlist before the call, as with every slug.

HARD constraints:

- **No tool calling** — the OpenRouter endpoint does not expose `tools`. Never route agentic T0/T1 (grunt-with-tools or T1 tool work) here.
- **Single provider (Nebius)** — no fallback diversity; provider-sort suffixes are no-ops.
- **Bare slug only** — no `:free` variant exists; do not append `:floor`/`:nitro`/`:exacto`.
- **Paid** — 402s while the account is overdrawn; waits on the credit top-up like the other paid slugs.
- `nousresearch/hermes-4-405b` ($1.00/$3.00) is **escalation-only** for correctness-critical steerable work, per the T0→T1 escalation rules.

Evidence: [openrouter-apps-hermes-uncensored_2026-08-27.md](openrouter-apps-hermes-uncensored_2026-08-27.md).

## Probe commands

Thin T0 script: reads `OPENROUTER_API_KEY` from the environment, sends one chat completion with app headers `HTTP-Referer` and `X-OpenRouter-Title` (`agents-openrouter-sidecar`), prints generation id plus usage, then reads spend from `GET /api/v1/generation?id=...` when an id is present. It never prints the secret. `GET /generation` can 404 for a few seconds; retry.

```powershell
# Wave 0 smoke while paid T0 is 402:
C:\Python314\python.exe C:\Users\Prekzursil\.agents\scripts\openrouter-complete.py --model liquid/lfm-2.5-2.6b:free --prompt "pong"

C:\Python314\python.exe C:\Users\Prekzursil\.agents\scripts\openrouter-complete.py --show-limits --model liquid/lfm-2.5-2.6b:free --prompt "pong"

# Paid cheap (only after credits exist):
C:\Python314\python.exe C:\Users\Prekzursil\.agents\scripts\openrouter-complete.py --prompt "Reply with the single word: pong"
```

Do not run verbose HTTP clients against these endpoints; they can echo auth headers.

## Noted, not wired (ADOPT-later)

- `openrouter:web_search` server tool exists (beta) — the `:online` replacement **if ever** needed; search stays on Firecrawl/MCP per routing decision.
- Embeddings + rerank live on a **separate** catalog (`GET /api/v1/embeddings/models`, 33 models, not in `/models`) — ADOPT-later, nothing wired.
- `session_id` sticky routing for prompt-cache hits (~10 min stickiness) — ADOPT-later.

## Related

- `cost-tracking` — OpenRouter generation ids plus the Claude SQLite tracker (label the source).
- `cost-aware-llm-pipeline` — generic routing patterns (not OpenRouter SSOT).
- Evidence: [openrouter-complete-surface_2026-08-27.md](openrouter-complete-surface_2026-08-27.md) (38-source full-surface audit) and [openrouter-free-models_2026-08-27.md](openrouter-free-models_2026-08-27.md) (free-slug catalog snapshot).