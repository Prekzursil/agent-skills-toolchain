# Lens 05 - Competitive teardown: provider/model registries in other harnesses

- Gem-hunt: `2026-09-02-hosted-models` (discovery only; no code changed)
- Lens id: `05-competitive-teardown-provider-registries`
- Branch: `gemhunt/hosted-models-05-competitive-teardown-provider-registries` (from `main` @ `5fa34fda1`)
- Author: cloud agent, one lens of a multi-lens hunt
- Date: 2026-09-02
- Status: IN PROGRESS - sections are appended and pushed one at a time (platform kills runs ~12 min)

## 0. Scope, method, locks

### 0.1 Question this lens answers

How do the other agent harnesses on (or adjacent to) this estate describe a *model endpoint* -
`id`, `base_url`, API shape, auth env-var name, context window, tool support, cost, capability
flags, health probe - and how do they materialize that description into per-runtime config?
Which pieces should the estate's own registry (`.agents/agents.json` + secrets-by-name in
`.agents/local.json`, DEDUP item 4) copy *verbatim*, and which are NATIVE (already shipped by a
runtime we run) vs BUILD (we would have to write it)?

Targets named by the hunt brief: OpenCode (models.dev registry + `provider` config), Goose
`custom_providers`, Aider model settings/metadata, Cline / Roo Code / Continue provider schemas,
Kilo Code, Pi (`pi-mono`) / Oh-my-pi, Hermes Agent, Crush, Codex `model_providers`, Grok CLI
`[model.X]` blocks, Claude Code settings.

### 0.2 Method (deep-research discipline)

- Every claim carries a URL and a grade. Grade = source tier + corroboration + date:
  - **A** = primary artifact (the schema file, the Rust/TS/Go struct, the JSON Schema, official docs).
  - **B** = official docs or maintainer text that describes but is not the artifact.
  - **C** = secondary (blog, issue thread, third-party summary).
  - `corroborated` = two independent sources agree; `UNVERIFIED` = single source or unreachable
    at hunt time; every grade carries the retrieval date `(2026-09-02)`.
- Preference: sources from the last 12 months (2025-09 .. 2026-09). Older sources are flagged.
- Each paragraph is labelled **[FACT]** (sourced), **[INFERENCE]** (my reasoning from facts) or
  **[RECOMMENDATION]** (what the estate should do).
- Verification ladder used: `WebFetch` of the raw schema file on GitHub or the official docs page;
  where a fetch failed, the claim is marked `UNVERIFIED` rather than dropped.

### 0.3 Estate locks (constraints, cited as given by the hunt brief; never violated below)

| Lock | Consequence for this lens |
| --- | --- |
| OpenRouter is a spend-capped CLI/Codex sidecar only; never a Cursor BYOK key, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP | Any "copy models.dev / OpenRouter pricing" finding is registry *metadata*, not a routing change. |
| No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory | Findings that lean on a proxy layer (LiteLLM-style) are marked out-of-bounds and only their *schema* is harvested. |
| `auth2api :8317` stays the only Cursor bridge; retires within 7 days of an official Cursor `/v1` GA | Every per-runtime materialization below points `cursor-*` ids at `127.0.0.1:8317`, never elsewhere. |
| Ports 8765 / 8812 / 8317 are owned | No health-probe or registry service may claim them. |
| `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it) | Provider registry is *config* SSOT, not prompt SSOT; nothing here duplicates prompts. |
| Never rotate credentials | Secrets stay *by name* (`auth_env`), never by value, in any schema proposed. |
| Never remove a feature to buy reliability - present tradeoffs | Deprecating `tools/mcp/glm53-space` (DEDUP item 2) is the owner's decision; this lens only supplies the replacement schema. |

### 0.4 DEDUP-SET acknowledged (not re-proposed)

1. `.agents/skills/hosted-model-agents` on `live-capture/2026-09-02` - current doctrine.
2. `tools/mcp/glm53-space` on `main` - hardcoded to `router.huggingface.co/v1` + `zai-org/GLM-5.3`; to be deprecated in favour of a general integration layer (this lens feeds that layer's schema).
3. `auth2api` on `127.0.0.1:8317` - 36 `cursor-*` model ids; consumed by goose, grok `config.toml`, fabric/claude/codex wrappers.
4. Registry `.agents/agents.json` (`mcp.servers`, 42 servers) + secrets by name in `.agents/local.json`.
5. Installed runtimes on the Windows 11 box (31.6 GB RAM, no GPU assumed): claude, codex, cursor-agent, grok + agent.exe, goose 1.47, fabric 1.4.470, agy, gemini CLI, opencode, aider 0.86, ollama, lms, ralph, basic-memory :8765, agent-mail :8812, browser-bridge hub :8770.

## 1. Codex CLI - `[model_providers.<id>]` (TOML) and `ModelProviderInfo` (Rust)

### 1.1 The schema, verbatim from the primary artifact

**[FACT, A, corroborated (Rust struct + generated JSON Schema agree), 2026-09-02]** Codex's
provider record is the Rust struct `ModelProviderInfo` in
`codex-rs/model-provider-info/src/lib.rs` and is mirrored 1:1 in the generated
`codex-rs/core/config.schema.json` (`definitions.ModelProviderInfo`, `schemars(deny_unknown_fields)`).
Sources: <https://raw.githubusercontent.com/openai/codex/main/codex-rs/model-provider-info/src/lib.rs>
and <https://raw.githubusercontent.com/openai/codex/main/codex-rs/core/config.schema.json>. Fields
(all optional unless noted):

| Field | Type | Doc-comment (verbatim, abbreviated) |
| --- | --- | --- |
| `name` | string (required) | Friendly display name. |
| `base_url` | string | Base URL for the provider's OpenAI-compatible API. |
| `env_key` | string | Environment variable that stores the user's API key for this provider. |
| `env_key_instructions` | string | Instructions to help the user get a valid value for the variable and set it. |
| `experimental_bearer_token` | redacted string | Discouraged in favour of `env_key`. |
| `auth` | `ModelProviderAuthInfo` | **Command-backed bearer token**: `command`, `args`, `cwd`, `timeout_ms`, `refresh_interval_ms` (0 = no proactive refresh). |
| `aws` | `ModelProviderAwsAuthInfo` | SigV4: `profile`, `region`, `auth_refresh {command,args,timeout_ms}`. |
| `wire_api` | enum | **Only `"responses"` is accepted** (see 1.2). |
| `query_params` | map | Appended to the base URL. |
| `http_headers` | map | Static extra headers. |
| `env_http_headers` | map header -> ENV NAME | Header is sent only if the env var is set and non-empty. |
| `request_max_retries` / `stream_max_retries` / `stream_idle_timeout_ms` / `websocket_connect_timeout_ms` | ints | Per-provider resilience knobs, hard-capped by constants. |
| `requires_openai_auth` | bool | If true, login screen + `auth.json`; else key comes from `env_key`. |
| `supports_websockets` | bool | Provider supports the Responses-API WebSocket transport. |
| `supports_standalone_web_search` | bool | Provider supports the standalone web-search endpoint. |

Top-level: `model_providers` is a map `id -> ModelProviderInfo` whose description reads
"User-defined provider entries that extend the built-in list. **Built-in IDs cannot be
overridden**"; `model_provider` (string) selects one. Built-ins include `openai`,
`amazon-bedrock`, `amazon-bedrock-runtime` (default base
`https://bedrock-mantle.us-east-1.api.aws/openai/v1`), and the OSS ids `ollama` and `lmstudio`.

### 1.2 The load-bearing fact: Codex no longer speaks `chat/completions`

**[FACT, A+C corroborated, 2026-09-02]** `WireApi` now has a single variant, `Responses`; the
deserializer returns the error string ``"`wire_api = \"chat\"` is no longer supported. How to fix:
set `wire_api = \"responses\"` ... https://github.com/openai/codex/discussions/7782"``. The
discussion (opened 2025-12-09 by a maintainer) announced deprecation with hard removal "early
February 2026"; a commenter confirms removal landed 2026-02-05 via PR #10157. The legacy
`ollama-chat` provider id was removed at the same time (`OLLAMA_CHAT_PROVIDER_REMOVED_ERROR`).
Sources: `lib.rs` above (lines 57-59, 64-90) and
<https://github.com/openai/codex/discussions/7782>.

**[FACT, C, 2026-09-02]** Same thread: LM Studio and llama.cpp `server` implement `/v1/responses`
(llama.cpp "works by converting Responses request into Chat Completions request"); Ollama was
"planning" it as of 2025-12; several community bridges exist that translate Responses -> Chat
Completions (`jazzenchen/VibeAround` + crate `va-ai-api-bridge`, `apieum/codex-proxy` which uses
LiteLLM - **out of bounds for this estate by the no-LiteLLM lock**). Grade C: single thread,
not re-verified against each project's docs.

**[INFERENCE]** DEDUP item 3 says `codex-cursor` in `~/.local/bin` routes Codex through
`auth2api :8317`. That wrapper only works today if `auth2api` serves **`POST /v1/responses`**
(streamed SSE items), not just `/v1/chat/completions`. Whether it does is not recorded in the
brief; this lens cannot verify it from the cloud sandbox and flags it **UNVERIFIED / must-probe**.
This is also why a registry needs an `api.shape` field *per endpoint* and not per provider:
the same `127.0.0.1:8317` may be `chat_completions`-capable for Goose/Fabric and
`responses`-capable (or not) for Codex.

