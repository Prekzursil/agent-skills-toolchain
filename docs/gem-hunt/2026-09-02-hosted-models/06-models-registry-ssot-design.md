# Gem-hunt 2026-09-02 / hosted models / lens 06: models registry SSOT + materializers (design)

Lens id: `06-models-registry-ssot-design`
Branch: `gemhunt/hosted-models-06-models-registry-ssot-design`
Status: IN PROGRESS (sections land incrementally; each push is a checkpoint)
Mode: discovery + design only. No code changed. No PR.

## 0. Scope, dedup-set, estate locks

**Question this lens answers.** What should the one authoritative description of "which
model endpoints exist in this estate, how each is reached, what each can do, what each
costs, and which runtime consumes it" look like, and how does it get *materialized* into
the nine runtime configs that already exist on the box without a second orchestration
runtime?

**Dedup-set (exists; not re-proposed here, only referenced):**
1. `.agents/skills/hosted-model-agents` on branch `live-capture/2026-09-02` - the doctrine
   for hosted/local models.
2. `tools/mcp/glm53-space` on `main` - hardcoded to `router.huggingface.co/v1` +
   `zai-org/GLM-5.3`; owner has decided to DEPRECATE and replace with a general layer.
3. `auth2api` on `127.0.0.1:8317` - the ONLY Cursor-quota OpenAI-compatible bridge.
4. Registry `.agents/agents.json` (`mcp.servers`, 42 servers) + secrets by NAME only in
   `.agents/local.json`.
5. Installed runtimes: claude, codex, cursor-agent, grok + agent.exe, goose 1.47,
   fabric 1.4.470, agy, gemini CLI, opencode, aider 0.86, ollama, lms, ralph; services
   basic-memory :8765, agent-mail :8812, browser-bridge :8770.

**Estate locks (constraints; every design decision below is checked against them):**
- L1 OpenRouter = spend-capped CLI/Codex sidecar only. Never Cursor BYOK, never Claude
  `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP.
- L2 No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory.
- L3 auth2api :8317 stays the only Cursor bridge; retires within 7 days of official
  Cursor `/v1` GA.
- L4 Ports 8765 / 8812 / 8317 are owned.
- L5 `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it).
- L6 Never rotate credentials.
- L7 Never remove a feature to buy reliability; present tradeoffs instead.

