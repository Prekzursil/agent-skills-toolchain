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

Method and limits of this lens:

- Sources were fetched live on 2026-09-02 from `huggingface.co/docs/*`, `router.huggingface.co`,
  `huggingface.co/api/*`, `huggingface.co/mcp/server-card`, and the `huggingface/hub-docs`,
  `evalstate/hf-mcp-server` and `gradio-app/gradio` GitHub sources. All are primary (tier A) except
  where marked.
- The sandbox had **no HF token**, so every authenticated surface (a real chat completion, the
  Hub MCP `tools/list`, the private Space's runtime state, ZeroGPU wake latency) is reported as
  documented or UNVERIFIED, never as measured. Unauthenticated probes (`/v1/models`, 401 on
  `/v1/chat/completions`, Space and model metadata) are labelled `measured`.
- The `tools/mcp/glm53-space` directory is registered in `.agents/agents.json` on `main` but its
  files are not present in this checkout (Windows path `C:\Users\Prekzursil\source\...`); the
  hunt brief's description of it (one tool, hardcoded `zai-org/GLM-5.3`) is taken as given.
- Prices and quotas are quoted as published on the fetch date; HF marks several as "subject to
  change".

## 1. Status

Sections are appended as research lands; each section is committed and pushed on completion.

- [x] 2. router.huggingface.co/v1 (Inference Providers)
- [x] 3. Inference Endpoints (dedicated)
- [x] 4. Spaces as inference hosts (Gradio MCP, /v1 Spaces, ZeroGPU, sleep/wake, owner recipe)
- [x] 5. Official Hugging Face MCP server
- [x] 6. HF token scopes
- [x] 7. Decision table: router vs endpoint vs space vs local
- [x] 8. Stale claims in the current `hosted-model-agents` skill
- [x] 9. Rubric table
- [x] 10. Ten-line summary

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
  12 M output tokens of `gpt-oss-120b:deepinfra` at $0.17/M before pay-as-you-go starts
  (input tokens not counted; both figures are upper bounds).

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
  OpenRouter and which the same reasoning should be applied to for HF - see S13 in section 8).

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

## 4. Spaces as inference hosts

### 4.1 ZeroGPU (what the owner's private Space runs on)

- `[fact][A][corr][f:2026-09-02]` ZeroGPU now allocates **NVIDIA RTX Pro 6000 Blackwell** slices:
  `large` (default) = half card, 48 GB VRAM, 1x quota; `xlarge` = full card, 96 GB, 2x quota.
  Gradio SDK only; Gradio 4+; PyTorch 2.8.0+ (2.8.0, 2.9.1, 2.10.0, 2.11.0); Python 3.12.12 or
  3.10.13; `torch.compile` unsupported (AoT compilation is). Source:
  <https://huggingface.co/docs/hub/spaces-zerogpu>.
- `[fact][A][corr][f:2026-09-02]` Daily GPU quota per **caller** (not per Space): unauthenticated
  2 min, Free 5 min, **PRO 40 min** (extensible), Team member 40 min, Enterprise member 60 min;
  resets 24 h after first use; remaining quota drives queue priority; PRO/Team/Enterprise can exceed
  quota on pre-paid credits at **$1 per 10 GPU-minutes** ($6/GPU-hour). Hosting caps: Free 2
  ZeroGPU Spaces (account >30 days, verified email), **PRO 10**, Team/Enterprise org 50. Same source.
- `[fact][A][corr][f:2026-09-02]` `@spaces.GPU` default runtime budget is **60 s** per call,
  overridable with `duration=` (static or a callable of the inputs); shorter declared durations get
  better queue priority; models must be moved to `cuda` at module import (CUDA emulation outside the
  decorated function), lazy-loading inside `@spaces.GPU` is "significantly less efficient". Same source.
- `[fact][A][UNVERIFIED][measured f:2026-09-02]` The owner's public Space `Prekzursil/GLM-5.3`
  (Gradio `6.26.0`, `hf_oauth: true`, scopes `inference-api` + `write-repos`, created 2026-08-30) is in
  `runtime.stage = RUNTIME_ERROR` with `errorMessage: "No @spaces.GPU function detected during
  startup"` and `hardware.requested = zero-a10g`, `hardware.current = null`. Probe:
  `GET https://huggingface.co/api/spaces/Prekzursil/GLM-5.3`.
