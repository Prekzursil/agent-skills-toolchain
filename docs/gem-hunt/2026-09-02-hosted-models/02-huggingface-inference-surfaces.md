# Gem-hunt lens 02 - Hugging Face inference surfaces (2026)

- Hunt: `2026-09-02-hosted-models`
- Lens id: `02-huggingface-inference-surfaces`
- Mode: discovery only. No code changed. Findings, citations, decision table, rubric.
- Author: Cursor cloud agent (Claude), 2026-09-02.
- Branch: `gemhunt/hosted-models-02-huggingface-inference-surfaces` (from `main`).

## 0. Reading guide and grading scheme

Every claim carries a grade in square brackets:

- Tier: `A` = primary source (HF docs, HF blog, HF pricing page, HF GitHub repo, HF changelog),
  `B` = secondary but reputable (provider docs, major outlets, well-maintained third-party docs),
  `C` = forum/thread/community post/inferred from behaviour.
- Corroboration: `corr` = two or more independent sources agree; `UNVERIFIED` = single source or
  not re-checked live from this sandbox.
- Date: the date the source was published or last updated, when the page states it; otherwise the
  fetch date (`f:2026-09-02`).
- Kind: `[fact]` = sourced, `[infer]` = inference from facts, `[rec]` = recommendation.

Estate locks (hard constraints, restated so no finding below can be read as violating them):

- OpenRouter is a spend-capped CLI/Codex sidecar only; never a Cursor BYOK key, never
  `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP.
- No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory.
- `auth2api` on `127.0.0.1:8317` stays the ONLY Cursor bridge; retires within 7 days of an
  official Cursor `/v1` GA. Ports 8765/8812/8317 are owned.
- `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it).
- Never rotate credentials. Never remove a feature to buy reliability; present trade-offs instead.

Dedup-set (exists; not re-proposed): `hosted-model-agents` skill (branch
`live-capture/2026-09-02`), `tools/mcp/glm53-space` (deprecation decided), `auth2api :8317`,
`.agents/agents.json` + `.agents/local.json`, the installed Windows runtimes and wrappers.

## 1. Status

Sections are appended as research lands; each section is committed and pushed on completion.

- [x] 2. router.huggingface.co/v1 (Inference Providers)
- [x] 3. Inference Endpoints (dedicated)
- [ ] 4. Spaces as inference hosts (Gradio MCP, /v1 Spaces, ZeroGPU, sleep/wake, owner recipe)
- [ ] 5. Official Hugging Face MCP server
- [ ] 6. HF token scopes
- [ ] 7. Decision table: router vs endpoint vs space vs local
- [ ] 8. Stale claims in the current `hosted-model-agents` skill
- [ ] 9. Rubric table
- [ ] 10. Ten-line summary

## 2. `router.huggingface.co/v1` (Inference Providers)

### 2.1 What it is

- `[fact][A][corr][f:2026-09-02]` The router is an OpenAI-compatible endpoint
  (`base_url=https://router.huggingface.co/v1`, `api_key=$HF_TOKEN`) that fronts a network of
  third-party inference partners. HF states it is a "drop-in replacement for the OpenAI chat
  completions API" and that the `/v1` surface is **chat completion only**; embeddings, text-to-image,
  speech and other tasks go through the `huggingface_hub.InferenceClient` / `@huggingface/inference`
  SDKs instead. Source: <https://huggingface.co/docs/inference-providers/index>.
- `[fact][A][corr][f:2026-09-02]` Requests are proxied through HF infrastructure; HF advertises
  unified auth/billing, automatic failover when a provider is flagged unavailable by HF's validation
  system (only under automatic selection), and one request format across providers. Same source.
- `[fact][A][UNVERIFIED][f:2026-09-02]` Unauthenticated `POST /v1/chat/completions` returns HTTP 401
  (probed from this sandbox). `GET /v1/models` is public (HTTP 200, no token) and returned **136**
  chat models with per-provider metadata (see 2.3). Measured here; not re-checked from a second
  network.

### 2.2 Provider routing suffixes and policies

- `[fact][A][corr][f:2026-09-02]` Model id suffix selects a **policy** or a **provider**:
  - default (no suffix) = `:fastest` = highest measured output tokens/s;
  - `:cheapest` = lowest price per output token;
  - `:preferred` = first available provider in the user's preference order at
    `hf.co/settings/inference-providers`;
  - `:<provider>` pins a provider, e.g. `openai/gpt-oss-120b:groq`,
    `deepseek-ai/DeepSeek-R1-0528:novita`, or the model author's own serving
    (`zai-org/GLM-5.3:zai-org`).
  Sources: <https://huggingface.co/docs/inference-providers/index> ("Provider Selection"),
  <https://huggingface.co/docs/inference-providers/guides/function-calling> ("Provider Selection").