**Evidence grading used throughout.**
- Tier A = primary source (vendor docs, repo source, this repo's own files) read today.
- Tier B = reputable secondary (release notes, maintainer issues/PRs).
- Tier C = community / blog / inferred from code.
- `corroborated` = two independent sources agree; `UNVERIFIED` = single source or not
  re-checked today. Every citation carries the date checked (2026-09-02 unless noted).
- Labels: **[FACT]** sourced, **[INFER]** inference from facts, **[REC]** recommendation.

## 1. What exists on main today (repo evidence)

All Tier A, read 2026-09-02 from `origin/main` @ `5fa34fda1` unless a branch is named.

**1.1 The MCP registry is already a validated, target-aware SSOT with materializers.**
- **[FACT]** `.agents/agents.json` top-level keys: `schemaVersion, instructions, integrations,
  syncMode, mcp, workspace, lastSync, lastSyncSourceHash`; `mcp` = `{policy, supervision,
  servers}`; 42 servers. (Tier A, `.agents/agents.json`.)
- **[FACT]** `.agents/scripts/mcp_control_plane.py` is the validator + publication library:
  `VALID_TARGETS = {"claude","codex"}`; credentials only as `${ENV_NAME}` or `keyring://`
  references (`ENV_REFERENCE_RE`, `KEYRING_REFERENCE_RE`); a `LITERAL_SECRET_RE` that rejects
  `hf_`, `sk-`, `ghp_` ... literals; `credentialNames` must exactly equal the sensitive subset of
  `requiredEnv`; credential-bearing http servers must be `https://`; `singletonKey` dedup;
  `maxPrivateBytes` with a 512 MiB default and a mandatory `resourceException` prose above it;
  `healthProbe.kind in {mcp-tools-list, http, command, none}`; `atomic_write_text` does
  tmp + fsync + `os.replace`; `assert_exact_target_parity` fails closed when the rendered set
  differs from the selected set. (Tier A, lines 15-50, 143-313, 385-437, 439-458.)
- **[FACT]** `merge_generated_codex_mcp.py` merges into `~/.codex/config.toml` by splitting the
  live file into `[section]` blocks (`SECTION_RE`), recognising `mcp_servers.<name>[.suffix]`
  headers, removing only registry-named blocks whose suffix is "replaceable"
  (`None, env, http_headers, env_http_headers`), preserving every non-MCP block and any
  local-only sub-block, then appending regenerated blocks; `RETIRED_MCP_SERVERS = {"memory",
  "codex_consult"}` are purged if found; a `promptbridge-codex managed` marker pair is stripped
  as legacy. (Tier A, lines 15-23, 32-59, 213-241.)
- **[FACT]** `merge_generated_claude_mcp.py` merges into `~/.claude.json` `mcpServers`, wraps
  `npx/npm/node` in `cmd /c` on Windows, sets `"type": "http"` because an entry with `url` but no
  `type` is silently read as stdio and never mounts, pops plugin-provided servers
  (`CLAUDE_PLUGIN_PROVIDED_SERVERS`) and the retired `memory`, optional timestamped `--backup`.
  (Tier A, lines 26-31, 60-101, 160-187.)
- **[FACT]** `merge_generated_cursor_mcp.py` merges into `~/.cursor/mcp.json`; the registry carries
  a closed `x_cursor.stdio_bridge` extension (only key allowed) rendered as a per-session stdio
  shim in front of an http server; a bridge may not carry headers or bearer creds. (Tier A,
  `mcp_control_plane.py` lines 316-357; script docstring line 2.)
- **[FACT]** Per-runtime extension blocks already exist as a pattern: `x_codex`
  (`bearer_token_env_var`, `startup_timeout_sec`, `tool_timeout_sec`, `env_vars`) and `x_cursor`.
  Both are validated closed. (Tier A.)
- **[INFER]** The models registry should reuse, not fork, this machinery: same reference-only
  credential rule, same closed `x_<runtime>` extension pattern, same block-preserving merge for
  TOML targets, same key-preserving merge for JSON targets, same fail-closed parity assertion.

**1.2 The two things being deprecated.**
- **[FACT]** `glm53-space` is registered in `agents.json` as a Claude-only stdio server launched by
  `uv run --locked --directory ...\tools\mcp\glm53-space python mcp_server.py`, env
  `HUGGINGFACE_TOKEN=${HUGGINGFACE_TOKEN}`, tags `hosted-inference, owner-requested`. Its
  description: "On-demand GLM 5.3 adapter using Hugging Face's official OpenAI-compatible
  inference router. Exposes one text-only chat tool ..." (Tier A, `agents.json`.)
- **[FACT]** The directory `tools/mcp/glm53-space/` is **not present** on `origin/main` @
  `5fa34fda1` and `git log --all -- tools/mcp/glm53-space` is empty in this clone: the registry
  entry points at a path that this checkout cannot resolve. (Tier A, measured; the task brief
  says it is "on main" - treat that as the owner's live box, where the tree exists under
  `~/source/agent-skills-toolchain`. UNVERIFIED which of the 178 checkouts carries it.)
- **[FACT]** `qwen-space-tool-api` exists on `origin/live-capture/2026-09-02` as a skill already
  marked `status: deprecated` with a redirect to `hosted-model-agents` and to its own
  `reference.md` (the Space's wire contract). (Tier A, that branch, `skills/qwen-space-tool-api/SKILL.md`.)
- **[FACT]** The estate's tombstone convention is documented in `.agents/skills/codex-consult/SKILL.md`:
  frontmatter `description: RETIRED <date> - redirect tombstone ...`, body says "Do not follow the
  old procedure", a "Use instead" table, and a "Why a tombstone and not a deletion" paragraph ("a
  tombstone resolves and redirects; a missing skill fails opaquely"). (Tier A.)
- **[FACT]** The `huggingface` server description already states the layer split this lens must
  preserve: "Inference runtimes (Space Gradio, Space OpenAI /v1, Endpoints) are separate; skill
  hosted-model-agents. Do not register a raw inference URL as a second Hub MCP." (Tier A.)

**1.3 The doctrine skill this lens must be consistent with.**
- **[FACT]** `hosted-model-agents/SKILL.md` (branch `live-capture/2026-09-02`) hard rule 2: "An
  inference URL is not Hub MCP ... Do not register every GPU URL in `agents.json` as MCP - that
  explodes the tool catalogue." Hard rule 3: "The hosted model proposes; the harness executes."
  `environments.md` lists the surfaces: HF Hub MCP / Space Gradio / Space OpenAI `/v1` / Inference
  Endpoints-TGI-vLLM; Modal, RunPod, Lightning via `cloud-infra-toolchain`; Azure AI Foundry via
  `microsoft-foundry`; local llama-server, LM Studio, Ollama; Cursor Max via auth2api `:8317`
  (G-32); G-36 = at most one `cursor-agent` process. (Tier A.)
- **[INFER]** Therefore the models registry must be a *data* file consumed by process-local
  clients and materializers - NOT 20 new MCP servers. The one MCP it justifies is the single
  generic inference tool (section 5), which is exactly the "general integration layer" the owner
  wants glm53-space replaced by.

**1.4 Existing provider-config precedents in the estate (what materializers must not break).**
- **[FACT]** `openrouter-routing/SKILL.md`: Codex gets a **non-default** `[model_providers.openrouter]`
  with `base_url = "https://openrouter.ai/api/v1"`, `env_key = "OPENROUTER_API_KEY"`,
  `wire_api = "responses"` ("Codex no longer accepts `chat`"); opt-in via `codex --profile openrouter`.
  Same file: never Cursor BYOK, never `ANTHROPIC_BASE_URL` to OpenRouter, no LiteLLM, no OpenRouter
  MCP; a normal key can *read* its own limits via `GET /api/v1/key`. (Tier A; matches locks L1/L2.)
- **[FACT]** `~/.agents/local.json` is the secrets file: `browser-bridge/lib/load-bridge-auth.mjs`
  and `ensure_bridge_auth.py` read `chromeBridge.*` tokens from it and "never log token values";
  `SECURITY.md` lists `local.json` as protected. (Tier A.)
- **[INFER]** `local.json` is a *nested JSON object* keyed by feature (e.g. `chromeBridge.agentToken`),
  not a flat env map. The models registry therefore needs an explicit `auth.env` NAME plus an
  optional `auth.localJsonPath` (JSON-pointer into local.json) so a resolver can find the value
  without the registry ever holding it.

## 2. Runtime provider surfaces: what each runtime can natively take

The materializer design (section 4) is only as good as the facts in this table. Each row:
config file, schema, auth shape, wire API accepted, and the sharp edge that a naive generator
would trip.

### 2.1 Codex CLI - `~/.codex/config.toml` `[model_providers.<id>]`
- **[FACT]** Keys: `name, base_url, env_key, env_key_instructions, wire_api, query_params,
  http_headers, env_http_headers, request_max_retries (4), stream_max_retries (5),
  stream_idle_timeout_ms (300000), supports_websockets, requires_openai_auth,
  experimental_bearer_token, auth, aws, websocket_connect_timeout_ms,
  supports_standalone_web_search`. Defaults from `developers.openai.com/codex/config-reference`.
  (Tier B corroborated: [alexdunlop.com config.toml write-up](https://www.alexdunlop.com/writing/codex-cli-config-toml),
  [codex.danielvaughan.com custom providers guide 2026-04-23](https://codex.danielvaughan.com/2026/04/23/codex-cli-custom-model-providers-configuration-guide/);
  the primary `developers.openai.com/codex/config-reference` timed out on fetch today - UNVERIFIED direct.)
- **[FACT]** `wire_api = "chat"` was **removed** (deprecation in discussion #7782 2025-12-09; removal
  PR #10157, Feb 2026, Codex 0.59). Only `"responses"` is accepted and it is the default. (Tier B
  corroborated, same two sources + [openai/codex issue #41816](https://github.com/openai/codex/issues/41816).)
- **[FACT] SHARP EDGE:** a single **inert** `[model_providers.x]` block with `wire_api = "chat"` makes
  *every* Codex command fail at config load, even `codex login status`
  ([openai/codex#41816](https://github.com/openai/codex/issues/41816), Tier A issue text, 2026).
  **[INFER]** A Codex materializer must therefore (a) never emit `wire_api = "chat"`, (b) only emit
  providers whose endpoint has capability `wire.responses != absent`, and (c) run a
  `codex --version`-class smoke after every write, because a bad block bricks the whole runtime
  (the estate's Codex is a primary rail - see L7: present the tradeoff, don't drop the endpoint;
  route chat-only endpoints to Codex through the inference MCP of section 5 instead).
- **[FACT]** Estate precedent already in this shape: `[model_providers.openrouter]` with
  `env_key = "OPENROUTER_API_KEY"`, `wire_api = "responses"`, non-default, opt-in via
  `--profile openrouter` (Tier A, `openrouter-routing/SKILL.md`; lock L1).
- **[FACT]** Built-in provider ids `openai`, `ollama`, `lmstudio` exist and must not be shadowed.
  (Tier B, danielvaughan guide.)

### 2.2 Grok Build CLI (`grok` + `agent.exe`) - `~/.grok/config.toml` `[model."<id>"]`
- **[FACT]** Per-model block keys: `model, base_url, name, description, api_key, env_key (string
  OR array of names; first non-empty wins), api_backend = chat_completions | responses | messages,
  temperature, top_p, max_completion_tokens, context_window, extra_headers, query_params,
  supports_backend_search, supports_reasoning_effort, reasoning_effort, stream_tool_calls,
  max_retries, inference_idle_timeout_secs`. `[models] default = "<id>"`, `[models] web_search`.
  `[endpoints] models_base_url` lets `[model.*]` blocks inherit `base_url`. Windows path
  `%USERPROFILE%\.grok\config.toml`; `GROK_HOME` overrides. Credential precedence: per-model
  `api_key` > `env_key` > signed-in session token > `XAI_API_KEY` global. (Tier A:
  [docs.x.ai/build/settings](https://docs.x.ai/build/settings) and
  [xai-org/grok-build user-guide/11-custom-models.md](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/11-custom-models.md), 2026-09-02.)
- **[FACT]** Grok Build was open-sourced (Apache-2.0, `xai-org/grok-build`) on 2026-07-15; upstream
  does not accept external PRs. (Tier B, [MarkTechPost 2026-07-15](https://www.marktechpost.com/2026/07/15/spacexai-open-sources-grok-build-the-rust-agent-harness-tui-and-tool-layer-behind-its-coding-cli/).)
- **[INFER]** Grok is the *most permissive* target: it accepts chat-completions, responses AND
  Anthropic messages, per model, with an env_key *array* - so the materializer can emit one block
  per (endpoint, model) pair for every endpoint in the registry, and can list several env names
  (e.g. `["HUGGINGFACE_TOKEN","HF_TOKEN"]`) without a resolver. The dedup-set item
  `[model."cursor-grok-4.6"]` pointing at auth2api is exactly this shape (L3).
- **[FACT] SHARP EDGE:** `api_key = "..."` literal is allowed by Grok; the estate rule (control
  plane `LITERAL_SECRET_RE`) forbids emitting it. Materializer must only ever write `env_key`.

### 2.3 Goose 1.x - `~/.config/goose/custom_providers/<name>.json` (Windows: `%APPDATA%\Block\goose\config\custom_providers\`)
- **[FACT]** One JSON file per provider: `name, engine (openai|anthropic|ollama), display_name,
  description, api_key_env, base_url, base_path (default v1/chat/completions), models[{name,
  context_limit, input_token_cost, output_token_cost}], headers, timeout_seconds,
  supports_streaming, requires_auth (default true), catalog_provider_id, env_vars (list of env
  names expanded inside base_url)`. Registered automatically at startup by
  `register_declarative_providers`. Selection precedence: subagent settings > recipe > env
  `GOOSE_PROVIDER/GOOSE_MODEL` > config.yaml > default. (Tier A:
  [block/goose providers.md](https://github.com/block/goose/blob/main/documentation/docs/getting-started/providers.md),
  [declarative_providers.rs](https://github.com/block/goose/blob/58f3cc9e/crates/goose/src/config/declarative_providers.rs),
  [CUSTOM_DISTROS.md](https://github.com/block/goose/blob/main/CUSTOM_DISTROS.md), 2026-09-02.)
- **[INFER]** Goose is the *cleanest* materializer target: file-per-provider means idempotency is
  "overwrite the files we own, delete the ones we no longer generate, never touch files without
  our marker" - no in-file merging at all. Dedup-set item `GOOSE_PROVIDER=goose-cursor-proxy` is
  already one such file (L3).
- **[FACT] SHARP EDGE:** `headers` values are literal strings (the docs example puts a secret in
  `x-origin-secret`). Estate rule: never emit a header whose *name* matches `SECRET_NAME_RE`
  unless its value is resolvable via `env_vars`; otherwise skip the endpoint for Goose and say so.

### 2.4 Fabric (danielmiessler, Go) 1.4.x - `~/.config/fabric/.env` + `~/.config/fabric/config.yaml`
- **[FACT]** Generic OpenAI-compatible vendor: `OPENAI_API_KEY`, `OPENAI_API_BASE_URL` (must end in
  `/v1`), `DEFAULT_VENDOR`, `DEFAULT_MODEL`, `DEFAULT_MODEL_CONTEXT_LENGTH`. Dedicated local
  vendors: `LM_STUDIO_API_URL` (**must include `/v1`** or model listing fails), `OLLAMA_API_URL`.
  (Tier A issue threads: [Fabric#1558](https://github.com/danielmiessler/Fabric/issues/1558),
  [Fabric#928](https://github.com/danielmiessler/Fabric/issues/928), [discussion #138](https://github.com/danielmiessler/Fabric/discussions/138).)
- **[FACT] SHARP EDGE:** Fabric's OpenAI vendor defaults to the **Responses API**; against
  llama-server it 404s on `POST /v1/responses`. Fix since 1.4.257: `--disable-responses-api` or
  `disableResponsesAPI: true` in `~/.config/fabric/config.yaml`. The flag is **global** (all
  OpenAI-compatible vendors), which is a tradeoff the materializer must surface, not hide.
  ([Fabric#1625](https://github.com/danielmiessler/Fabric/issues/1625), Tier A, fix confirmed by maintainer.)
  Estate Fabric is 1.4.470 (task brief) so the flag exists.
- **[FACT]** Fabric has a compiled-in list of OpenAI-compatible vendors, each with its own
  `<VENDOR>_API_KEY` / `<VENDOR>_API_BASE_URL` pair (e.g. `fabric -L` shows `Together|...`,
  `LM Studio|...`). (Tier A, #928 output.) **[INFER]** the exact vendor list lives in
  `internal/plugins/ai/openai_compatible/configs.go`; the materializer should read Fabric's own
  `fabric -L` output to discover which env-pairs the installed build honours rather than hardcoding
  (UNVERIFIED file path today).
- **False friend:** `fabric-docs-3kh.pages.dev` describes a *different* Rust "Fabric" (Postgres,
  `[[providers.custom_openai_endpoints]]`) - not the estate's binary. Do not cite it for 1.4.470.

### 2.5 OpenCode - `~/.config/opencode/opencode.json` (or project `opencode.json`) `provider.<id>`
- **[FACT]** Shape: `provider.<id> = { npm: "@ai-sdk/openai-compatible", name, options: { baseURL,
  apiKey: "{env:VAR}" | "{file:~/path}" }, models: { <model-id>: { name, limit: {context,
  output}, options: {...} } } }`, `$schema: https://opencode.ai/config.json`, top-level
  `model: "<provider-id>/<model-id>"`. (Tier A issue reproductions:
  [anomalyco/opencode#5674](https://github.com/anomalyco/opencode/issues/5674),
  [#19946](https://github.com/anomalyco/opencode/issues/19946), [#23622](https://github.com/anomalyco/opencode/issues/23622).)
- **[FACT] SHARP EDGES:** (a) a provider id containing a dot silently drops model options
  (#23622, fix PR #25145); (b) `{env:VAR}` resolves against the *process* environment only - no
  `.env` autoload, so a desktop-launched OpenCode sees an empty key (#19946, maintainer note,
  closed not-reproducible on v1.17.13); (c) the historical `options` forwarding bug (#5674) is
  fixed but shows the SDK reads options under the `openai` namespace.
- **[INFER]** Materializer: dot-free ids (`hf-router`, not `router.huggingface.co`), `{env:NAME}`
  only, and the launch wrapper (not the config) must export the env from `local.json`.

### 2.6 Aider 0.86 - env / `.aider.conf.yml` / `.aider.model.metadata.json` / `.aider.model.settings.yml`
- **[FACT]** Generic OpenAI-compatible path: `OPENAI_API_BASE` + `OPENAI_API_KEY` (or
  `--openai-api-base`, env `AIDER_OPENAI_API_BASE`), model named `openai/<id>`; unknown models get
  context/cost from `.aider.model.metadata.json` (dict keyed by the fully-qualified
  `provider/model`; `litellm_provider` must equal the prefix; fields `max_input_tokens,
  max_output_tokens, input_cost_per_token, output_cost_per_token`) and behaviour from
  `.aider.model.settings.yml` (list of `{name, edit_format, use_repo_map, extra_params, ...}`;
  `aider/extra_params` applies to all). Load order home -> repo root -> cwd -> `--model-*-file`,
  last wins. Other knobs: `--alias`, `--set-env NAME=value`, `--api-key PROVIDER=KEY`.
  (Tier A: [aider.chat adv-model-settings](https://aider.chat/docs/config/adv-model-settings.html),
  [options reference](https://aider.chat/docs/config/options.html), 2026-09-02.)
- **[FACT] SHARP EDGE:** one `OPENAI_API_BASE` per process - Aider cannot hold several
  OpenAI-compatible bases simultaneously. Metadata-file regressions have happened before
  ([Aider-AI/aider#2928](https://github.com/Aider-AI/aider/issues/2928): 0.72.1 stopped reading the
  file; "LLM Provider NOT provided" when the prefix is missing).
- **[INFER]** Materializer for Aider = (a) one shared `~/.aider.model.metadata.json` +
  `~/.aider.model.settings.yml` covering every registry model (pure data, safe to merge by key),
  plus (b) per-endpoint *launch wrappers* in `~/.local/bin` (`aider-hf`, `aider-ollama`, ...) that
  export `OPENAI_API_BASE`/`OPENAI_API_KEY` from `local.json` for that one process - the exact
  pattern the estate already uses for `fabric-cursor` / `claude-cursor` / `codex-cursor` (dedup
  item 3). No new gateway.
- **Lock-L2 reading [INFER]:** Aider *embeds* the `litellm` Python library as its model router.
  L2 ("no LiteLLM") is read here as "no LiteLLM proxy/gateway as an estate service"; the library
  inside an already-installed runtime is that runtime's internals, not a second orchestration
  runtime. Flagged so the owner can overrule.

### 2.7 Gemini CLI, Agy (Antigravity CLI)
_(pending - next checkpoint)_

### 2.8 Runtimes that cannot take a provider at all: Claude Code, Cursor
_(pending - next checkpoint)_

### 2.9 Endpoint-side wire facts (which endpoints speak `/v1/responses`)
_(pending - next checkpoint)_

## 3. Proposed `.agents/models.json` schema

_(pending)_

## 4. Materializers (per runtime) and idempotent merge semantics

_(pending)_

## 5. Fallback for runtimes that cannot take a provider: generic inference MCP

_(pending)_

## 6. Migration plan: deprecate glm53-space and qwen-space with redirect tombstones

_(pending)_

## 7. Test plan

_(pending)_

## 8. Per-find rubric table

_(pending)_

## 9. Summary (10 lines)

_(pending)_
