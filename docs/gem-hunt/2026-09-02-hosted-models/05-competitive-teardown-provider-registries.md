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

<!-- sections 4..N appended below; rubric table last -->