**[FACT, A, 2026-09-02]** Codex also ships a *capability probe* in its app-server protocol:
`ModelProviderCapabilitiesReadResponse { imageGeneration: bool, namespaceTools: bool, webSearch: bool }`
(<https://raw.githubusercontent.com/openai/codex/main/codex-rs/app-server-protocol/schema/json/v2/ModelProviderCapabilitiesReadResponse.json>).
It is a *read* of what the provider record declares, not a live HTTP probe.

### 1.3 Materialization pattern

**[FACT, A, 2026-09-02]** Codex materializes from one TOML file (`~/.codex/config.toml`, plus
project and managed layers - `requirements.toml` can pin `allow_managed_hooks_only`, per
<https://raw.githubusercontent.com/openai/codex/main/docs/config.md>). Provider blocks are
`[model_providers.<id>]`; model choice is separate (`model = "..."`, `[profiles.<p>]` can pin
`model_provider` + `model`). Secrets are never inline by default: `env_key` names the variable,
`env_http_headers` names variables for headers, `auth.command` runs a token helper.

### 1.4 What to copy verbatim / NATIVE-vs-BUILD

**[RECOMMENDATION]**
- COPY VERBATIM into the estate registry: `env_key` (secret-by-name, matches
  `.agents/local.json` doctrine), `env_http_headers` (header -> env name), `auth {command,args,
  timeout_ms, refresh_interval_ms}` (a *command-backed token* slot is exactly what a future
  Cursor-quota bridge or HF token helper needs), and the trio
  `request_max_retries / stream_max_retries / stream_idle_timeout_ms`.
- ADAPT: `wire_api` must become a multi-valued `api.shape` in *our* registry
  (`chat_completions | responses | anthropic_messages | ollama_native | gemini_generate`),
  because Codex is the only consumer that is Responses-only.
- NATIVE: Codex reads `[model_providers.*]` itself - the estate only has to *emit* the TOML
  block (BUILD = a renderer, ~40 lines, from the registry to `~/.codex/config.toml`; same
  shape as the existing `merge_generated_cursor_mcp.py` renderer pattern on `main`).
- Health probe to add for every `responses`-shaped endpoint: `POST {base_url}/responses` with
  `{"model": id, "input": "ping", "stream": false}` expecting `200` + `object: "response"`.

## 2. OpenCode - models.dev catalog + `provider` config (V2 schema)

### 2.1 Two-layer design: public catalog (models.dev) + local override (opencode.json)

**[FACT, A, corroborated (README + `packages/core/src/schema.ts` reference + OpenCode loader), 2026-09-02]**
models.dev is a TOML-per-model catalog (`providers/<provider>/provider.toml`,
`providers/<provider>/models/<model>.toml`, plus provider-agnostic `models/<lab>/<model>.toml`
metadata since the `base_model` feature) compiled to one JSON at `https://models.dev/api.json`.
Source: <https://raw.githubusercontent.com/sst/models.dev/dev/README.md>. Schema reference
(verbatim field list, README "Schema Reference"):

- Provider: `name`, `npm` (AI-SDK package, e.g. `@ai-sdk/openai-compatible`), `env` (string[]
  of env-var *names* used for auth), `doc`, `api` (base URL; required only when `npm` is the
  openai-compatible package).
- Model: `name`, `family`, `attachment`, `reasoning`, `tool_call`, `structured_output`,
  `temperature` (bool = "supports temperature control"), `knowledge` (cutoff `YYYY-MM`),
  `release_date`, `last_updated`, `open_weights`, `interleaved` (bool | `{field:
  "reasoning_content" | "reasoning_details"}`), `cost.{input,output,reasoning,cache_read,
  cache_write,input_audio,output_audio}` USD per 1M, `limit.{context,input,output}`,
  `modalities.{input,output}` from `text|image|audio|video|pdf`, `status` in
  `alpha|beta|deprecated`, `reasoning_options` (provider-specific control set - the README
  warns "Do not use `[]` from uncertainty on relays"), `base_model` + `base_model_omit`
  (override-only inheritance with dot-path removal).

**[FACT, A, 2026-09-02]** OpenCode's runtime model of a provider/model (Effect `Schema`, package
`@opencode-ai/schema`): <https://raw.githubusercontent.com/sst/opencode/dev/packages/schema/src/provider.ts>
and <https://raw.githubusercontent.com/sst/opencode/dev/packages/schema/src/model.ts>.

```text
ProviderV2.Info { id, integrationID?, name, disabled?, api: AISDK|Native, request: {headers, body} }
  AISDK  = { type:"aisdk", package, url?, settings? }
  Native = { type:"native", url?, settings }
ModelV2.Info { id, providerID, family?, name, api: {id, ...AISDK|Native},
  capabilities: { tools: bool, input: string[], output: string[] },
  request: { headers, body, variant? }, variants: [{ id, headers, body }],
  time: { released }, cost: Cost[] where Cost = { tier?: {type:"context", size}, input, output, cache:{read,write} },
  status: alpha|beta|deprecated|active, enabled, limit: { context, input?, output } }
```

Key design choices worth naming: (a) **`api` is a tagged union** - either "use this AI-SDK
npm package" or "native" with an optional `url`; the API *shape* is implied by the package
(`@ai-sdk/openai-compatible`, `@ai-sdk/anthropic`, ...). (b) **`request.{headers, body}` is a
generic per-provider *and* per-model override**, and `variants[]` are named request presets
(e.g. a "high reasoning" variant) - this replaces bespoke `reasoning_effort` fields.
(c) **`cost` is an array with an optional `tier {type:"context", size}`** so a 200k-context
price tier and a 1M-context price tier can coexist for the same id. (d) `status` gained
`active` in the runtime schema (catalog has only `alpha|beta|deprecated`,
`packages/core/src/models-dev.ts` line 15).

**[FACT, A, 2026-09-02]** User-side config (`packages/core/src/config/provider.ts`) is the same
shape with everything optional plus `env: string[]`, `models: Record<id, Model>`; i.e. the
local file *patches* the catalog record. Source:
<https://raw.githubusercontent.com/sst/opencode/dev/packages/core/src/config/provider.ts>.

### 2.2 Materialization: fetch -> disk cache -> flock -> merge

**[FACT, A, 2026-09-02]** `packages/core/src/models-dev.ts`
(<https://raw.githubusercontent.com/sst/opencode/dev/packages/core/src/models-dev.ts>):
source URL `Flag.OPENCODE_MODELS_URL || "https://models.opencode.ai"` + `/api.json`; on-disk
cache under the global cache dir with a **5-minute TTL** on mtime; **cross-process `flock`**
around the cache file ("concurrent opencode CLIs can race on this cache file"); a background
refresh every **60 minutes**; escape hatches `OPENCODE_MODELS_PATH` (load a local snapshot) and
`OPENCODE_DISABLE_MODELS_FETCH`; a compile-time embedded snapshot `OPENCODE_MODELS_DEV` as last
resort. The catalog `Model` also carries `reasoning_options` (typed union incl.
`{type:"budget_tokens", min, max}`) and `experimental.modes` (per-mode `cost` + provider
`body/headers`).

**[INFERENCE]** This is the most complete *offline-first* materialization among the harnesses
surveyed: remote -> TTL cache -> local override path -> embedded fallback, with a file lock.
It is exactly the failure-tolerant shape the estate needs on a memory-starved Windows box where
multiple CLIs (goose, fabric, aider, codex) may start concurrently.

### 2.3 What to copy verbatim / NATIVE-vs-BUILD

**[RECOMMENDATION]**
- COPY VERBATIM (as the *model metadata* half of the estate registry): models.dev's model TOML
  fields `tool_call`, `reasoning`, `attachment`, `structured_output`, `temperature`,
  `knowledge`, `release_date`, `open_weights`, `cost.*`, `limit.*`, `modalities.*`, `status`,
  `interleaved.field`. They are the de-facto lingua franca (OpenCode, Pi, and - via
  `@ai-sdk/*` package names - the Vercel ecosystem consume them).
- COPY VERBATIM (as the *materialization* half): the `OPENCODE_MODELS_URL / _PATH /
  _DISABLE_MODELS_FETCH` triad and the TTL + flock + embedded-fallback ladder.
- ADOPT `request.{headers, body}` + `variants[]` instead of inventing per-runtime
  `reasoning_effort` columns; `cost[]` with `tier` for context-tiered pricing.
- NATIVE: `opencode` is installed on the box (DEDUP 5) and already reads
  `~/.config/opencode/opencode.json` `provider.*`; the estate only needs a renderer that
  emits `provider["cursor-auth2api"] = { npm:"@ai-sdk/openai-compatible", options:{baseURL:
  "http://127.0.0.1:8317/v1"}, models:{...36 ids...} }`. Verify the exact key names against the
  *current* OpenCode docs at render time (V2 config has `api`/`request`, older docs used
  `npm`/`options.baseURL`; both are still accepted through `config/v2-compat.ts`
  [FACT, A: file exists in tree, content not read - UNVERIFIED as to which keys it maps]).
- BUILD: a nightly job that snapshots `https://models.dev/api.json` into the estate as
  `models.snapshot.json` (pin by sha) so registry entries can reference `models_dev:
  "huggingface/zai-org/GLM-5.3"` and inherit cost/limits without re-typing.

## 3. Crush - `crush.json` `providers` + Catwalk registry (Go)

### 3.1 The schema, verbatim

**[FACT, A, corroborated (JSON Schema + Go struct), 2026-09-02]** Crush's user config is
validated by <https://raw.githubusercontent.com/charmbracelet/crush/main/schema.json>
(`$defs.ProviderConfig`, `$defs.Model`, `$defs.SelectedModel`); its catalog type is the Go
struct in <https://raw.githubusercontent.com/charmbracelet/catwalk/main/pkg/catwalk/provider.go>.

`ProviderConfig` (schema descriptions verbatim): `id`, `name`, `base_url`, `type` enum
`openai | openai-compat | openrouter | vercel | anthropic | google | azure | bedrock |
google-vertex | hyper | litellm | llamacpp | lmstudio | ollama | omlx`, `api_key`, `oauth`
(Token), `disable`, `system_prompt_prefix`, `extra_headers`, `extra_body` ("only works with
openai-compatible providers"), `provider_options`, `aws_auth_refresh` ("Shell command to run
when AWS credentials expire"), `flat_rate`, **`discover_models`** ("Auto-discover models from
`/v1/models` endpoint. When true with existing models they are merged (yours win)"), `models[]`.

`Model` (Go struct, JSON names): `id`, `name`, `cost_per_1m_in`, `cost_per_1m_out`,
`cost_per_1m_in_cached`, `cost_per_1m_out_cached`, `context_window`, `default_max_tokens`,
`can_reason`, `reasoning_levels[]`, `default_reasoning_effort`, `supports_attachments`,
`options {temperature, top_p, top_k, frequency_penalty, presence_penalty, provider_options}`.

`SelectedModel` (the `models.large` / `models.small` slots): `model`, `provider`,
`reasoning_effort` enum `low|medium|high`, `think` (Anthropic), `max_tokens`, sampling
params, `provider_options`.

**[FACT, A, 2026-09-02]** Catwalk's shipped provider records use **`"api_key":
"$OPENROUTER_API_KEY"`** - a `$ENV` reference, not a value - plus `api_endpoint`,
`default_large_model_id`, `default_small_model_id`, `default_headers` (OpenRouter record sets
`HTTP-Referer`/`X-Title`). Source:
<https://raw.githubusercontent.com/charmbracelet/catwalk/main/internal/providers/configs/openrouter.json>
(266 models at fetch time).

### 3.2 Materialization: `CATWALK_URL` -> 45 s timeout -> cache -> embedded

**[FACT, A, 2026-09-02]** `internal/config/provider.go`
(<https://raw.githubusercontent.com/charmbracelet/crush/main/internal/config/provider.go>):
resolution order is `CATWALK_URL` env (or a literal `embedded`) -> HTTP fetch with a
**45-second context timeout** -> on-disk cache -> `embedded.GetAll()` compiled-in list. The
doc comment is explicit that "A refresh that simply could not reach the network is not an
error at all: the cached or embedded catalog is a sound answer".

### 3.3 What to copy verbatim / NATIVE-vs-BUILD

**[RECOMMENDATION]**
- COPY VERBATIM: `type` as an explicit **API-shape enum that includes local servers**
  (`llamacpp`, `lmstudio`, `ollama`, `omlx`) - this is the cleanest answer to "what wire shape
  does 127.0.0.1:1234 speak" and maps directly onto the estate's installed `ollama` and `lms`
  (DEDUP 5). Also copy `discover_models` (probe `/v1/models`, merge, **user entries win**) as
  the estate's *first* health/discovery probe - it is cheap and works for auth2api, LM Studio,
  Ollama's OpenAI shim, HF router and Spaces alike.
- COPY VERBATIM: `"$ENV_NAME"` string convention for `api_key` (compatible with
  `.agents/local.json` secrets-by-name) and `default_large_model_id / default_small_model_id`
  (a per-provider "large/small" default pair is how Crush, Claude Code and OpenCode all pick
  a cheap sidecar model).
- ADAPT: `cost_per_1m_*` is flatter than models.dev `cost.*`; keep models.dev naming and
  map on render.
- NATIVE-vs-BUILD: Crush is **not** installed on the box (absent from DEDUP 5) - treat it as
  schema-donor only (BUILD nothing for Crush). Catwalk itself is a static JSON service; a
  Catwalk-format export from the estate registry would be ~30 lines if Crush is ever adopted.
- Lock check: `type: "litellm"` exists in Crush's enum; it is **not** to be used here
  (no-LiteLLM lock) - the estate enum should omit it.

## 4. Goose - declarative providers (`custom_providers/*.json`) + canonical model registry

### 4.1 The schema, verbatim

**[FACT, A, corroborated (Rust struct + shipped definitions + docs), 2026-09-02]** Goose 1.x (the
box runs 1.47, DEDUP 5) defines every non-hand-coded provider as a JSON file deserialized into
`DeclarativeProviderConfig` (`crates/goose-providers/src/declarative.rs`,
<https://raw.githubusercontent.com/block/goose/main/crates/goose-providers/src/declarative.rs>).
Built-in definitions live in `crates/goose-providers/src/declarative/definitions/*.json`
(groq, lmstudio, llama_swap, deepseek, mistral, moonshot, minimax ...); user definitions are
loaded by `load_custom_providers(dir)` from every `*.json` in `~/.config/goose/custom_providers/`
(Windows: `%APPDATA%\Block\goose\config\custom_providers\`) per
<https://raw.githubusercontent.com/block/goose/main/documentation/docs/getting-started/providers.md>
("Configure Custom Provider" + "Command-Based Authentication").

| Field | Type / default | Note (from doc-comments or definitions) |
| --- | --- | --- |
| `name` | string | provider id |
| `engine` | enum `openai` \| `anthropic` \| `ollama` (aliases `*_compatible`) | **API shape enum** - "Custom providers must use OpenAI, Anthropic, or Ollama compatible API formats" |
| `display_name`, `description` | string | UI |
| `api_key_env` | string, default `""` | secret **by env name**; mutually exclusive with `auth` |
| `auth` | `{command, args[], refresh_interval (s, default 3600, 0 = reactive only), timeout_seconds (10), cwd}` | spawned **without a shell**; "matches Codex's `refresh_interval_ms: 0` convention" (verbatim doc-comment) |
| `base_url` | string, supports `${ENV}` interpolation | **full route**, e.g. `.../v1/chat/completions`, `${LMSTUDIO_HOST}/v1/chat/completions` |
| `base_path` | string? | alt. path override |
| `models[]` | `ModelInfo { name, context_limit, max_tokens? }` | static list |
| `dynamic_models` | bool? | `Some(false)`+non-empty models = static, no API call; else **try `/v1/models`, fall back to `models` on 404** |
| `headers` | map | static headers |
| `env_vars[]` | `{name, required, secret, primary, default, description}` | typed, UI-renderable env declarations (lmstudio: `LMSTUDIO_HOST` default `http://localhost:1234`, `secret:false`) |
| `timeout_seconds`, `supports_streaming`, `requires_auth` (default true) | | |
| `catalog_provider_id`, `skip_canonical_filtering` | | link to the canonical catalog (4.2) / opt out of filtering |
| `fast_model` | string? | the provider's cheap/"small" model |
| `preserves_thinking`, `emit_clear_thinking` | bool | reasoning-replay quirks (Z.AI `clear_thinking`) |
| `setup { category, setup_method: single_api_key \| config_fields, group, docs_url, field_overrides[] }` | | drives the configure wizard |
| `model_doc_link`, `setup_steps[]` | | onboarding text |

### 4.2 Canonical model registry = models.dev shape, normalised ids

**[FACT, A, 2026-09-02]** `crates/goose-provider-types/src/canonical/data/canonical_models.json`
(<https://raw.githubusercontent.com/block/goose/main/crates/goose-provider-types/src/canonical/data/canonical_models.json>)
holds **7,205** records whose fields are *exactly* the models.dev model schema (`id`, `name`,
`family`, `attachment`, `reasoning`, `tool_call`, `temperature`, `release_date`,
`last_updated`, `modalities`, `open_weights`, `cost{input,output}`, `limit{context,output}`)
with ids like `302ai/MiniMax-M1`; `provider_metadata.json` (175 providers) carries the
models.dev *provider* fields `npm`, `api`, `doc`, `env[]` plus `model_count`. The crate README
(<https://raw.githubusercontent.com/block/goose/main/crates/goose-provider-types/src/canonical/README.md>)
says the builder "normalizes provider-specific model names (e.g. `claude-sonnet-4-5-20250929`)
to canonical IDs (e.g. `anthropic/claude-sonnet-4.5`)" and "Compares with previous runs (like a
lock file)" via `canonical_mapping_report.json`. The README still says it "Fetches from
OpenRouter API"; the data shape says models.dev - **[INFERENCE]** the README lags the code;
graded B for the *source* of the data, A for the *shape*.

**[INFERENCE]** Two independent, heavily-used harnesses (OpenCode and Goose) now store model
capability metadata in the models.dev shape. That is the strongest possible signal for which
field names the estate registry should adopt for the *model* half.

### 4.3 What to copy verbatim / NATIVE-vs-BUILD

**[RECOMMENDATION]**
- COPY VERBATIM: `env_vars[] {name, required, secret, primary, default, description}` - the only
  surveyed schema that types *non-secret* configuration env vars (a host URL) separately from
  secrets; this is precisely the `LMSTUDIO_HOST`/`OLLAMA_HOST`/`AUTH2API_HOST` situation on the
  box. Also copy `dynamic_models` semantics (static list wins if declared; else `/v1/models`
  with 404 fallback) and `fast_model`.
- COPY VERBATIM: the `auth {command,args,refresh_interval,timeout_seconds,cwd}` block - it is
  already field-compatible with Codex's (Goose's own comment says so), so one estate field set
  renders to both runtimes.
- ADAPT: Goose wants `base_url` as a **full route** (`.../v1/chat/completions`), Codex/OpenCode/
  Crush want a **base** (`.../v1`). The estate registry must store the base and let the Goose
  renderer append the engine-specific route; record this as `api.shape -> route` table:
  `chat_completions -> /chat/completions`, `responses -> /responses`, `anthropic_messages ->
  /v1/messages`, `ollama -> /api/chat`.
- NATIVE: `goose configure` already supports "Command (refreshable)" and custom providers; the
  estate's existing `GOOSE_PROVIDER=goose-cursor-proxy` (DEDUP 3) is presumably one such JSON
  - the registry renderer should *own* that file (`custom_providers/goose-cursor-proxy.json`)
  rather than hand-edit it. BUILD = renderer only.
- Lock check: Goose's `.agents/skills` consumption is prompt-side and untouched; this is
  config-side.

## 5. Aider - `.aider.model.settings.yml` + `.aider.model.metadata.json`

### 5.1 Two files, two concerns

**[FACT, A, 2026-09-02]** Aider (0.86 on the box) splits *behavioural* settings from *metadata*:

- `aider/resources/model-settings.yml`
  (<https://raw.githubusercontent.com/Aider-AI/aider/main/aider/resources/model-settings.yml>,
  86 KB) is a YAML list keyed by `name`. Key frequency in the shipped file (measured
  2026-09-02): `use_repo_map` 338, `edit_format` 333, `weak_model_name` 300,
  `accepts_settings` 233, `use_temperature` 178, `examples_as_sys_msg` 158,
  `editor_model_name` 145, `editor_edit_format` 138, `extra_params` 88 (nested `max_tokens`,
  `extra_headers`, `top_p`, `temperature`, `include_reasoning`), `overeager` 64,
  `cache_control` 63, `system_prompt_prefix` 53, `reminder` 44, `streaming` 36, `lazy` 15,
  `use_system_prompt` 11, `caches_by_default` 10, `reasoning_tag` 3.
- `aider/resources/model-metadata.json`
  (<https://raw.githubusercontent.com/Aider-AI/aider/main/aider/resources/model-metadata.json>)
  is JSON-with-comments in the **LiteLLM `model_prices_and_context_window` shape**:
  `max_tokens`, `max_input_tokens`, `max_output_tokens`, `input_cost_per_token` (per *token*,
  not per 1M), `input_cost_per_token_cache_hit`, `cache_read_input_token_cost`,
  `cache_creation_input_token_cost`, `output_cost_per_token`, `litellm_provider`, `mode:
  "chat"`, `supports_function_calling`, `supports_assistant_prefill`, `supports_tool_choice`,
  `supports_prompt_caching`. Model keys are LiteLLM-prefixed (`openrouter/deepseek/...`).

**[INFERENCE]** Aider's *settings* file is the only surveyed schema that records **per-model
prompting behaviour** (`edit_format`, `use_repo_map`, `lazy`, `overeager`, `reminder: sys`,
`examples_as_sys_msg`) and a **per-model sidecar pair** (`weak_model_name`,
`editor_model_name`). No other harness encodes "which cheap model does the commit messages"
declaratively.

**[FACT + lock note, A, 2026-09-02]** Aider *embeds* `litellm` as a Python library (the
`litellm_provider` key exists because of it). The estate lock forbids a LiteLLM **proxy /
orchestration runtime**, not the library already inside an installed tool; this lens treats
Aider's metadata format as a *render target* (write `~/.aider.model.metadata.json` from the
registry) and never as a routing layer. Tradeoff stated, feature not removed.

### 5.2 What to copy verbatim / NATIVE-vs-BUILD

**[RECOMMENDATION]**
- COPY VERBATIM (into the estate schema, as optional per-runtime hints): `weak_model_name`,
  `editor_model_name`, `edit_format`, `use_repo_map`, `reasoning_tag`, `extra_params`
  (with nested `extra_headers`) - they are the cleanest existing vocabulary for "sidecar model"
  and "wire quirks".
- ADAPT: cost units. The estate should store USD **per 1M tokens** (models.dev/Catwalk
  convention) and divide by 1e6 when rendering Aider metadata; `max_input_tokens ->
  limit.input`, `max_output_tokens -> limit.output`.
- NATIVE: aider reads both files from `~/` or repo root; `--model-settings-file` /
  `--model-metadata-file` flags exist. BUILD = a renderer for the 36 `cursor-*` ids as
  `openai/<id>` entries with `api_base` pointed at `http://127.0.0.1:8317/v1` via
  `OPENAI_API_BASE` (Aider convention for OpenAI-compatible endpoints; [FACT, B, aider docs
  "OpenAI compatible APIs" page, not re-fetched this run - UNVERIFIED for 0.86 exact flag names]).

## 6. Cline / Roo Code / Kilo Code / Continue - IDE-agent lineage

### 6.1 Roo Code `modelInfoSchema` (zod) - the richest *capability flag* vocabulary

**[FACT, A, 2026-09-02]** `packages/types/src/model.ts`
(<https://raw.githubusercontent.com/RooCodeInc/Roo-Code/main/packages/types/src/model.ts>):

```text
modelInfoSchema = { maxTokens?, maxThinkingTokens?, contextWindow (required), supportsImages?,
  supportsPromptCache (required), promptCacheRetention?: "in_memory"|"24h", supportsVerbosity?,
  supportsReasoningBudget?, supportsReasoningBinary?, supportsTemperature?, defaultTemperature?,
  requiredReasoningBudget?, supportsReasoningEffort?: bool | ["disable","none","minimal","low","medium","high","xhigh"][],
  requiredReasoningEffort?, preserveReasoning?, supportedParameters?: ("max_tokens"|"temperature"|"reasoning"|"include_reasoning")[],
  inputPrice?, outputPrice?, cacheWritesPrice?, cacheReadsPrice?,
  tiers?: [{ contextWindow, inputPrice?, outputPrice?, cacheWritesPrice?, cacheReadsPrice? }],
  pricing multipliers { thresholdTokens, *PriceMultiplier, appliesToServiceTiers: ("default"|"flex"|"priority")[] },
  description?, minTokensPerCachePoint?, maxCachePoints?, cachableFields?, deprecated?, isStealthModel?, isFree?,
  excludedTools?: string[], includedTools?: string[] }
```

Provider settings (`packages/types/src/provider-settings.ts`,
<https://raw.githubusercontent.com/RooCodeInc/Roo-Code/main/packages/types/src/provider-settings.ts>)
are a **zod discriminated union on `apiProvider`** (`anthropic`, `openrouter`, `bedrock`,
`vertex`, `openai`, `ollama`, `vscode-lm`, `lmstudio`, `gemini`, `gemini-cli`,
`openai-codex`, ...). The generic OpenAI-compatible branch is:
`openAiBaseUrl`, `openAiApiKey`, `openAiR1FormatEnabled`, `openAiModelId`,
**`openAiCustomModelInfo: modelInfoSchema`**, `openAiUseAzure`, `azureApiVersion`,
`openAiStreamingEnabled`, `openAiHeaders: Record<string,string>`; local branches add
`ollamaNumCtx` (int >= 128) and `lmStudioDraftModelId` + `lmStudioSpeculativeDecodingEnabled`.
`dynamicProviders = ["openrouter","vercel-ai-gateway","litellm","requesty","unbound","poe"]`
are the ones whose model list is fetched live; `localProviders = ["ollama","lmstudio"]`.
Base settings carry `modelTemperature` and **`rateLimitSeconds`**.

**[INFERENCE]** Roo's schema is the best *capability-flag* donor: it separates "supports X"
from "requires X" (`supportsReasoningBudget` vs `requiredReasoningBudget`), types the
reasoning-effort *value set* per model, and encodes prompt-cache mechanics
(`minTokensPerCachePoint`, `maxCachePoints`, `cachableFields`) that matter for Anthropic-shaped
endpoints. Its weakness: secrets are **inline values** (`openAiApiKey`), stored by the IDE's
secret storage rather than by env name - not compatible with the estate's secrets-by-name lock
without a renderer.

### 6.2 Cline `ModelInfo` (TypeScript interface)

**[FACT, A, 2026-09-02]** `apps/vscode/src/shared/api.ts`
(<https://raw.githubusercontent.com/cline/cline/main/apps/vscode/src/shared/api.ts>; the repo was
re-laid out into `apps/`, `sdk/`, `evals/` - the old `src/shared/api.ts` path 404s):
`ModelInfo { name?, maxTokens?, contextWindow?, maxInputTokens?, supportsImages?,
supportsPromptCache (required, "hardcoded for now"), supportsReasoning?, inputPrice?,
outputPrice?, thinkingConfig { maxBudget?, outputPrice?, supportsThinkingLevel? },
supportsGlobalEndpoint?, cacheWritesPrice?, cacheReadsPrice?, description?, tiers[{
contextWindow, inputPrice?, outputPrice?, cache*Price? }], temperature? }`; the
OpenAI-compatible extension adds `supportsReasoningEffort?`, `supportsTools?`,
`supportsStreaming?`; a **`PriceTier { tokenLimit, price }`** type ("Use Infinity for the
highest tier") implements context-tiered pricing; `openAiModelInfoSafeDefaults` provides a
conservative default record for unknown endpoints. A `liteLlmDefaultModelId` constant exists
(Cline supports a LiteLLM provider - **out of bounds here**).

### 6.3 Kilo Code = OpenCode schema, byte-for-byte

**[FACT, A, corroborated by diff, 2026-09-02]** `Kilo-Org/kilocode` `main` now has
`packages/{opencode, schema, llm, kilo-gateway, ...}`; its `packages/schema/src/provider.ts`
(<https://raw.githubusercontent.com/Kilo-Org/kilocode/main/packages/schema/src/provider.ts>) is
**identical (2,352 bytes, empty `diff`) to OpenCode's** `packages/schema/src/provider.ts`, and
the directory also carries `model.ts`, `models-dev.ts`, `catalog.ts`. The old Roo-style
`packages/types/src/model.ts` path 404s. **[INFERENCE]** Kilo has moved its CLI/agent core onto
the OpenCode codebase; for registry purposes Kilo == OpenCode (section 2) and adds no new
schema. Grade A for the file identity; B for the organisational inference.

### 6.4 Continue `config.yaml` `models[]`

**[FACT, A (official reference doc in-repo), 2026-09-02]** `docs/reference.mdx`
(<https://raw.githubusercontent.com/continuedev/continue/main/docs/reference.mdx>), `models`
section, verbatim property list: `name` (req), `provider` (req, e.g. `openai`, `ollama`),
`model` (req), `apiBase`, **`roles`** (`chat | autocomplete | embed | rerank | edit | apply |
summarize`; default `[chat, edit, apply, summarize]`), **`capabilities`** (`tool_use`,
`image_input` - "will overwrite Continue's autodetection"), `maxStopWords`, `promptTemplates`
(`chat | edit | apply | autocomplete`, chat value is a template *name* like `llama3`,
`anthropic`), `chatOptions {baseSystemMessage, baseAgentSystemMessage, basePlanSystemMessage}`,
`embedOptions {maxChunkSize, maxBatchSize}`, `defaultCompletionOptions {contextLength,
maxTokens, temperature, topP, topK, stop[], reasoning, reasoningBudgetTokens, keepAlive}`,
**`requestOptions {timeout, verifySsl, caBundlePath, proxy, headers, extraBodyProperties,
noProxy[], clientCertificate {cert,key,passphrase}}`**. API keys are written as
`apiKey: ${{ secrets.NAME }}` in Continue Hub blocks (Hub secret templating; [FACT, B: seen in
the same reference doc's examples, not separately verified]).

**[INFERENCE]** Continue is the only surveyed schema that models a **role vector** per model
(`chat/autocomplete/embed/rerank/edit/apply`) and a full **HTTP transport block**
(proxy, CA bundle, client cert, `noProxy`). The role vector is directly useful for the estate:
a HF Space or LM Studio model is often only good for `autocomplete`/`embed`.

### 6.5 What to copy verbatim / NATIVE-vs-BUILD

**[RECOMMENDATION]**
- COPY VERBATIM from Roo: `supportsPromptCache`, `promptCacheRetention`,
  `supportsReasoningEffort: bool | [values]`, `requiredReasoning*`, `preserveReasoning`,
  `supportedParameters[]`, `tiers[]`, `deprecated`, `isFree`, `rateLimitSeconds`.
- COPY VERBATIM from Continue: `roles[]` and `requestOptions {timeout, verifySsl,
  caBundlePath, proxy, noProxy, headers, extraBodyProperties}`.
- COPY VERBATIM from Cline: the idea of `openAiModelInfoSafeDefaults` - a documented
  conservative default record applied to any endpoint whose `/v1/models` says nothing about
  context/tools.
- NATIVE-vs-BUILD: none of Cline/Roo/Kilo/Continue is listed among installed runtimes
  (DEDUP 5; `cursor-agent` is, and Cursor is not in this lineage). Treat all four as **schema
  donors only**; BUILD nothing for them unless one is adopted. If Kilo is ever adopted, the
  OpenCode renderer covers it for free (6.3).

## 7. Pi (`pi-mono`) `~/.pi/agent/models.json` and Oh-my-pi `~/.omp/agent/models.yml`

### 7.1 Pi - the deepest *wire-quirk* vocabulary (`compat`) and the cleanest secret resolution

**[FACT, A (in-repo reference doc), 2026-09-02]** `packages/coding-agent/docs/models.md`
(<https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/models.md>):

- Provider fields: `baseUrl`, **`api`** in `openai-completions | openai-responses |
  anthropic-messages | google-generative-ai` (settable per provider *and* per model),
  `apiKey`, `oauth` (`"radius"`), `headers`, `authHeader: true` (auto `Authorization: Bearer`),
  `models[]`, `modelOverrides{}` (patch built-in models: `name, reasoning, thinkingLevelMap,
  input, cost (partial), contextWindow, maxTokens, samplingParams, headers, compat`).
- Model fields: `id` (req), `name`, `api`, `reasoning` (bool), `thinkingLevelMap` (pi level ->
  provider value, `null` hides a level), `input: ["text"] | ["text","image"]`, `contextWindow`
  (default 128000), `maxTokens` (16384), `samplingParams` (merged verbatim into body),
  **`cost {input, output, cacheRead, cacheWrite, tiers[{inputTokensAbove, ...full rate set}]}`**
  per-1M USD with request-wide tiering ("highest threshold wins"), `compat`.
- **Value resolution** for `apiKey` and `headers` (verbatim rules): `"!command"` executes and
  uses stdout; `$NAME` / `${NAME}` env interpolation (missing var => unresolved); escapes `$$`
  and `$!`; plain strings are literals. "For `models.json`, shell commands are resolved at
  request time. pi intentionally does not apply built-in TTL, stale reuse, or recovery logic for
  arbitrary commands."
- `compat` flags (OpenAI-side): `supportsStore`, `supportsDeveloperRole`,
  `supportsReasoningEffort`, `supportsUsageInStreaming` (`stream_options.include_usage`),
  `supportsFinishReason`, `maxTokensField` (`max_completion_tokens` vs `max_tokens`),
  `requiresThinkingAsText`, `thinkingFormat` in `reasoning_effort | openrouter | deepseek |
  together | baseten | zai | qwen | chat-template | qwen-chat-template`, `chatTemplateKwargs`,
  `thinkingTokenBudgetField` (`thinking_token_budget` vLLM / `thinking_budget` Qwen-SGLang /
  `thinking_budget_tokens` llama.cpp), `cacheControlFormat: anthropic`,
  `sessionAffinityFormat` (`openai | openai-nosession | openrouter`), `supportsStrictMode`,
  `supportsOpenAIGrammarTools`, `deferredToolsMode: kimi`, `supportsLongCacheRetention`,
  `openRouterRouting` (passed through as OpenRouter `provider` object). Anthropic-side:
  `supportsEagerToolInputStreaming`, `supportsCacheControlOnTools`, `forceAdaptiveThinking`,
  `allowEmptySignature`, `supportsStrictTools`.

**[INFERENCE]** Pi's `compat` block is what every "OpenAI-compatible" endpoint on this estate
actually needs and no other schema has: `supportsDeveloperRole=false` for llama.cpp/Ollama,
`maxTokensField`, `thinkingTokenBudgetField` per local server, `supportsUsageInStreaming`
for proxies that drop usage chunks. It is the missing "quirks" half of the estate schema.

### 7.2 Oh-my-pi (`can1357/oh-my-pi`, 28.9k stars, pushed 2026-09-02) - adds **discovery probes**

**[FACT, A (in-repo reference doc), 2026-09-02]** `docs/models.md`
(<https://raw.githubusercontent.com/can1357/oh-my-pi/main/docs/models.md>): config moved to
`~/.omp/agent/models.yml` (auto-migrates `models.json`); root may contain only `providers`
(unknown root keys fail validation). Provider adds over Pi: `auth: apiKey | none | oauth`,
`disableStrictTools`, **`discovery { type: ollama | llama.cpp | lm-studio |
openai-models-list | proxy | litellm, timeoutMs, injectV1 }`** ("optional per-provider HTTP
probe timeout in milliseconds"; `injectV1:false` for gateways rooted at e.g. `/v3/compat`;
`discovery.type: proxy` = "per-model wire auto-detected"), `transport: pi-native`
(`POST /v1/pi/stream` to an `omp auth-gateway`), `imageInputDecoder: stb`, `tokenizer` (pick an
embedded tokenizer: `claude-v3|claude-v47|claude-v5|claude-v5-sonnet|qwen3|deepseek-v3|kimi-k2|glm5`),
`compactionModel` and `remoteCompaction {enabled, api, endpoint, model, v2StreamingEnabled,
v2Endpoint, streamingEndpoint}`. `api` enum grows to `openai-completions | openai-responses |
openai-codex-responses | azure-openai-responses | anthropic-messages | bedrock-converse-stream |
google-generative-ai | google-gemini-cli | google-vertex`. Secrets: `apiKey`/`headers` may
start with `!` to run a command ("10 s timeout, stdout is trimmed, and empty/failing commands
are omitted"). Grade A for the doc; the repo also ships `docs/provider-compat-reference.md`,
`docs/provider-endpoint-constraints.md`, `docs/provider-quirks.md` (listed in tree, **not read
- UNVERIFIED content**).

### 7.3 What to copy verbatim / NATIVE-vs-BUILD

**[RECOMMENDATION]**
- COPY VERBATIM: Pi's `api` enum names (`openai-completions`, `openai-responses`,
  `anthropic-messages`, `google-generative-ai`) as the estate's `api.shape` values - they are
  precise, already used by two agents, and map 1:1 onto Codex (`responses`), Goose (`openai`/
  `anthropic`), Crush (`openai-compat`/`anthropic`) with a trivial rename table.
- COPY VERBATIM: Pi's value-resolution grammar for secrets (`$ENV`, `${ENV}`, `!cmd`, `$$`,
  `$!`) - it subsumes Catwalk's `$ENV`, Goose/Codex `env_key`, and Codex/Goose `auth.command`
  in one string form that lives comfortably in `.agents/local.json` *by name*.
- COPY VERBATIM: OMP's `discovery {type, timeoutMs, injectV1}` as the estate **health-probe
  descriptor** - it is the only surveyed schema that names the probe *kind* per local server
  (Ollama `/api/tags`, llama.cpp `/props` or `/v1/models`, LM Studio `/api/v0/models`,
  generic `/v1/models`) instead of assuming `/v1/models`.
- COPY (as optional sub-object): Pi `compat` verbatim, namespaced `quirks.openai.*` /
  `quirks.anthropic.*`.
- NATIVE-vs-BUILD: neither `pi` nor `omp` is on the installed list (DEDUP 5). Schema donors
  only; no renderer needed unless adopted.

## 8. Hermes Agent - `~/.hermes/config.yaml` `model:` + `providers:` (YAML)

### 8.1 The schema, from the shipped annotated example

**[FACT, A (annotated example config in repo, pushed 2026-09-02), 2026-09-02]**
`cli-config.yaml.example`
(<https://raw.githubusercontent.com/NousResearch/hermes-agent/main/cli-config.yaml.example>,
109 KB):

- `model: { default, provider: auto | openrouter | nous | nous-api | anthropic | openai-codex |
  copilot | gemini | zai | kimi-coding | minimax | minimax-cn | huggingface | nvidia | xiaomi |
  arcee | ollama-cloud | deepinfra | kilocode | ai-gateway | azure-foundry | lmstudio | custom
  (aliases ollama, vllm, llamacpp), base_url, api_key, auth_mode: entra_id, entra.scope,
  context_length, max_tokens, reasoning_effort, reasoning_overrides }`. `huggingface` is a
  first-class provider (`HF_TOKEN`); LM Studio is first-class (`http://127.0.0.1:1234/v1`).
  Doc-comment on `context_length`: "Leave unset - Hermes auto-detects the correct value from
  the provider. Set manually only when auto-detection is wrong (e.g. a local server with a
  custom num_ctx, or a proxy that doesn't expose /v1/models)."
- `providers: <name>: { base_url, key_env, key_cmd, api_key, api_mode: chat_completions |
  codex_responses | anthropic_messages | (bedrock_converse), model, extra_headers,
  request_timeout_seconds, stale_timeout_seconds, models{...per-model exceptions},
  transport_fallback }`. `api_mode` is **auto-detected per host** ("auto-detected as
  codex_responses for api.meta.ai"). Worked example: one Databricks gateway split into three
  entries (`dbx` chat_completions, `dbx-gpt` codex_responses, `dbx-claude` anthropic_messages)
  sharing one `key_cmd: "databricks auth token -p MY-PROFILE"`.
- **`key_cmd` contract (verbatim):** "print ONLY the token on stdout, either bare or as JSON
  with an `access_token` field (`expires_in` is honoured). Same shape as OAuth 2.0 token
  endpoints, Claude Code's `apiKeyHelper`, `gcloud auth print-access-token`, and `aws ecr
  get-login-password`." Precedence: `--api-key` > `key_cmd` > `api_key`/`key_env`. Distinct
  from `secrets.command` (runs once at startup, returns a `KEY=VALUE` blob).
- Header values "are treated as secrets and are never logged"; `extra_headers` supports
  `${ENV}` interpolation.

**[INFERENCE]** Hermes names the *third* API shape explicitly as `codex_responses` (not
`responses`), acknowledging that the Responses dialect Codex emits differs from vanilla; and
it is the only surveyed config that documents **both** a per-request refreshable `key_cmd`
*and* a startup-time bulk `secrets.command`, and explains when to use which. The
`request_timeout_seconds`/`stale_timeout_seconds` pair with "auto-disabled for local
endpoints" is the right shape for a memory-starved box where local cold-starts are slow.

### 8.2 What to copy verbatim / NATIVE-vs-BUILD

**[RECOMMENDATION]**
- COPY VERBATIM: the `key_cmd` output contract (bare token *or* `{access_token, expires_in}`
  JSON) as the estate's *one* token-helper contract - it is already compatible with Claude
  Code's `apiKeyHelper`, Codex `auth.command`, Goose `auth.command`, Pi `!cmd`.
- COPY VERBATIM: `request_timeout_seconds` + `stale_timeout_seconds` with the "local endpoints
  get longer defaults" rule; and the pattern **one registry entry per (host, api_mode)**.
- NATIVE-vs-BUILD: Hermes is not installed (DEDUP 5). Schema donor only.

## 9. Grok Build CLI (xAI) - `~/.grok/config.toml` `[model."<alias>"]` blocks

### 9.1 The schema, verbatim from the official reference

**[FACT, A (official docs, corroborated by a third-party integration guide), 2026-09-02]**
`[model.<alias>]` - "Custom / BYOK models (OpenAI-compatible or Anthropic Messages). Prefer
`env_key` over hardcoding `api_key`." Fields: `model` (id sent to the API), `base_url`
("Provider endpoint"), `name`, `description`, `api_key`, `env_key`, **`api_backend`:
`chat_completions | responses | messages`** (docs.x.ai/build/overview example shows the three
values inline; the third-party guide states "`chat_completions` maps to `/v1/chat/completions`
and is Grok's default" and "do not append `/chat/completions`"), `temperature`/`top_p`/
`max_completion_tokens`, **`context_window`** ("drives auto-compact timing"), `extra_headers`,
`supports_backend_search`, `supports_reasoning_effort` / `reasoning_effort`,
`stream_tool_calls` ("some BYOK endpoints need `false`"), `max_retries`,
`inference_idle_timeout_secs`. The in-repo user guide adds `query_params`,
`env_http_headers`, and **`env_key` as "a single string or an array of names"** ("The first
set, non-empty" wins) plus `[endpoints] models_base_url` from which per-model `base_url` is
inherited.
`[models]`: `default`, `web_search`, `session_summary`, `image_description`,
`default_reasoning_effort`, global `extra_headers`/sampling/`max_retries`/`stream_tool_calls`,
**`allowed_models` (glob list), `hidden_models`, `disabled_models`**.
Env: `GROK_MODELS_BASE_URL` ("model list from `{base}/models`"), `GROK_MODELS_LIST_URL`,
`GROK_XAI_API_BASE_URL`, `GROK_DEFAULT_MODEL`, `GROK_WEB_SEARCH_MODEL`.
Config layers: env -> user `~/.grok/config.toml` (or `$GROK_HOME`) -> project `.grok/config.toml`
(MCP/plugins/permission only) -> managed `managed_config.toml` -> `requirements.toml` policy
pins. Also `[compat.cursor]` / `[compat.claude]` scanners read Cursor and Claude skills, rules,
agents, MCP configs and hooks (default on).
Sources: <https://docs.x.ai/build/settings/reference>, <https://docs.x.ai/build/settings>,
<https://docs.x.ai/build/overview>,
<https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/11-custom-models.md>
(B: rendered via search snippet, raw not re-fetched), third-party guide
<https://live-turing-docs.cn.llm.tcljd.com/en/ai-coding-tools/grok-build/overview/> (C).

**[INFERENCE]** Grok Build's block is structurally the closest existing schema to what the
estate already writes for `[model."cursor-grok-4.6"]` (DEDUP 3): id + alias + base_url +
env_key + api_backend + context_window + reliability knobs. Its three-valued `api_backend`
is the same triad as Hermes' `api_mode` and Pi's `api`, confirming the estate needs exactly
these three (plus `ollama_native`/`gemini` for local/Google) in `api.shape`. The
`env_key` **array** form is unique and useful: `["CURSOR_AUTH2API_KEY", "OPENAI_API_KEY"]`
lets one rendered block tolerate two naming conventions without duplicating secrets.
`allowed_models` globs + `hidden_models`/`disabled_models` is the cleanest *picker policy*
vocabulary surveyed; `[compat.cursor]` means Grok Build already reads `.cursor/rules` and
Cursor `mcp.json` on this box - relevant to the `.agents/skills` SSOT lock (Grok scans, does not
own).

### 9.2 What to copy verbatim / NATIVE-vs-BUILD

**[RECOMMENDATION]**
- COPY VERBATIM: `env_key: string | string[]`, `context_window` semantics ("drives
  auto-compact timing" - i.e. it is *operational*, not informational), `stream_tool_calls`
  as a per-endpoint quirk, `inference_idle_timeout_secs`, and the `allowed_models` /
  `hidden_models` / `disabled_models` picker policy.
- NATIVE: `grok` + `agent.exe` are installed and already read `[model.*]` (DEDUP 5). The
  estate renderer should own the `[model."cursor-*"]` blocks (36 of them) and the
  `[models].allowed_models` list; verify with `grok models` / `grok inspect` after render.
- Health probe: `GET {base_url}/models` is what Grok itself uses for discovery
  (`GROK_MODELS_LIST_URL`), so the same probe result can be reused.

## 10. Claude Code - `settings.json` + `ANTHROPIC_*` env, `apiKeyHelper`, `modelOverrides`, `modelPricing`

### 10.1 The relevant keys, verbatim

**[FACT, A (official docs, 2026-09-02)]** Sources: <https://code.claude.com/docs/en/settings.md>,
<https://code.claude.com/docs/en/settings-reference.md>, <https://code.claude.com/docs/en/env-vars.md>,
<https://code.claude.com/docs/en/llm-gateway.md>.

- Endpoint/credential env (documented in `env-vars`): `ANTHROPIC_BASE_URL`,
  `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, `ANTHROPIC_CUSTOM_HEADERS`, `API_TIMEOUT_MS`,
  `CLAUDE_CODE_MAX_RETRIES`, `CLAUDE_CODE_SKIP_{BEDROCK,VERTEX,FOUNDRY,MANTLE,ANTHROPIC_AWS}_AUTH`,
  `CLAUDE_CODE_USE_{BEDROCK,VERTEX,FOUNDRY,MANTLE}`, `ANTHROPIC_FOUNDRY_{API_KEY,AUTH_TOKEN,BASE_URL,RESOURCE}`.
- Model-slot env: `ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU,FABLE}_MODEL`,
  `ANTHROPIC_SMALL_FAST_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS`,
  `MAX_THINKING_TOKENS`, `CLAUDE_CODE_EFFORT_LEVEL`, `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST`.
- Settings keys: `model`, `fallbackModel`, `availableModels` (managed allow-list that
  "constrains `/model`, `--model`, and the `model` key"), `enforceAvailableModels`,
  **`modelOverrides`** ("Map Anthropic model IDs to provider-specific model IDs, such as
  Amazon Bedrock inference profile ARNs"), **`modelPricing {multiplier (0,1], overrides{id:
  {input, output, cacheRead, cacheWrite}}}`** (USD per 1M, all four required; managed scope
  only; v2.1.242+), `modelSettings {<canonical-model>: {effortLevel}}` (v2.1.251+),
  `advisorModel`, `teammateDefaultModel`, `env` block, **`apiKeyHelper`** (shell command whose
  stdout is sent as both `X-Api-Key` and `Authorization: Bearer`; cached 5 min or
  `CLAUDE_CODE_API_KEY_HELPER_TTL_MS`; re-run on `401/403` and on expired-JWT output
  v2.1.246+), `awsAuthRefresh`, `awsCredentialExport`.
- Precedence rule worth quoting: "`ANTHROPIC_MODEL` exported in your shell applies over the
  `model` key from any file, while `ANTHROPIC_DEFAULT_MODEL` applies only when no file sets
  `model`." Settings files hot-reload, including `apiKeyHelper`.
- Gateway doc: "`ANTHROPIC_BASE_URL` is the variable that points Claude Code at the gateway.
  Setting only that variable, without a gateway credential, doesn't replace the
  subscription." Gateways forwarding to Anthropic "must forward the OAuth capability in
  `anthropic-beta`".

**[FACT + lock note]** The estate lock says OpenRouter is never Claude's `ANTHROPIC_BASE_URL`;
nothing above changes that. The `claude-cursor` wrapper (DEDUP 3) implies `ANTHROPIC_BASE_URL`
-> `127.0.0.1:8317` which requires auth2api to speak **Anthropic Messages** (`/v1/messages`) -
a third wire shape for the same port; **UNVERIFIED** from here, same must-probe as the Codex
`/v1/responses` case in 1.2.

### 10.2 What to copy verbatim / NATIVE-vs-BUILD

**[RECOMMENDATION]**
- COPY VERBATIM: `modelOverrides` (canonical id -> provider id map) and the *slot* vocabulary
  `opus|sonnet|haiku|small_fast|subagent` - the estate registry should expose named **slots**
  (`large`, `small`, `subagent`, `web_search`, `summary`, `embed`) that render to Claude's
  `ANTHROPIC_DEFAULT_*_MODEL`, Crush's `large/small`, Grok's `[models].web_search/
  session_summary`, Aider's `weak_model_name/editor_model_name`, Goose's `fast_model`.
- COPY VERBATIM: `modelPricing.overrides{id:{input,output,cacheRead,cacheWrite}}` field names
  (they equal Pi's `cost` names) and the `multiplier` idea for contracted/quota pricing -
  Cursor-quota models via auth2api have *effective* cost 0 with a quota budget; a
  `cost.multiplier: 0` + `budget: {unit: "requests", ...}` is the honest encoding.
- COPY VERBATIM: the `apiKeyHelper` contract (stdout token, TTL, re-run on 401/403) - identical
  in spirit to Hermes `key_cmd`, Codex/Goose `auth.command`; adopt one estate contract and
  render to all four.
- NATIVE: `claude` is installed; `~/.claude/settings.json` `env` + `model` keys are the render
  target (BUILD = renderer). Do **not** render `modelPricing` (managed-scope only; Claude
  ignores it in user settings - a renderer writing it there would silently no-op).

## 11. Synthesis - the best schema for a model endpoint, field by field

### 11.1 Cross-harness field matrix (who has what; A-grade artifacts cited in sections 1-10)

| Concern | Codex | OpenCode / models.dev (=Kilo) | Crush / Catwalk | Goose | Aider | Roo / Cline | Continue | Pi / OMP | Hermes | Grok Build | Claude Code |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Endpoint id + alias | `[model_providers.<id>] name` | `provider` key + `name` | `id`, `name` | `name`, `display_name` | `name` (model key) | `apiProvider` union | `name`, `provider` | provider key, model `name` | providers `<name>` | `[model."alias"]` + `model` | `modelOverrides` id map |
| `base_url` | base (`/v1`) | `api` / `url` | `base_url`, `api_endpoint` | **full route** | `api_base` (env) | `openAiBaseUrl` | `apiBase` | `baseUrl` | `base_url` | `base_url` (root; appends route) | `ANTHROPIC_BASE_URL` |
| API shape | `wire_api` = **responses only** | implied by `npm` pkg / `api` union | `type` enum (15, incl. `llamacpp/lmstudio/ollama/omlx`) | `engine` `openai\|anthropic\|ollama` | `litellm_provider` + `mode` | discriminated union | `provider` | `api` 4-9 values | `api_mode` 3-4 values (auto-detected) | `api_backend` 3 values | Anthropic only (+Bedrock/Vertex/Foundry switches) |
| Auth by env name | `env_key`, `env_http_headers` | `env: string[]` | `"$ENV"` string | `api_key_env`, typed `env_vars[]` | env conventions | inline value | `${{ secrets.X }}` | `$ENV`/`${ENV}` | `key_env` | `env_key: string\|string[]` | `ANTHROPIC_AUTH_TOKEN` etc. |
| Command-backed token | `auth {command,args,cwd,timeout_ms,refresh_interval_ms}` | - | `aws_auth_refresh` (cmd) | `auth {command,args,refresh_interval,timeout_seconds,cwd}` | - | - | - | `"!cmd"` (no TTL by design) | `key_cmd` (bare or `{access_token,expires_in}`) | - | `apiKeyHelper` (TTL 5 min, re-run on 401/403) |
| Extra headers / body | `http_headers`, `query_params` | `request.{headers,body}` per provider *and* model | `extra_headers`, `extra_body` | `headers` | `extra_params.extra_headers` | `openAiHeaders` | `requestOptions.headers/extraBodyProperties` | `headers`, `samplingParams` | `extra_headers` | `extra_headers`, `query_params`, `env_http_headers` | `ANTHROPIC_CUSTOM_HEADERS` |
| Context / output limits | (model-side) | `limit.{context,input,output}` | `context_window`, `default_max_tokens` | `context_limit`, `max_tokens` | `max_input_tokens`, `max_output_tokens` | `contextWindow`, `maxTokens`, `maxThinkingTokens` | `contextLength`, `maxTokens` | `contextWindow`, `maxTokens` | `context_length`, `max_tokens` | `context_window` (drives compaction) | `CLAUDE_CODE_MAX_OUTPUT_TOKENS` |
| Tool support flag | `supports_standalone_web_search` | `tool_call` / `capabilities.tools` | (implied) | - | `supports_function_calling`, `supports_tool_choice` | `supportsTools`, `excludedTools[]` | `capabilities: [tool_use]` | compat `supportsStrictMode` etc. | - | `stream_tool_calls` | - |
| Cost | - | `cost.{input,output,reasoning,cache_read,cache_write}` /1M, tiers | `cost_per_1m_*` | via canonical catalog | per-token (LiteLLM) | `inputPrice`..., `tiers[]` | - | `cost{input,output,cacheRead,cacheWrite,tiers[]}` | - | - | `modelPricing.overrides{input,output,cacheRead,cacheWrite}` |
| Capability flags | `supports_websockets` | `reasoning`, `attachment`, `structured_output`, `temperature`, `interleaved`, `modalities`, `status`, `open_weights`, `knowledge` | `can_reason`, `reasoning_levels`, `supports_attachments` | `preserves_thinking`, `supports_streaming` | `use_temperature`, `reasoning_tag`, `edit_format` | 20+ (`supportsPromptCache`, `promptCacheRetention`, `supportsReasoningBudget/Binary/Effort`, `isFree`, `deprecated`) | `roles[]`, `capabilities[]` | `reasoning`, `input[]`, `thinkingLevelMap`, `compat.*` (25+ quirks) | `reasoning_effort` | `supports_reasoning_effort`, `supports_backend_search` | `modelSettings.effortLevel` |
| Reliability knobs | `request_max_retries`, `stream_max_retries`, `stream_idle_timeout_ms`, `websocket_connect_timeout_ms` | - | - | `timeout_seconds` | `streaming` | `rateLimitSeconds` | `requestOptions.timeout/verifySsl/proxy/caBundlePath` | - | `request_timeout_seconds`, `stale_timeout_seconds` | `max_retries`, `inference_idle_timeout_secs` | `API_TIMEOUT_MS`, `CLAUDE_CODE_MAX_RETRIES` |
| Health / discovery probe | `ModelProviderCapabilitiesRead` (declared, not live) | `/v1/models` via SDK; catalog TTL 5 min + flock + 60 min refresh | `discover_models` (`/v1/models`, user wins) | `dynamic_models` (`/v1/models`, 404 -> static) | - | `dynamicProviders` list fetch | autodetect | **`discovery {type: ollama\|llama.cpp\|lm-studio\|openai-models-list\|proxy, timeoutMs, injectV1}`** | auto-detect `api_mode` + context via `/v1/models` | `GROK_MODELS_LIST_URL` `{base}/models` | - |
| Sidecar / slot models | - | - | `default_large_model_id`, `default_small_model_id` | `fast_model` | `weak_model_name`, `editor_model_name` | - | `roles[]` | `compactionModel` | - | `[models].web_search/session_summary/image_description` | `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL` |
| Picker policy | - | `disabled`, `enabled` | `disable`, `hidden` | `setup.*` | - | `deprecated`, `isStealthModel` | - | `modelOverrides` | - | `allowed_models` globs, `hidden_models`, `disabled_models` | `availableModels` (managed), `enforceAvailableModels` |
| Secret-value grammar | env name only | env name only | `"$ENV"` | env name only | env | inline | `${{ secrets }}` | `$E`, `${E}`, `!cmd`, `$$`, `$!` | `${ENV}`, `key_cmd` | env name (array ok) | env / helper |

### 11.2 The extracted "best" endpoint record (RECOMMENDATION; fits `.agents/agents.json` conventions)

**[FACT, A, 2026-09-02]** The estate's `.agents/agents.json` MCP records already use `label`,
`description`, `targets[]`, `enabled`, `transport`, `url`, `requiredEnv[]`, `credentialNames[]`,
`x_codex {...}` per-runtime extension blocks, `${ENV}` interpolation and `tags[]` (read from
the repo at `main`). A model-endpoint record should reuse those exact conventions rather than
invent new ones.

**[RECOMMENDATION]** Proposed `models.endpoints.<id>` record. Every field name below is
*copied verbatim* from the harness named in the trailing comment; nothing is invented except
the top-level nesting, which mirrors the existing MCP records.

```jsonc
"models": {
  "catalog_snapshot": { "source": "https://models.dev/api.json", "pinned_sha256": "...", "fetched": "2026-09-02" }, // OpenCode/Goose: models.dev is the lingua franca
  "slots": { "large": "cursor/cursor-claude-fable-5-1", "small": "hf/zai-org/GLM-5.3", "subagent": "...", "web_search": "...", "summary": "...", "embed": null }, // Crush large/small, Claude *_MODEL, Grok web_search/session_summary, Aider weak/editor, Goose fast_model
  "endpoints": {
    "cursor-auth2api": {
      "label": "Cursor quota via auth2api",                 // estate MCP convention
      "targets": ["goose", "grok", "fabric", "aider", "opencode", "codex", "claude"], // estate MCP convention
      "enabled": true,
      "base_url": "http://127.0.0.1:8317/v1",              // Codex/Crush/Grok: BASE, renderer appends route
      "api": ["openai-completions"],                        // Pi enum; may hold several: "openai-responses", "anthropic-messages" once PROBED (see 1.2, 10.1)
      "env_key": ["CURSOR_AUTH2API_KEY", "OPENAI_API_KEY"], // Grok: string|string[] ; secret BY NAME (lock)
      "auth": null,                                         // Codex/Goose {command,args,cwd,timeout_ms,refresh_interval_ms}; Hermes key_cmd output contract
      "env_vars": [ { "name": "AUTH2API_HOST", "required": false, "secret": false, "default": "http://127.0.0.1:8317", "description": "..." } ], // Goose typed non-secret env
      "headers": {}, "env_http_headers": {}, "query_params": {}, // Codex
      "request": { "headers": {}, "body": {} },             // OpenCode per-endpoint override
      "discovery": { "type": "openai-models-list", "timeoutMs": 5000, "injectV1": true }, // OMP probe descriptor
      "reliability": { "request_max_retries": 4, "stream_max_retries": 5, "stream_idle_timeout_ms": 300000, "request_timeout_seconds": 300, "stale_timeout_seconds": 90 }, // Codex + Hermes
      "quirks": { "supportsDeveloperRole": true, "supportsUsageInStreaming": true, "maxTokensField": "max_tokens", "stream_tool_calls": true }, // Pi compat + Grok
      "cost": { "multiplier": 0, "budget": { "unit": "requests", "note": "Cursor quota; see auth2api" } }, // Claude modelPricing.multiplier; honest zero-cost encoding
      "models": {
        "cursor-grok-4.6": { "models_dev": null, "limit": { "context": 1000000, "output": 32000 }, "tool_call": true, "reasoning": true, "attachment": false, "status": "active", "roles": ["chat","edit","apply"] } // models.dev names + Continue roles + OpenCode status
      },
      "picker": { "allowed_models": ["cursor-*"], "hidden_models": [], "disabled_models": [] }, // Grok Build
      "x_codex": { "wire_api": "responses", "requires_openai_auth": false }, // only if the /v1/responses probe passes
      "x_goose": { "engine": "openai", "route": "/chat/completions", "dynamic_models": true },
      "x_aider": { "weak_model_name": "openai/cursor-grok-4.6", "edit_format": "diff", "use_repo_map": true },
      "x_claude": { "slot_env": "ANTHROPIC_DEFAULT_SONNET_MODEL" },
      "credentialNames": ["CURSOR_AUTH2API_KEY"],           // estate MCP convention
      "tags": ["local", "quota", "shared"]
    }
  }
}
```

Design rules that fall out of the teardown (each cites the section it came from):

1. **`api` is a list, per endpoint, not per provider** (1.2, 8.1, 10.1): one host can speak
   several dialects; consumers pick the one they need; the renderer refuses to emit a Codex
   block when `"openai-responses"` is absent instead of silently writing a config that hard-errors.
2. **Store the base, derive the route** (4.3): Goose's full-route `base_url` is the only outlier.
3. **Secrets by name, three forms, one grammar** (3.1, 7.1, 8.1, 10.1): `env_key[]`,
   `auth.command` with the Hermes/Claude stdout contract, and Pi's `$E`/`!cmd` string grammar
   for headers. Never a value. Never rotation (lock).
4. **Model metadata = models.dev names** (2.1, 4.2): `tool_call`, `reasoning`, `attachment`,
   `structured_output`, `temperature`, `limit.*`, `cost.*`, `modalities.*`, `status`,
   `release_date`, `knowledge`, `open_weights`, plus a `models_dev` pointer so the nightly
   snapshot can fill the rest.
5. **Quirks are first-class** (7.1, 9.1): Pi `compat` + Grok `stream_tool_calls` - the reason
   "OpenAI-compatible" endpoints fail in practice.
6. **Probe descriptor per endpoint** (7.2, 3.1, 4.1): OMP `discovery.type` decides *which* URL
   to hit; result feeds `models{}` with **user entries winning** (Crush rule).
7. **Slots, not hard-coded sidecars** (10.2): render `slots.*` into every runtime's own
   small/large/subagent vocabulary.
8. **Per-runtime extension blocks `x_<runtime>`** (estate convention) hold what only that
   runtime understands (Codex `wire_api`, Aider `edit_format`), never duplicated upward.

### 11.3 Materialization matrix (how each installed runtime consumes the record)

| Runtime (installed per DEDUP 5) | File written by the renderer | Native mechanism it rides | Probe before render |
| --- | --- | --- | --- |
| Codex | `~/.codex/config.toml` `[model_providers.<id>]` + `[profiles.*]` | NATIVE reads TOML; `wire_api="responses"` mandatory | `POST {base}/responses` must 200 |
| Goose 1.47 | `~/.config/goose/custom_providers/<id>.json` (Windows `%APPDATA%\Block\goose\config\custom_providers\`) | NATIVE `load_custom_providers` | `GET {base}/models` (or static list) |
| Grok Build | `~/.grok/config.toml` `[model."<alias>"]` + `[models].allowed_models` | NATIVE; `grok models` verifies | `GET {base}/models` |
| Claude Code | `~/.claude/settings.json` `env` + `model` (never `modelPricing`) | NATIVE; hot-reload | `POST {base}/messages` if `anthropic-messages` claimed |
| Aider 0.86 | `~/.aider.model.settings.yml` + `~/.aider.model.metadata.json` | NATIVE two-file split | none (static) |
| OpenCode | `~/.config/opencode/opencode.json` `provider.<id>` | NATIVE; v2-compat maps old keys | `GET {base}/models` |
| Fabric 1.4.470 | vendor-specific env (`OPENAI_API_BASE_URL`-style) [UNVERIFIED exact key for 1.4.470] | NATIVE | `GET {base}/models` |
| Ollama / LM Studio (`lms`) | no render; they are *endpoints*, registered with `discovery.type: ollama` / `lm-studio` | NATIVE servers | `/api/tags` / `/api/v0/models` |
| Cline / Roo / Kilo / Continue / Pi / OMP / Hermes / Crush | not installed - **schema donors only**, no renderer | - | - |

**[RECOMMENDATION]** Build order that respects "never remove a feature to buy reliability":
(a) write the record + probe script first (read-only; probes only `GET /models` and one
1-token completion per claimed `api`), (b) render Goose/Grok/Aider/OpenCode (chat-completions
consumers, already working today), (c) render Codex and Claude *only for endpoints whose
`responses`/`messages` probe passed* - the existing `codex-cursor`/`claude-cursor` wrappers
stay untouched until then (tradeoff: they may already be broken by 1.2; the probe tells us,
the renderer does not guess).

<!-- section 12 rubric appended below -->