- `[infer]` That Space is a router *client* (a GLM-5.3 chat front-end), not a model host, so it has no
  GPU function to decorate; requesting ZeroGPU hardware for it cannot succeed. The fix is a hardware
  change to `cpu-basic` in Space settings (free, sleeps after 48 h idle), not code. It is also a live
  example of why "Space" and "router" must not be conflated in the skill's environments table.
- `[fact][A][UNVERIFIED][f:2026-09-02]` The private Space `Prekzursil/qwen38-27b-heretic-chat` returns
  HTTP 401 to an unauthenticated `GET /api/spaces/...` (expected for a private repo); its runtime state
  could not be read from this sandbox.

### 4.2 Paid Space hardware, sleep and wake

- `[fact][A][corr][f:2026-09-02]` Spaces hardware prices (per hour, billed per minute, only while
  `Starting`/`Running`): CPU Basic (2 vCPU, 16 GB) free but "creating a new Space that runs on compute
  (Gradio or Docker) requires a paid plan"; CPU Upgrade $0.03; T4-small $0.40; T4-medium $0.60;
  1x L4 $0.80; 1x L40S (48 GB) $1.80; A10G-small $1.00; A10G-large $1.50; A100-large $2.50;
  4x A100 $10; 8x A100 $20. **H100 and 8x H100 removed December 2025.** Source:
  <https://huggingface.co/docs/hub/spaces-gpus>.
- `[fact][A][corr][f:2026-09-02]` Sleep: `cpu-basic` Spaces sleep after **48 h** idle and any visitor
  restarts them; upgraded Spaces never sleep by default but accept a custom sleep time (no billing
  while `stopped`, wake on next visitor); `pause` stops billing and only the owner can restart.
  Replicas (paid hardware only, billed each) via `POST /api/spaces/{ns}/{repo}/replicas`. Same source.
- `[fact][A][corr][f:2026-09-02]` Space observability endpoints (authenticated SSE):
  `GET /api/spaces/{ns}/{repo}/logs/{build|run}?tail=N`, `/events`, `/metrics`. Same source.
- `[fact][A][UNVERIFIED][f:2026-09-02]` HF does not publish a wake-latency figure for sleeping Spaces;
  the only documented latency statements are the ZeroGPU 60-s per-call budget and the Endpoints "a few
  minutes" cold start. A measured wake time for the owner's private Space is therefore an **open
  measurement** for the skill's evals, not a fact this lens can cite.

### 4.3 Gradio MCP server mode (`mcp_server=True`)

- `[fact][A][corr][f:2026-09-02]` `pip install "gradio[mcp]"`, then `demo.launch(mcp_server=True)` or
  `GRADIO_MCP_SERVER=True`. Every API endpoint becomes an MCP tool (name = function name, description
  and schema from docstring + type hints, component defaults = argument defaults). Transport is
  **Streamable HTTP** at `<host>/gradio_api/mcp/` (schema at `/gradio_api/mcp/schema`); clients that
  lack streamable-HTTP support can bridge with `npx mcp-remote <url>`. Source:
  <https://github.com/gradio-app/gradio/blob/main/guides/10_mcp/01_building-mcp-server-with-gradio.md>
  (rendered at <https://www.gradio.app/guides/building-mcp-server-with-gradio>).
- `[fact][A][corr][f:2026-09-02]` Private Spaces and "a ZeroGPU Space with your own quota" are used
  as MCP servers by adding `"headers": {"Authorization": "Bearer <HF_TOKEN>"}` to the client config;
  `gr.Header` / `gr.Request` let the tool read caller headers; `queue=False` on handlers can raise
  throughput "by as much as 10 times" at the cost of progress notifications. Same source.
- `[infer]` For the estate this confirms the skill's existing rule (Gradio MCP = *that app's* tools,
  not Hub): a ZeroGPU chat Space exposed as MCP would put a `generate` tool on every turn of every
  agent that mounts it, which `mcp-fleet-curation` forbids. It is the right shape only for a
  narrow, side-effect-free tool (e.g. an OCR or a transcription Space), not for chat.

### 4.4 The Heretic checkpoint is already on the router (new)