- `[fact][A][UNVERIFIED][f:2026-09-02]` A second, provider-scoped base URL exists:
  `https://router.huggingface.co/<provider>/v1` (the structured-output guide uses
  `https://router.huggingface.co/cerebras/v1` with the provider-native model id `qwen-3-32b`).
  Source: <https://huggingface.co/docs/inference-providers/guides/structured-output>. Single doc page;
  not probed live.
- `[fact][A][corr][f:2026-09-02]` The Hub API exposes the provider mapping separately:
  `GET https://huggingface.co/api/models/<id>?expand[]=inferenceProviderMapping` (status `live` /
  `staging`, `providerId`, `task`), `GET .../api/models?inference_provider=<p>` to list a provider's
  models, and `hf models ls --warm [--search ...] [--inference-provider ...] [--expand inferenceProviderMapping] [--json]`
  from the `hf` CLI. Source: <https://huggingface.co/docs/inference-providers/hub-api>.
- `[infer]` The `:zai-org` suffix the hunt brief mentions is therefore not special: it is the generic
  `:<provider>` form, and `zai-org` (Z.ai) is listed as a partner that serves its own models
  (`is_model_author: true`). Any of the 14 chat providers below can be pinned the same way.

### 2.3 `GET /v1/models` - the machine-readable capability and price sheet (measured 2026-09-02)

- `[fact][A][corr][f:2026-09-02]` HF documents that each `providers[]` entry may carry `status`
  (`live`|`error`), `context_length`, `pricing` (`input`/`output` USD per million tokens), `is_free`,
  `supports_tools`, `supports_structured_output`, `first_token_latency_ms`, `throughput` (tok/s), and
  `is_model_author`; these are "the same provider performance signals shown in the provider comparison
  table" and are refreshed from HF's validation probes. Source:
  <https://huggingface.co/docs/inference-providers/hub-api> ("List OpenAI-compatible models").
- `[fact][A][UNVERIFIED][measured f:2026-09-02]` Provider census from the live `/v1/models` payload
  (136 models). Counts are models served; medians are over entries carrying probe data.

| Provider | Models | `supports_tools` | `supports_structured_output` | Median TTFT (ms) | Median tok/s |
|---|---|---|---|---|---|
| featherless-ai | 65 | 0 (field absent on all) | 0 (absent) | n/a | n/a |
| deepinfra | 64 | 61 | 47 | 473 | 36 |
| novita | 63 | 51 | 15 | 838 | 47 |
| zai-org | 21 | 21 | 0 | 1239 | 41 |
| together | 18 | 18 | 7 | 478 | 74 |
| nscale | 17 | 10 | 12 | 618 | 131 |
| fireworks-ai | 15 | 15 | 14 | 537 | 81 |
| baseten | 12 | 12 | 11 | 413 | 107 |
| cohere | 12 | 6 | 6 | 186 | 88 |
| scaleway | 8 | 8 | 7 | 372 | 97 |
| ovhcloud | 7 | 6 | 7 | 461 | 67 |
| publicai | 7 | 6 | 7 | 962 | 63 |
| groq | 3 | 3 | 3 | 347 | 670 |
| cerebras | 2 | 2 | 2 | 211 | 868 |

- `[fact][A][UNVERIFIED][measured f:2026-09-02]` All 136 x N provider entries reported `status: live`;
  **zero** entries had `is_free: true` (no promo-free chat models on the day of measurement).
- `[infer]` `featherless-ai` publishes no capability or latency fields, so a filter of the form
  "provider must report `supports_tools == true`" silently excludes 65 model listings. Treat
  Featherless as "unknown", not "no tools".
- `[fact][A][corr][f:2026-09-02]` The partner table in the index doc lists 18 partners (Baseten,
  Cerebras, Cohere, DeepInfra, Fal AI, Featherless AI, Fireworks, Groq, HF Inference, Novita, Nscale,
  OVHcloud AI Endpoints, Public AI, Replicate, Scaleway, Together, WaveSpeedAI, Z.ai). Fal,
  Replicate and WaveSpeedAI are image/video/speech only; `hf-inference` did not appear in the
  chat `/v1/models` payload at all (measured). Source: <https://huggingface.co/docs/inference-providers/index>.