- `[fact][A][UNVERIFIED][measured f:2026-09-02]` `GET https://huggingface.co/api/models/heretic-org/Qwen3.8-27B-heretic-ara?expand[]=inferenceProviderMapping&expand[]=inference`
  returns `inference: "warm"` and `inferenceProviderMapping: {"featherless-ai": {status: "live",
  providerId: "heretic-org/Qwen3.8-27B-heretic-ara", task: "conversational"}}`; safetensors total
  27,356,728,560 parameters. A Hub search for `Qwen3.8-27B-heretic` returned 20 repos including
  `trohrbaugh/Qwen3.8-27B-heretic-ara`, several NVFP4/INT8/GGUF quantisations and abliterated
  variants.
- `[infer]` The `hosted-model-agents` recipe describes the private Space checkpoint as "Qwen3.8-27B
  Heretic-ARA". If it is the `heretic-org` (or an equivalent) upload, the same weights are callable
  today as `heretic-org/Qwen3.8-27B-heretic-ara:featherless-ai` through `router.huggingface.co/v1`
  with no GPU quota, no sleep/wake and no `@spaces.GPU` 60-s budget. Three caveats keep this
  UNVERIFIED: (1) featherless-ai publishes no `supports_tools` / `supports_structured_output` /
  latency probe data (section 2.3), so OpenAI `tool_calls` from that route must be tested, not
  assumed; (2) this model id is **not** in the 136-row `/v1/models` payload, so the router's
  `:fastest`/`:cheapest` policies have nothing to choose between (pin `:featherless-ai`); (3) whether
  the owner's Space uses this exact revision (and its chat template with the `xhigh` reasoning alias)
  cannot be read from the private repo.
- `[rec]` Add to the skill's evals a 5-line probe: `POST /v1/chat/completions` with
  `model: heretic-org/Qwen3.8-27B-heretic-ara:featherless-ai`, one `tools` entry and
  `tool_choice: required`; record whether `tool_calls` come back well-formed. If yes, the private
  ZeroGPU Space becomes the **fallback**, not the primary, for that persona - a trade-off (lose
  control of template/quantisation; gain zero-ops availability), not a removal.

## 5. Official Hugging Face MCP server (`https://huggingface.co/mcp`)

- `[fact][A][corr][f:2026-09-02]` The public server card at `https://huggingface.co/mcp/server-card`
  reports `name: huggingface.co/mcp`, **version 0.4.15**, one remote of type `streamable-http` at
  `https://huggingface.co/mcp`. Measured here; schema
  `https://static.modelcontextprotocol.io/schemas/v1/server-card.schema.json`.
- `[fact][A][corr][f:2026-09-02]` Source repo `evalstate/hf-mcp-server`: transports STDIO and
  Streamable HTTP in **stateless JSON mode**; `?login` URL variant for OAuth (Claude Code:
  `claude mcp add hf-mcp-server -t http https://huggingface.co/mcp?login`; Gemini CLI:
  `gemini mcp add -t http huggingface https://huggingface.co/mcp?login`), or a
  `Authorization: Bearer <HF_TOKEN>` header (Cursor/VS Code snippets); per-user tool and Space
  selection at `https://huggingface.co/settings/mcp`; `?no_image_content=true` strips Gradio
  ImageContent; `?bouquet=openai` exposes "Hub filesystem, repository search and details, dynamic
  Space, Jobs, and sandbox tools" (Jobs/dynamic Space/sandbox require auth); `DISABLE_TOOLS`
  example names `hub_repo_search,hf_fs`; local run `npx @llmindset/hf-mcp-server` (STDIO) or
  `npx @llmindset/hf-mcp-server-http`, Docker `ghcr.io/evalstate/hf-mcp-server:latest` on port 3000.
  Source: <https://github.com/evalstate/hf-mcp-server/blob/main/README.md>.
- `[fact][A][corr][f:2026-09-02]` The HTTP server also implements the **SEP-2640 skills** surface
  (`skills/list`, `skills/get`, `resources/read`, capability `io.modelcontextprotocol/skills`) from a
  digest-verified snapshot of `hf://buckets/huggingface/skills`; skills are not exposed over STDIO.
  Same source.
- `[fact][A][UNVERIFIED][measured f:2026-09-02]` An anonymous JSON-RPC `tools/list` to
  `https://huggingface.co/mcp` returned HTTP 400 `{"code": -32600, "message": "Session ID required"}`;
  the canonical tool list therefore cannot be enumerated without a token from this sandbox. The
  skill should not hard-code tool names; the per-user list is configured server-side.
- `[infer]` Two things in this server are new relative to the estate's skill: (1) **Jobs, dynamic
  Space and sandbox tools** behind `?bouquet=openai` - the Hub MCP can now launch Gradio Space tools
  and HF Jobs, i.e. it edges into the *runtime* layer the skill keeps separate; (2) the **skills
  bucket** (`hf://buckets/huggingface/skills`) is a second SSOT of prompt packs that Claude Code /
  Cursor will see if the HTTP transport is mounted - a direct tension with the estate lock
  ".agents/skills is the ONE prompt SSOT". Section 8 records this as a stale-claim + lock-check item.
- `[infer]` The estate's `agents.json` entry (`transport: http`, `url: https://huggingface.co/mcp?login`,
  `targets: [claude]`, `x_codex.bearer_token_env_var: HUGGINGFACE_TOKEN`) is consistent with the
  README; the only correction is that `?login` (OAuth) and `Authorization: Bearer` are alternatives,
  and Codex's bearer path does not need `?login`.

## 6. HF token scopes

- `[fact][A][corr][f:2026-09-02]` Three token roles: `fine-grained` (per-resource, recommended for
  production, shareable inside an org without exposing the account), `read` (read public + private
  repos the user can read; HF's own text says this is enough "when downloading private models or
  doing inference"), `write` (adds push). Best practice: one token per app/machine; leaked tokens
  can be invalidated by anyone via `POST https://huggingface.co/api/credentials/revoke` (always 202,
  owner emailed). Source: <https://huggingface.co/docs/hub/security-tokens>.
- `[fact][A][corr][f:2026-09-02]` The router-specific permission is the fine-grained checkbox
  **"Make calls to Inference Providers"** (named identically in the Providers index, the Codex,
  Claude Code and Responses guides). Sources:
  <https://huggingface.co/docs/inference-providers/index>,
  <https://huggingface.co/docs/inference-providers/integrations/codex>,
  <https://huggingface.co/docs/inference-providers/guides/responses-api>.
- `[fact][A][corr][f:2026-09-02]` OAuth (Space "Sign in with HF") scopes are a separate vocabulary:
  `openid`, `profile`, `email`, `read-billing`, `read-repos`, `gated-repos`, `write-repos`,
  `manage-repos`, `inference-api` ("Make inference requests to Inference Providers on behalf of the
  user"), `jobs`, `webhooks`, `write-discussions`. Source:
  <https://github.com/huggingface/hub-docs/blob/main/docs/hub/oauth.md> (rendered
  <https://huggingface.co/docs/hub/oauth>).
- `[fact][A][corr][f:2026-09-02]` Team/Enterprise orgs can require admin approval of fine-grained
  tokens (Pending -> approved/denied, `403` when denied), revoke org access permanently, or reject
  classic read/write tokens (`403`). CI can avoid stored tokens entirely via **Trusted Publishers**
  (OIDC -> short-lived Hub token, repo- or user-scoped). Source:
  <https://huggingface.co/docs/hub/security-tokens>.
- `[fact][A][corr][f:2026-09-02]` Routing security: HF states it does not store request/response
  bodies, keeps debug logs up to 30 days without user data or tokens, TLS in transit, Hub is SOC2
  Type 2; provider-side policies apply downstream. Source:
  <https://huggingface.co/docs/inference-providers/security>.
- `[infer]` The estate's single `HUGGINGFACE_TOKEN` name (in `.agents/local.json`, referenced by
  `agents.json` for both `huggingface` MCP and `glm53-space`) is doing at least three jobs today: Hub
  MCP (read/search/Spaces CRUD), router inference (needs the "Make calls to Inference Providers"
  permission), and private-Space Bearer auth. HF's own best practice is one token per usage. This
  is not a rotation (forbidden by the locks); it is a **split by name** the owner may choose to do
  later - e.g. a fine-grained inference-only token for wrappers, keeping the current token for Hub
  ops. Present as trade-off: blast radius vs one more secret to keep in `.agents/local.json`.
- `[rec]` Whatever token the router wrappers use, it must carry "Make calls to Inference Providers";
  a classic `read` token works per HF text but cannot be narrowed, so the general integration layer
  should fail with a clear message on 401/403 rather than fall back to another surface.

## 7. Decision table - router vs Endpoint vs Space vs local

All rows are for a chat model that must emit OpenAI `tool_calls` to a **local** harness (the
skill's hard rule 3). "Measured" = read from `/v1/models` or probed on 2026-09-02; "documented" =
HF docs; "open" = neither.

| Surface | When to use | Latency | Cost | Capability | Ops burden |
|---|---|---|---|---|---|
| **Router `/v1`** (`router.huggingface.co/v1`) | Model is in `/v1/models` or has a live `inferenceProviderMapping`; need tools/JSON; want zero fixed cost | Measured TTFT 200-1700 ms by provider (GLM-5.3: together 196 ms, fireworks 537 ms, baseten 634 ms, zai-org 1410 ms, novita 1721 ms); 22-1039 tok/s | Pass-through per-token; GLM-5.3 $1.40/$4.40 per M; GLM-5.3-Flash from $0.075/$0.25; gpt-oss-120b from $0.037/$0.17; $2/month PRO credits then PAYG | `tools` broadly; `response_format` only where `supports_structured_output` (fireworks/baseten/deepinfra for GLM/Qwen); Responses API beta incl. remote MCP + `reasoning.effort`; no Hub file access | None; must honour 401/429; pin provider for schemas |
| **Inference Endpoint** (dedicated) | Private checkpoint not on router AND sustained hourly load AND client can wait/hold | Documented: cold start "a few minutes", 503 or `X-Scale-Up-Timeout` hold; warm = provider-class | L4 $0.80/h, L40S $1.80/h, A100 $2.50/h; scale-to-zero idle 1 h default; scaled-to-zero still counts against quota | Full control of engine (TGI/vLLM), template, quantisation; standard `/v1` | Highest: quota, autoscaling, card on file |
| **Space - ZeroGPU** (owner's private Heretic recipe) | Private/abliterated checkpoint; bursty, low volume; PRO account | Open (no HF wake-latency figure); per-call GPU budget 60 s default; queue priority tied to remaining quota | $0 to 40 min/day GPU (PRO), then $6/GPU-h; 10 ZeroGPU Spaces cap | Any Gradio 4+/PyTorch 2.8+ app; you own `/v1` shim, template fixes (`xhigh` alias, dict `arguments`); Bearer auth for private | Medium: keep `@spaces.GPU` only on `generate`; 48 GB (large) / 96 GB (xlarge) VRAM |
| **Space - paid GPU** | Need always-warm private model without Endpoint quota dance | Wake on visit if sleep set (open latency); warm otherwise | Same per-hour as Endpoints (L40S $1.80/h), billed per minute while Running; sleep stops billing | Same as ZeroGPU without 60-s budget | Medium |
| **Space - Gradio MCP** | Expose *one* narrow side-effect-free app tool to agents | Same as underlying Space | Same as underlying Space | Streamable HTTP MCP at `/gradio_api/mcp/`; Bearer for private/ZeroGPU quota | Low, but tool-catalogue cost on every turn (`mcp-fleet-curation`) |
| **Local** (llama.cpp / LM Studio / Ollama on the 31.6 GB, no-GPU Windows box) | Offline, private, small models only | CPU-bound; a 27B model in 4-bit needs ~16 GB RAM and is impractical on a memory-starved host | $0 | Full control; OpenAI `/v1` on localhost | RAM contention with the agent fleet (G-36) |

- `[rec]` Default for **any model that appears in `/v1/models` or has a live provider mapping**:
  router, with `:fastest` for interactive, `:cheapest` for bulk, an explicit
  `:<provider>` whenever `response_format` is attached. Endpoint only for private checkpoints under
  sustained load. ZeroGPU Space for private checkpoints under bursty load (today's Heretic recipe),
  re-evaluated against the featherless route (4.4). Local only when the box is otherwise idle.

## 8. Stale or incomplete statements in the current `hosted-model-agents` skill

Checked against `skills/hosted-model-agents/{SKILL.md, environments.md, tool-loop.md, evals.md,
recipes/hf-space-openai.md}` on branch `live-capture/2026-09-02` (`valid_as_of: 2026-08-29`).

| # | Skill text (paraphrased) | Status now | Evidence |
|---|---|---|---|
| S1 | Environments table lists Hub MCP, Space Gradio UI, Space `/v1`, Endpoints/TGI/vLLM, Jobs. **The router (`router.huggingface.co/v1`, Inference Providers) is absent** from the HF section. | **Stale/missing.** The router is the cheapest, lowest-ops HF runtime and the one `glm53-space` already uses. | Section 2; `agents.json` `glm53-space` description |
| S2 | "Optional `mcp_server=True` on Gradio 6+" | **Inaccurate version.** Gradio MCP mode is documented for Gradio 4+ (`gradio[mcp]`); the owner's Spaces run 6.26.0. | Gradio guide (4.3); Space card `sdk_version: 6.26.0` |
| S3 | "Private Spaces need Bearer token" | Still true; add that ZeroGPU quota is **the caller's** (Bearer decides whose 40 min is spent) and that Gradio MCP mode accepts the same header. | ZeroGPU doc; Gradio guide |
| S4 | Recipe: "Qwen3.8-27B Heretic-ARA, ZeroGPU" as the private Space checkpoint, implied to require self-hosting | **Possibly superseded.** `heretic-org/Qwen3.8-27B-heretic-ara` is `warm` on featherless-ai via the router. Tool-calling on that route UNVERIFIED. | Section 4.4 |
| S5 | ZeroGPU implicitly described as A10G-class (`zero-a10g` still the requested hardware id on the owner's Space) | **Stale hardware.** ZeroGPU is now RTX Pro 6000 Blackwell, 48 GB `large` / 96 GB `xlarge`; PyTorch 2.8+ only; `torch.compile` unsupported. | ZeroGPU doc (4.1) |
| S6 | No statement of ZeroGPU quotas, per-call duration, or credit overage | **Missing.** PRO 40 min/day, 60-s default budget, $1/10 min overage, 10-Space cap. | ZeroGPU doc |
| S7 | Endpoints row says "Dedicated GPU, OpenAI `/v1`" only | **Missing** scale-to-zero semantics (1 h idle, 503 vs `X-Scale-Up-Timeout`, quota counted while scaled to zero) and prices. | Section 3 |
| S8 | "Hub MCP lists Hub operations, not `read_file` on the owner's disk" | Still true, but **incomplete**: the official server now also exposes Jobs, dynamic Space tools, a sandbox (`?bouquet=openai`) and a SEP-2640 **skills** surface. The layer boundary the skill draws has moved. | Section 5 |
| S9 | `agents.json` `huggingface` URL `https://huggingface.co/mcp?login` for Claude, bearer for Codex | Consistent; note `?login` is OAuth and unnecessary when a Bearer header is sent. | README (5) |
| S10 | Tool loop: "Streaming: SSE `data:` chunks then `[DONE]`" | Still true for `/v1/chat/completions`; **missing** that `/v1/responses` (beta) exists with event streaming, `reasoning.effort`, `response_format`, and remote MCP tool execution *on the router side* - which is exactly the "remote executes tools" pattern the skill's rule 3 forbids and must be explicitly opted out of. | Responses guide |
| S11 | No mention of provider-pinning suffixes or of `/v1/models` capability flags | **Missing.** `:fastest`/`:cheapest`/`:preferred`/`:<provider>`; `supports_tools`, `supports_structured_output`, pricing, TTFT in `/v1/models`. | Section 2.2-2.3 |
| S12 | No mention of Hub rate-limit tiers | **Missing.** PRO 2,500 API / 12,000 resolvers / 400 pages per 5 min; IETF `RateLimit` headers. | Section 2.7 |
| S13 | "Cursor Max / Claude Max ... G-32 ... Do not conflate with HF" | Still right, and now sharper: HF publishes first-party Claude Code and Codex guides that **repoint `ANTHROPIC_BASE_URL` / add a Codex `model_providers.huggingface`**. The estate lock forbids `ANTHROPIC_BASE_URL` for OpenRouter; the same reasoning (Claude Code identity/quotas must not be silently swapped) applies to HF. Codex's per-profile provider (`codex --profile huggingface`) is process-local and does not touch the Cursor bridge, so it is lock-compatible **as a sidecar**, mirroring the OpenRouter posture. | Section 2.8; integration guides |
| S14 | `glm53-space` registered in `agents.json` as a stdio MCP with one tool | Owner has decided to deprecate; this lens confirms the replacement should be a router client with policy suffixes and `/v1/models`-driven capability checks, not another MCP. The public Space `Prekzursil/GLM-5.3` that fronts the same idea is in `RUNTIME_ERROR` (wrong hardware). | Sections 2.4, 4.1 |
| S15 | Spaces hardware price list (if any copy exists in recipes) | H100 / 8x H100 Spaces hardware **removed December 2025**. | Spaces GPU doc |

## 9. Rubric table

Columns: name | what | why THIS estate | how to build or adopt | source | value x effort | novelty-for-us | NATIVE-vs-BUILD.

| Name | What | Why THIS estate | How to build or adopt | Source | Value x effort | Novelty-for-us | NATIVE-vs-BUILD |
|---|---|---|---|---|---|---|---|
| F1 `/v1/models` as the provider table | Public JSON with per-provider price, ctx, tools, structured-output, TTFT, tok/s for 136 chat models | Replaces any hand-kept provider table in the glm53 successor; lets wrappers refuse `response_format` on providers that report `false` | Cache the payload (TTL hours) in the general integration layer; select by policy; log `provider` chosen | <https://huggingface.co/docs/inference-providers/hub-api>; measured | High x Low | New (skill has no mention) | NATIVE (HF publishes it) |
| F2 Policy suffixes `:fastest` / `:cheapest` / `:preferred` / `:<provider>` | Server-side routing knob in the model id | Zero-code routing for Goose/Fabric/aider profiles that read `.agents/skills`; `:preferred` order set once at `hf.co/settings/inference-providers` | Document in skill; expose as a wrapper flag; pin provider when schema attached | <https://huggingface.co/docs/inference-providers/index> | High x Low | New | NATIVE |
| F3 Heretic-ARA on featherless via router | `heretic-org/Qwen3.8-27B-heretic-ara` is `warm`/`live` on featherless-ai | Could demote the private ZeroGPU Space to fallback; removes 60-s budget and quota | 5-line probe with `tools` + `tool_choice: required`; compare template behaviour with the Space | Hub API probe (4.4) | High x Low (probe) / Medium (adopt) | New | NATIVE, UNVERIFIED for tools |
| F4 Responses API beta on router | `/v1/responses` with event streaming, `reasoning.effort`, `response_format`, remote MCP | Codex requires `wire_api = "responses"`; also the one place where HF would execute tools remotely - must be opted out to keep rule 3 | Use for Codex sidecar; forbid `type: mcp` tools in estate wrappers | <https://huggingface.co/docs/inference-providers/guides/responses-api> | Medium x Low | New | NATIVE |
| F5 Codex `model_providers.huggingface` profile | First-party Codex config for router (`base_url`, `env_key = HF_TOKEN`, `wire_api = responses`, `X-HF-Bill-To`) | Process-local sidecar like the OpenRouter posture; does not touch auth2api :8317 or Cursor BYOK | Add `~/.codex/huggingface.config.toml`; keep spend on HF credits | <https://huggingface.co/docs/inference-providers/integrations/codex> | Medium x Low | New | NATIVE |
| F6 `hf claude` extension / `ANTHROPIC_BASE_URL` swap | First-party Claude Code repoint to router | **Lock-adjacent**: the OpenRouter lock forbids `ANTHROPIC_BASE_URL`; treat HF the same unless the owner explicitly widens the lock | Do not adopt; record as trade-off (open models in Claude Code UX vs identity/quota confusion) | <https://huggingface.co/docs/inference-providers/integrations/claude-code> | Low x Low | New | NATIVE (rejected by lock) |
| F7 `X-HF-Bill-To` + org spending limits | Header-level billing attribution and provider disable list | Only if the owner creates a Team org; single user gets $2 PRO credits | Note only | <https://huggingface.co/docs/inference-providers/pricing> | Low x Low | Minor | NATIVE |
| F8 ZeroGPU 2026 facts | Blackwell 48/96 GB, 40 min/day PRO, 60-s call budget, $1/10 min overage, PyTorch 2.8+, no `torch.compile` | Owner's private recipe runs on it; skill text is stale (A10G-era) | Update recipe + evals; add `duration=` to `generate` | <https://huggingface.co/docs/hub/spaces-zerogpu> | Medium x Low | Correction | NATIVE |
| F9 Fix `Prekzursil/GLM-5.3` Space hardware | Public Space in `RUNTIME_ERROR` (ZeroGPU requested, no GPU function) | It is a router client; wrong hardware; visible failure on the owner's public profile | Owner action: set hardware `cpu-basic` (Space settings); no code change | Space API probe (4.1) | Medium x Trivial | Bug-find | NATIVE (settings) |
| F10 Endpoint scale-to-zero contract | 1 h idle, 503 vs `X-Scale-Up-Timeout`, quota counted while at zero | Only matters if a private checkpoint moves off ZeroGPU | Document in environments.md Endpoints row | <https://huggingface.co/docs/inference-endpoints/guides/autoscaling> | Low x Low | Correction | NATIVE |
| F11 Hub `RateLimit` headers + `huggingface_hub >= 1.2.0` retry | IETF draft headers, exact-sleep retry in SDK | Hub MCP + `hf models ls` + router share one token; a burst from the fleet can 429 the Hub API bucket (2,500/5 min PRO) | Prefer `huggingface_hub` for Hub calls; surface `RateLimit` in wrapper logs | <https://huggingface.co/docs/hub/rate-limits> | Medium x Low | New | NATIVE |
| F12 Official HF MCP skills surface (SEP-2640) | `skills/list` etc. from `hf://buckets/huggingface/skills` over HTTP | **Lock check**: a second prompt SSOT visible to Claude Code/Cursor; `.agents/skills` is the ONE SSOT | Keep the `huggingface` MCP mounted but document that its skills are advisory and never copied into `.agents/skills` without review | <https://github.com/evalstate/hf-mcp-server> | Medium x Low | New risk | NATIVE (needs a rule) |
| F13 Gradio MCP header auth (`gr.Header`, Bearer) | Private/ZeroGPU Space tools callable as MCP with caller-quota semantics | Only for narrow non-chat tools per fleet-curation | Not now | Gradio guide | Low x Low | Minor | NATIVE |
| F14 Token split by usage (not rotation) | Fine-grained "Make calls to Inference Providers" token for wrappers; keep current token for Hub | Blast-radius reduction without rotating anything | Owner creates one additional token; new name in `.agents/local.json` | <https://huggingface.co/docs/hub/security-tokens> | Medium x Low | New | NATIVE |
| F15 General HF integration layer (glm53 successor) | ~100-line OpenAI-SDK client: model + policy suffix, `/v1/models` cache, capability gate, 401/429 handling, no MCP | Owner has decided to deprecate `glm53-space`; this is the shape that satisfies rules 2-3 of the skill and the locks | BUILD in `tools/` (process-local wrapper), register **nothing** new in `agents.json` | Sections 2, 7 | High x Medium | Planned replacement | BUILD (thin) |

## 10. Ten-line summary

1. `router.huggingface.co/v1` is the HF runtime the skill omits: OpenAI-compatible, chat-only, 14 chat providers, no markup, $2/month PRO credits then pay-as-you-go [A, corr].
2. Model-id suffixes `:fastest` (default) / `:cheapest` / `:preferred` / `:<provider>` do routing server-side; `:zai-org` is just the author-as-provider case [A, corr].
3. Public `GET /v1/models` (136 models) publishes per-provider price, context, `supports_tools`, `supports_structured_output`, TTFT and tok/s - a ready-made provider table [A, measured 2026-09-02].
4. Measured GLM-5.3: $1.40/$4.40 per M on novita/together/baseten; structured output only on fireworks-ai and baseten; author `zai-org` reports none; together is fastest (196 ms TTFT, 140 tok/s) [measured].
5. `heretic-org/Qwen3.8-27B-heretic-ara` is `warm` on featherless-ai via the router, so the private ZeroGPU Heretic Space may be demotable to fallback; tool-calling on that route is UNVERIFIED [A probe + infer].
6. ZeroGPU is now RTX Pro 6000 Blackwell (48/96 GB), PRO 40 GPU-min/day, 60-s per-call budget, $1/10 min overage, PyTorch 2.8+, 10-Space cap; the skill's A10G-era framing is stale [A, corr].
7. The owner's public Space `Prekzursil/GLM-5.3` is in `RUNTIME_ERROR` ("No @spaces.GPU function") because a router client requested ZeroGPU; fix is `cpu-basic` hardware [measured].
8. Dedicated Endpoints: L40S $1.80/h, scale-to-zero after 1 h idle, 503 unless `X-Scale-Up-Timeout`, scaled-to-zero still consumes quota - reserved for private checkpoints under sustained load [A, corr].
9. Official HF MCP (v0.4.15, streamable HTTP) now carries Jobs/Space/sandbox tools and a SEP-2640 skills surface - a second prompt SSOT that the `.agents/skills` lock must explicitly subordinate [A, corr + infer].
10. HF ships first-party Codex (`wire_api = responses`, lock-compatible sidecar) and Claude Code (`ANTHROPIC_BASE_URL` swap, lock-adjacent, do not adopt) router guides; the glm53 successor should be a thin process-local `/v1` client with policy suffixes and a `/v1/models` capability gate, registering no new MCP [A + rec].