### 2.4 Measured rows relevant to this estate (from `/v1/models`, f:2026-09-02)

`zai-org/GLM-5.3` (the model `glm53-space` hardcodes), text-only, 5 providers:

| Provider | $/M in | $/M out | ctx | tools | structured | TTFT ms | tok/s |
|---|---|---|---|---|---|---|---|
| novita | 1.40 | 4.40 | 1,048,576 | yes | no | 1721 | 51 |
| together | 1.40 | 4.40 | 1,048,575 | yes | no | 196 | 140 |
| fireworks-ai | (not published) | (not published) | 1,048,576 | yes | **yes** | 537 | 59 |
| zai-org (author) | (not published) | (not published) | (absent) | yes | no | 1410 | 33 |
| baseten | 1.40 | 4.40 | 1,048,576 | yes | **yes** | 634 | 87 |

`zai-org/GLM-5.3-Flash` (text+image input), 5 providers: novita **$0.075 / $0.25**, together and
baseten $0.15 / $0.50, fireworks and zai-org unpriced; baseten TTFT 206 ms at 168 tok/s with
structured output; fireworks 432 ms / 101 tok/s with structured output.

`Qwen/Qwen3.8-27B` (the base checkpoint of the owner's private Heretic Space), text+image:
deepinfra **$0.40 / $3.00**, ctx 262,144, tools + structured output, TTFT 335 ms, 40 tok/s;
featherless-ai listed without metadata.

Cheap tool-capable workhorses on the same sheet: `openai/gpt-oss-120b` on deepinfra $0.037 / $0.17
(22 tok/s), on cerebras $0.35 / $0.75 at **1039 tok/s**, on groq $0.15 / $0.75 at 422 tok/s;
`openai/gpt-oss-20b` on deepinfra $0.03 / $0.14; `google/gemma-4-31B-it` on deepinfra $0.13 / $0.38.

- `[infer]` The current `glm53-space` design (one hardcoded model, `router.huggingface.co/v1`, one
  tool) is a strict subset of what a 40-line client that reads `/v1/models` can do. The router
  already publishes the price, tool and structured-output flags per provider, so a general
  integration layer does not need its own provider table; it needs a **policy** (pin
  `:fireworks-ai` or `:baseten` when `response_format` is used, `:cheapest` for bulk, `:fastest`
  default) and a cache of `/v1/models`.
- `[infer]` Because `zai-org` (the author) reports `supports_structured_output: false` for every
  GLM-5.3 variant, a client that hardcodes `:zai-org` and later adds JSON-schema output will fail on
  a documented capability gap, not on a bug.

### 2.5 Pricing, credits, quotas

- `[fact][A][corr][f:2026-09-02]` No markup: "Hugging Face charges you the same rates as the
  provider." Monthly credits: Free **$0.10** ("subject to change"), PRO **$2.00**, Team/Enterprise
  **$2.00 per seat**. PRO/Team/Enterprise credits are general-purpose compute credits usable on
  Inference Providers, Inference Endpoints, upgraded Spaces hardware (including ZeroGPU beyond
  quota) and Jobs; they apply before pay-as-you-go. Free users can continue after the credits only by
  purchasing credits. Source: <https://huggingface.co/docs/inference-providers/pricing>.
- `[fact][A][corr][f:2026-09-02]` Two billing modes: HF-routed (billed by HF, credits apply) vs
  **custom provider key** set in HF settings or in the SDK (billed by the provider, credits do not
  apply, code unchanged - HF swaps the auth on the way through). Same source.
- `[fact][A][corr][f:2026-09-02]` Org billing via header `X-HF-Bill-To: <org>` (or `bill_to=` in
  `InferenceClient`); Enterprise resource-group ids also accepted; org admins can set spending limits
  and disable providers. Same source.
- `[fact][A][corr][f:2026-09-02]` `hf-inference` (the old "Inference API (serverless)") is billed by
  compute-seconds x hardware price and "as of July 2025 ... focuses mostly on CPU inference"
  (embeddings, rerankers, classifiers, small historical LLMs). Same source.
- `[fact][A][UNVERIFIED][f:2026-09-02]` Explicit per-plan **request rate limits for the router** are
  not stated on the pricing page; the pricing model is credits then pay-as-you-go. See 2.7 for the
  Hub-wide rate-limit page.
- `[infer]` For a single-owner estate on a PRO plan, the practical monthly ceiling of "free" router
  usage is $2.00 of credits, i.e. roughly 450k output tokens of `GLM-5.3` at $4.40/M or about
  13 M output tokens of `gpt-oss-120b:deepinfra` at $0.17/M before pay-as-you-go starts.

### 2.6 Tool calling and JSON mode across providers

- `[fact][A][corr][f:2026-09-02]` OpenAI-style `tools` + `tool_choice` (`auto` | `required` |
  `{type: function, function: {name}}`) are supported on the router; **strict mode**
  (`"strict": true` plus `"additionalProperties": false`) and **streaming with tool calls** are
  documented as "not supported by all providers". HF's own `InferenceClient` does not support the
  named-function `tool_choice` form. Source:
  <https://huggingface.co/docs/inference-providers/guides/function-calling>.
- `[fact][A][corr][f:2026-09-02]` Structured output uses `response_format = {type: "json_schema",
  json_schema: {name, schema, strict: true}}`; HF explicitly advises pinning a specific provider
  and model for structured output "to avoid incompatibility issues between the model, provider and
  the schema". Source: <https://huggingface.co/docs/inference-providers/guides/structured-output>.
- `[fact][A][UNVERIFIED][measured f:2026-09-02]` The per-provider truth table is the `supports_tools`
  / `supports_structured_output` pair in `/v1/models` (2.3). Providers that report structured output
  on most of their catalogue: fireworks-ai (14/15), baseten (11/12), scaleway (7/8), ovhcloud (7/7),
  publicai (7/7), groq (3/3), cerebras (2/2), deepinfra (47/64). Providers that mostly do not:
  novita (15/63), together (7/18), zai-org (0/21).
- `[rec]` For the estate's tool loop (`hosted-model-agents/tool-loop.md`), the safe rule is:
  `tools` -> any provider with `supports_tools`; `response_format json_schema` -> pin a provider
  with `supports_structured_output` (fireworks-ai / baseten / deepinfra for GLM and Qwen families);
  never rely on `:fastest` when a schema is attached, because the fastest provider for GLM-5.3
  (together, 140 tok/s) reports **no** structured-output support.

### 2.7 Hub-wide rate limits (context for the router)

- `[fact][A][corr][page dated "September '25", f:2026-09-02]` The Hub enforces three buckets over
  **5-minute fixed windows**: Hub API, Resolvers (`/resolve/` file downloads), Pages. Tiers:
  Anonymous 500 / 3,000 / 100; Free 1,000 / 5,000 / 200; **PRO 2,500 / 12,000 / 400**; Team
  3,000 / 20,000 / 400; Enterprise 6,000 / 50,000 / 600; Enterprise Plus 10,000 / 100,000 / 1,000
  (100,000 / 500,000 / 10,000 with "Higher Hub Rate Limits"). Anonymous and Free values are
  "subject to change ... depending on platform health". Org limits apply per member, not shared.
  Source: <https://huggingface.co/docs/hub/rate-limits>.
- `[fact][A][corr][f:2026-09-02]` On 429 the Hub returns IETF `draft-ietf-httpapi-ratelimit-headers`
  v9 headers `RateLimit: "api|pages|resolvers";r=<remaining>;t=<seconds-to-reset>` and
  `RateLimit-Policy`. `huggingface_hub >= 1.2.0` parses them and sleeps exactly until reset for
  downloads and paginated list calls. Same source.
- `[fact][A][corr][f:2026-09-02]` HF's stated number-one cause of throttling is requests without
  `HF_TOKEN`; the stated remedies are spacing requests, preferring Resolver URLs over API calls, or
  upgrading. Same source.
- `[infer]` The router (`router.huggingface.co`) is not one of the three named buckets on that
  page, and the pricing page gives no request-per-minute figure for it; the practical router ceiling
  is therefore **credits then pay-as-you-go**, with each partner's own concurrency limits behind the
  proxy (which HF's failover is designed to mask under `:fastest`/auto but **not** under a pinned
  `:<provider>` suffix). This should be stated in the skill as an open question, not a number.
- `[rec]` Any estate client that talks to both `huggingface.co/api/*` (Hub MCP, `hf models ls`) and
  the router should honour `RateLimit` headers and pass the token everywhere; the estate already
  centralises the token name (`HUGGINGFACE_TOKEN`) in `.agents/local.json`, so this is a code-path
  rule, not a secrets change.

### 2.8 Official "Quick Setup for Agents" integrations (new since the skill was written)

- `[fact][A][corr][f:2026-09-02]` The Inference Providers index now carries a "Quick Setup for
  Agents" block with per-tool guides at `docs/inference-providers/integrations/{opencode, pi,
  codex, claude-code, hermes-agent, datadesigner, macwhisper, visionagents, vscode}`, and the
  guides section gained `guides/responses-api`, `guides/gpt-oss`, `guides/coding-environment`
  ("Agentic Coding Environments with OpenEnv"), `guides/evaluation-inspect-ai` and
  `guides/github-actions-code-review`. Sources: rendered index
  <https://huggingface.co/docs/inference-providers/index>; navigation
  <https://github.com/huggingface/hub-docs/blob/main/docs/inference-providers/_toctree.yml>.
- `[infer]` Three of the estate's installed runtimes (Codex, Claude Code, OpenCode) are now
  first-party-documented router consumers. Section 8 examines whether the estate locks permit
  each one (the Claude Code path implies a base-URL swap, which the OpenRouter lock forbids for
  OpenRouter and which the same reasoning should be applied to for HF - see 8.x).

## 3. Inference Endpoints (dedicated)

- `[fact][A][corr][f:2026-09-02]` Dedicated Endpoints bill an hourly instance rate, metered per
  minute, only while the endpoint is initializing or running; requires an active subscription and a
  card on file. Formula: `rate * ((hours * min_replicas) + (scale_up_hours * extra_replicas))`.
  Source: <https://huggingface.co/docs/inference-endpoints/pricing>.
- `[fact][A][corr][f:2026-09-02]` GPU price points relevant to a 27B-class model (AWS unless noted):
  T4 16 GB $0.50/h; L4 24 GB $0.80/h (GCP $0.70); A10G 24 GB $1.00/h; **L40S 48 GB $1.80/h**;
  A100 80 GB $2.50/h (GCP $3.60); H200 141 GB $5.00/h; GCP H100 80 GB $10.00/h. CPU
  intel-spr x2 (2 vCPU, 4 GB) $0.067/h. Same source.
- `[fact][A][corr][f:2026-09-02]` Scale-to-zero: idle timeout default **1 hour**; while a replica
  cold-starts the proxy returns **503**, unless the client sends `X-Scale-Up-Timeout: <seconds>`
  (e.g. 600), in which case the proxy holds the request until ready or timeout. HF's own guidance:
  "scaling up can take a few minutes depending on the model ... scaling from 0 to 1 based on a
  request is typically not recommended if your application needs to be responsive." Autoscaling
  signals: hardware utilisation (80% default, scale-up evaluated every minute, scale-down every 2
  minutes, 300 s stabilisation) or pending requests (>1.5 per replica over 20 s). Source:
  <https://huggingface.co/docs/inference-endpoints/guides/autoscaling>.
- `[fact][A][corr][f:2026-09-02]` Quotas: instance quota is shown in the Endpoints dashboard;
  **paused** endpoints do not consume quota, **scaled-to-zero endpoints do**; PRO and Enterprise can
  request higher quota. Source: <https://huggingface.co/docs/inference-endpoints/pricing>.
- `[fact][A][corr][f:2026-09-02]` PRO/Team/Enterprise monthly credits ($2 / $2 per seat) may be spent
  on Endpoints. Source: <https://huggingface.co/docs/inference-providers/pricing>.
- `[infer]` Cost picture for the estate's private Heretic checkpoint (Qwen3.8-27B class, needs
  roughly 48 GB in bf16 or 24 GB in 4-bit): an always-on L40S is ~$1,314/month (730 h x $1.80);
  the same box scale-to-zero with a 1 h idle window costs $1.80 per wake-hour plus a multi-minute
  cold start and a 503-or-hold client contract. Versus ZeroGPU (section 4): $0 up to the daily quota
  and $6/GPU-hour beyond it, but shared queueing and a 60-s default per-call GPU budget. Versus the
  router: the *base* Qwen3.8-27B is $0.40/$3.00 per M tokens on deepinfra with no fixed cost, but
  the abliterated fine-tune is not on the router at all.
- `[rec]` An Endpoint is only the right surface for this estate when (a) the checkpoint is not on
  the router, (b) usage is bursty-but-long (hours per session, not one call per hour), and (c) the
  client is prepared to send `X-Scale-Up-Timeout` and treat 503 as "warming". None of those is true
  of the glm53 use case (GLM-5.3 is on five router providers), so the Endpoint column of the
  decision table is "reserved for private checkpoints under sustained load".
