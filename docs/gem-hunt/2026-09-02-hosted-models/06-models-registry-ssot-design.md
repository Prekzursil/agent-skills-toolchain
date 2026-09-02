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
- **[FACT] Gemini CLI** can override its *Gemini-protocol* base URL only: env `GOOGLE_GEMINI_BASE_URL`
  (non-Vertex) / `GOOGLE_VERTEX_BASE_URL`, or `config.baseUrl`; `validateBaseUrl` requires `https:`
  except for `localhost`, `127.0.0.1`, `[::1]`; wired via `@google/genai` `httpOptions.baseUrl`.
  An earlier `GEMINI_API_BASE_URL` PR was flagged for SSRF because it validated nothing.
  ([google-gemini/gemini-cli PR #21561](https://github.com/google-gemini/gemini-cli/pull/21561),
  [PR #16010](https://github.com/google-gemini/gemini-cli/pull/16010), [PR #5346](https://github.com/google-gemini/gemini-cli/pull/5346); Tier A PR text, 2026-09-02.)
- **[INFER]** Gemini CLI therefore **cannot** take an OpenAI-compatible endpoint natively; the
  only way is a Gemini-protocol translating proxy (LiteLLM-class), which lock L2 forbids. Gemini
  CLI is classed with Claude/Cursor as a *fallback-only* runtime: it reaches registry models
  through the generic inference MCP (section 5) mounted in `~/.gemini/settings.json` `mcpServers`.
- **[FACT] Port hazard:** the popular `gemini-cli-mcp-openai-bridge` defaults to `127.0.0.1:8765`
  ([Intelligent-Internet/gemini-cli-mcp-openai-bridge README](https://github.com/Intelligent-Internet/gemini-cli-mcp-openai-bridge)),
  which is `basic-memory`'s owned port (L4). Do not adopt it; if anyone ever does, it must be re-ported.
- **[FACT] Agy (Antigravity CLI, Go binary, released 2026-05-19)** has two HTTP clients: an admin
  CloudCode client that honours `CLOUD_CODE_URL`, and an **inference client hard-wired to a GCP
  backend** that ignores env/proxy config; auth is keyring + Google sign-in. An open feature
  request asks for base-URL + header override and notes that the Gemini CLI it replaces *did*
  support `GOOGLE_GEMINI_BASE_URL`. ([google-antigravity/antigravity-cli#514](https://github.com/google-antigravity/antigravity-cli/issues/514),
  [decolua/9router#1358](https://github.com/decolua/9router/issues/1358); Tier B issue text, 2026.)
- **[FACT]** Since agy 1.1.13 (2026-08-14) a keyless CI path exists: `settings.json`
  `modelProvider: "gemini"` + `GEMINI_API_KEY`, with a `GOOGLE_GEMINI_BASE_URL` override - still
  Gemini protocol only. (Tier C, [aibuilderclub agy guide](https://www.aibuilderclub.com/blog/antigravity-cli-guide), UNVERIFIED against release notes.)
- **[FACT]** BYOK for agy exists only as third-party local translating proxies (`agy-byok`
  default `127.0.0.1:12345`; `free-antigravity-cli` with `~/.free-antigravity/models.json` holding
  literal `apiKey` values). ([webbrain-one/agy-byok](https://github.com/webbrain-one/agy-byok),
  [vahapogut/free-antigravity-cli](https://github.com/vahapogut/free-antigravity-cli); Tier C.)
- **[INFER]** Agy is fallback-only (section 5). The proxies are a second gateway holding plaintext
  keys - a tradeoff, listed not adopted (L2, L6 spirit). Whether agy mounts MCP servers from
  `settings.json` like Gemini CLI is UNVERIFIED today; if not, agy simply has no path to
  registry models and the registry should record `targets.agy = "unsupported"` honestly.

### 2.8 Runtimes that cannot take a provider at all: Claude Code, Cursor (+ Gemini CLI, Agy)
- **[FACT]** Claude Code's only third-party model path is `ANTHROPIC_BASE_URL` (Anthropic Messages
  wire), which lock L1 forbids for OpenRouter and the estate keeps on native Max
  (`openrouter-routing/SKILL.md` line 62: "Leave Claude on native Max"). Cursor's only path is
  BYOK "Override OpenAI Base URL", which L1 forbids for OpenRouter and which "can break native Max
  models; Auto / Composer may ignore BYOK" (same skill, line 23). (Tier A repo doctrine.)
- **[INFER]** For Claude, Cursor, Gemini CLI and Agy the registry is reached **only** through the
  single generic inference MCP tool (section 5), mounted via the existing `agents.json`
  materializers (Claude/Codex/Cursor merges already exist; Gemini `settings.json` `mcpServers`
  would be a new small merge in the same family). That keeps hard rule 2 of
  `hosted-model-agents` intact: one MCP, not one per endpoint.

### 2.9 Endpoint-side wire facts (who speaks `/v1/responses`; gates the Codex + Fabric materializers)
| Endpoint | chat_completions | responses | Notes | Source |
|---|---|---|---|---|
| Ollama >= 0.13.3 | native | native, **non-stateful** (no `previous_response_id`/`conversation`), streaming + tools + reasoning summaries | < 0.13.3 returns 404 | Tier A [docs.ollama.com/api/openai-compatibility](https://docs.ollama.com/api/openai-compatibility), [ollama#13595](https://github.com/ollama/ollama/issues/13595) |
| LM Studio >= 0.3.29 | native | native, **stateful** (`previous_response_id`), custom tools, remote-MCP opt-in, `reasoning.effort` | port 1234 | Tier A [lmstudio.ai/blog/lmstudio-v0.3.29](https://lmstudio.ai/blog/lmstudio-v0.3.29) |
| llama.cpp `llama-server` | native | **absent / in progress** (404 observed against Fabric) | needs Fabric `disableResponsesAPI` | Tier A [Fabric#1625](https://github.com/danielmiessler/Fabric/issues/1625); current upstream state UNVERIFIED today |
| OpenRouter | native | native (`/api/v1/responses`) | Codex wire OK; sidecar only (L1) | Tier A `openrouter-routing/SKILL.md` |
| HF router `router.huggingface.co/v1` | native (glm53-space uses it) | UNVERIFIED today | must be **probed**, not declared | Tier A `agents.json` description; responses support unchecked |
| HF Space `/v1` (Gradio-mounted FastAPI) | native if the Space author mounted it | absent unless the author added it | recipe `hf-space-openai.md` | Tier A live-capture branch |
| HF Inference Endpoint / TGI / vLLM | native | vLLM has a `/v1/responses` server; TGI UNVERIFIED | per-deploy probe | Tier C (memory), UNVERIFIED today |
| auth2api `127.0.0.1:8317` | native (36 `cursor-*` ids) | UNVERIFIED | the only Cursor bridge (L3); Codex wrapper `codex-cursor` already exists, implying responses works or a shim exists - probe | Tier A task brief |
| Azure AI Foundry (OpenAI models) | native | native | `api-version` query param needed (Codex `query_params`) | Tier B alexdunlop write-up citing `config-advanced` |
| Modal / RunPod / Lightning | whatever the deployed server speaks (usually vLLM/TGI) | per-deploy | GPU rental, not a wire | Tier A `environments.md` |

**[INFER] Design consequence:** `wire` is a *per-endpoint capability with a probe*, never a global
assumption. Codex and Fabric materializers emit only endpoints whose `wire.responses` is
`native` or `probed=ok`; everything else reaches those runtimes through Grok/Goose/OpenCode/Aider
(chat-capable) or the inference MCP (section 5). Present this as a routing table, not as "drop
the endpoint" (L7).

## 3. Proposed `.agents/models.json` schema

### 3.1 Placement decision: separate file, not a block in `agents.json`  **[REC]**
- `agents.json` is validated by `mcp_control_plane.validate_registry`, which fails closed on
  shape it does not recognise, and is consumed by three merge scripts plus `sync_shared_state.ps1`
  (`lastSync`, `lastSyncSourceHash` at top level). Adding a `models` block would (a) widen the
  blast radius of every models edit to the MCP fleet, (b) force the MCP validator to learn a
  second domain, and (c) change `lastSyncSourceHash` on every model tweak. **[INFER]**
- **[REC]** New sibling file `.agents/models.json` with its own `schemaVersion: 1`, its own
  validator module `.agents/scripts/models_control_plane.py` (mirrors `mcp_control_plane.py`),
  and *one* cross-reference: the inference MCP server entry in `agents.json` (section 5) declares
  `"x_models": {"registry": ".agents/models.json"}` so `sync_shared_state.ps1` can hash both.
- Provenance (why an endpoint exists, who asked) goes to `.provenance/.agents/models.json.md`
  per the AGENTS.md rule "never add a manifest key merely to carry provenance". Tier A.

### 3.2 Top-level shape (JSON Schema 2020-12, abridged; full draft in 3.4)
```jsonc
{
  "schemaVersion": 1,
  "policy": {                       // defaults every endpoint inherits (same idiom as mcp.policy)
    "healthProbe": {"kind": "models-list", "timeoutMs": 8000, "intervalSec": 900},
    "capabilityProbe": {"enabled": true, "ttlHours": 168},
    "budget": {"currency": "USD", "monthlyCapUsd": 0, "onExceeded": "disable"},
    "allowLocalhostHttp": true,     // http:// only for 127.0.0.1/localhost/[::1] (mirrors gemini-cli validateBaseUrl)
    "targets": ["codex","grok","goose","fabric","opencode","aider","inference-mcp"]
  },
  "endpoints":  { "<endpoint-id>": Endpoint },    // where tokens come from
  "models":     { "<model-id>":    Model    },    // what runs there
  "aliases":    { "<alias>": "<model-id>" },      // estate-wide names: "fast", "cheap-extract", "cursor-default"
  "locks":      [ Lock ]                          // machine-readable copies of L1-L7 the validator enforces
}
```

### 3.3 `Endpoint` object
| Field | Type | Rule / rationale |
|---|---|---|
| `kind` | enum `hf-router \| hf-endpoint \| hf-space \| openrouter \| ollama \| lmstudio \| llamacpp \| modal \| runpod \| lightning \| azure-foundry \| cursor-auth2api \| generic-openai` | drives probe strategy + materializer eligibility |
| `baseUrl` | string (uri) | MUST end in `/v1` for OpenAI-compatible kinds (Fabric/Aider/Goose sharp edges, section 2); `https://` required unless host is loopback (`policy.allowLocalhostHttp`) |
| `auth` | object `{ "scheme": "bearer\|header\|none", "env": "NAME", "headerName"?: "x-api-key", "localJsonPath"?: "/hf/token", "altEnv"?: ["HF_TOKEN"] }` | `env` MUST match `^[A-Z][A-Z0-9_]*$`; the value NEVER appears (reuse `LITERAL_SECRET_RE` + `is_credential_name`); `localJsonPath` is a JSON Pointer into `~/.agents/local.json` for the launch-time resolver; `altEnv` feeds Grok's `env_key` array |
| `wire` | object `{ "chat_completions": Cap, "responses": Cap, "messages": Cap, "gradio": Cap }` | `Cap` = section 3.5 lattice value |
| `features` | object `{ "tools": Cap, "json_schema": Cap, "json_object": Cap, "vision": Cap, "streaming": Cap, "reasoning": Cap, "stateful": Cap }` | per-endpoint; a `Model` may override downward only (a model cannot claim more than its endpoint) |
| `cost` | object `{ "mode": "per-token\|subscription\|free\|gpu-hour", "inputUsdPerM"?: n, "outputUsdPerM"?: n, "gpuUsdPerHour"?: n, "quota"?: {"unit": "requests\|tokens\|credits", "readEndpoint"?: "GET /v1/key"} }` | OpenRouter exposes `GET /api/v1/key` limits (Tier A repo skill); auth2api is `subscription` (Cursor quota); local is `free` (RAM is the real cost - see `resource`) |
| `resource` | object `{ "ramBytes"?: n, "vramBytes"?: n, "exception"?: "text>=20 chars" }` | local endpoints only; mirrors `maxPrivateBytes`+`resourceException` idiom; box has 31.6 GB and is memory-starved (task brief) - the validator sums `ramBytes` of `enabled` local endpoints and warns above a `policy.localRamBudgetBytes` |
| `health` | object `{ "kind": "models-list\|chat-ping\|http-head\|none", "path"?: "/models", "expectStatus"?: 200, "timeoutMs"?: n }` | `models-list` = `GET {baseUrl}/models` (Fabric, Grok and Goose all rely on it) |
| `targets` | object `{ "<runtime>": "native\|fallback\|unsupported\|excluded" }` | explicit per runtime; validator fills `excluded` + reason when a lock or a wire gap forbids (e.g. Codex for a chat-only endpoint) |
| `tags` | string[] nonempty | reuse the estate vocabulary: `approved`, `owner-requested`, `hosted-inference`, `local`, `sidecar`, `default-off` |
| `enabled` | bool (default true) | |
| `singletonKey` | string | e.g. all Cursor-bridge endpoints share `cursor-bridge` so at most one is materialized (L3 + G-36) |
| `retiresWhen` | string | free text tied to a lock, e.g. `"official Cursor /v1 GA + 7 days"` for `cursor-auth2api` (L3) |
| `x_codex`, `x_grok`, `x_goose`, `x_fabric`, `x_opencode`, `x_aider` | closed objects | runtime-specific knobs that have no estate meaning (`request_max_retries`, `api_backend`, `timeout_seconds`, `edit_format`...). Closed schema each, as `x_codex`/`x_cursor` are today |

### 3.4 `Model` object
```jsonc
"models": {
  "glm-5.3@hf-router": {
    "endpoint": "hf-router",
    "remoteId": "zai-org/GLM-5.3",          // exact id sent on the wire
    "displayName": "GLM 5.3 (HF router)",
    "contextWindow": 131072, "maxOutput": 8192,
    "features": {"tools": "probed", "json_schema": "declared", "vision": "absent"},   // downward overrides only
    "cost": {"inputUsdPerM": 0.0, "outputUsdPerM": 0.0},                               // per-model price if the endpoint bills per model
    "roles": ["cheap-extract","learner"],    // maps to hosted-model-agents profiles.md packs, by name only
    "tags": ["approved","owner-requested"]
  }
}
```
- `model-id` convention `<slug>@<endpoint-id>` keeps the same checkpoint on two endpoints distinct
  (`qwen3-8b@ollama` vs `qwen3-8b@lmstudio`), which the RAM budget and the eval harness (lens 08)
  both need. Materializers slugify `@` to `-` for runtimes that dislike it (OpenCode: no dots;
  Grok: quoted keys fine; Codex: provider id only, model id separate).
- `aliases` are the only names skills/prompts may reference (L5: prompts live in `.agents/skills`
  and must not hardcode a checkpoint - that was the qwen-space mistake).

### 3.5 The capability lattice (the part the glm53-space adapter lacked)
```
                 native
                /      \
           probed      declared
                \      /
                emulated
                   |
                 absent
```
| Value | Meaning | Who may set it |
|---|---|---|
| `native` | vendor documents it AND the estate has exercised it | validator upgrades `probed`->`native` after N=3 successful probes over 7 days |
| `probed` | the estate's probe (section 7) succeeded at least once; carries `{at, version}` | probe job only |
| `declared` | vendor docs say yes; never exercised here | human, with a URL in `.provenance` |
| `emulated` | the inference MCP (section 5) can fake it (e.g. `json_schema` via post-validation + retry; `tools` via prompt-format ReAct) | inference MCP capability table only |
| `absent` | known not to work, or wire returned 404/400 | probe job or human |
- Materializers consult the lattice with a **floor**: Codex requires `wire.responses >= probed`;
  Fabric requires `wire.responses >= probed` OR sets `disableResponsesAPI` (global tradeoff,
  surfaced in the dry-run report); Goose/Grok/OpenCode/Aider require `wire.chat_completions >=
  declared`; the inference MCP accepts anything `>= emulated` and reports the level in its
  tool result so the calling agent knows what it got.
- Storing `probed` with a timestamp (not a boolean) is what lets `evals.md` in
  `hosted-model-agents` and lens 08's harness read the same file instead of a second ledger.

### 3.6 `Lock` object - the estate locks as data the validator enforces
```jsonc
"locks": [
  {"id":"L1","rule":"openrouter-sidecar-only","assert":"endpoints[kind=openrouter].targets.cursor == 'excluded' && targets.claude == 'excluded' && no endpoint kind=openrouter has x_mcp"},
  {"id":"L2","rule":"no-gateway-runtime","assert":"no endpoint.baseUrl host matches /litellm|langgraph/ and no endpoint.kind == 'gateway'"},
  {"id":"L3","rule":"single-cursor-bridge","assert":"count(endpoints[kind=cursor-auth2api && enabled]) <= 1 && baseUrl == 'http://127.0.0.1:8317/v1' && retiresWhen present"},
  {"id":"L4","rule":"owned-ports","assert":"no new endpoint.baseUrl port in {8765,8812,8317} unless kind == cursor-auth2api"},
  {"id":"L6","rule":"never-rotate","assert":"materializers never write a credential value; resolver is read-only on local.json"}
]
```
L5 and L7 are process locks, not data; they are enforced by the test plan (section 7) and the
dry-run report format (every exclusion carries a reason and the alternative route).

### 3.7 Seed content (what the file holds on day one) **[REC]**
| endpoint-id | kind | baseUrl | auth.env | wire.responses | first targets |
|---|---|---|---|---|---|
| `hf-router` | hf-router | `https://router.huggingface.co/v1` | `HUGGINGFACE_TOKEN` (alt `HF_TOKEN`) | `declared`-> probe | grok, goose, opencode, aider, inference-mcp; codex after probe |
| `openrouter` | openrouter | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | `native` | codex (non-default profile), grok, goose, aider; **cursor/claude excluded (L1)** |
| `cursor-auth2api` | cursor-auth2api | `http://127.0.0.1:8317/v1` | `AUTH2API_TOKEN` or `none` (UNVERIFIED which) | probe | goose (`goose-cursor-proxy` exists), grok (`cursor-grok-4.6` exists), fabric/claude/codex wrappers exist; `retiresWhen: "Cursor /v1 GA + 7d"` |
| `ollama` | ollama | `http://127.0.0.1:11434/v1` | none | `native` (>=0.13.3, non-stateful) | all; `resource.ramBytes` per model |
| `lmstudio` | lmstudio | `http://127.0.0.1:1234/v1` | none | `native` (>=0.3.29, stateful) | all |
| `llamacpp` | llamacpp | `http://127.0.0.1:<port>/v1` | none | `absent` -> Fabric needs `disableResponsesAPI`; Codex excluded with reason | grok, goose, opencode, aider, inference-mcp |
| `azure-foundry-*` | azure-foundry | per deployment | `AZURE_OPENAI_API_KEY` | `native` (+`api-version`) | codex (`query_params`), grok, goose |
| `hf-space-*`, `modal-*`, `runpod-*`, `lightning-*` | per deploy | per deploy | per deploy | probe | added by the deploy recipe, default `enabled: false` until probed |
The `hf-router` + model `glm-5.3@hf-router` row is the literal replacement for glm53-space's
hardcoded pair (section 6).

## 4. Materializers (per runtime) and idempotent merge semantics

### 4.1 Shared contract (mirrors `merge_generated_*_mcp.py`) **[REC]**
One module `.agents/scripts/models_control_plane.py` + one script per runtime
`merge_generated_<runtime>_models.py`. Every script:
1. `validate_registry(models_json)` first; any `RegistryError` -> exit 1, nothing written.
2. Loads the **live** config, never a template; computes `generated` from
   `select_target_endpoints(registry, runtime)` (enabled, `targets.<runtime> == native`,
   singletonKey-deduped, sorted for determinism).
3. **Ownership rule:** only blocks/keys/files the registry *names* are touched. Codex precedent:
   remove a live block only if its name is in `registry_names | RETIRED_NAMES` and its suffix is
   replaceable; everything else is preserved byte-for-byte. Retired names (`glm53-space`,
   `qwen-space`) live in a `RETIRED_MODEL_ENTRIES` frozenset so stale blocks are purged exactly
   the way `RETIRED_MCP_SERVERS` purges `memory` / `codex_consult` today.
4. `assert_exact_target_parity(...)` before write - the rendered set must equal the selected set.
5. Writes only with `--write`, via `control.atomic_write_text` (tmp + fsync + `os.replace`);
   default is a **dry-run diff** plus a **routing report**: for every (endpoint, runtime) pair
   that was *not* materialized, the reason (`lock:L1`, `wire:responses=absent`, `targets:excluded`)
   and the alternative route (`inference-mcp`, or another runtime). That is how L7 is honoured.
6. Prints one machine line `SUCCESS:models-<runtime>-merge managed=N removed=N write=bool` so
   `sync_shared_state.ps1` can gate on it like it gates the MCP merges.
7. **Post-write smoke** (new vs the MCP scripts, forced by Codex #41816): run the runtime's
   cheapest config-load command (`codex --version`/`codex login status`, `grok inspect`,
   `goose info`, `fabric -L`, `opencode models`, `aider --list-models openai/`) and roll back via
   the pre-write copy if it exits non-zero. Rollback is the one place a backup is mandatory.

### 4.2 Per-runtime rendering
| Runtime | Live file | Unit generated per endpoint | Merge strategy | Floor | Sharp edges honoured |
|---|---|---|---|---|---|
| **Codex** | `~/.codex/config.toml` | `[model_providers.<id>]` with `name, base_url, env_key, wire_api="responses", http_headers?, env_http_headers?, query_params?` + optional `[profiles.<id>]` (`model_provider`, `model`) - **never** touches top-level `model`/`model_provider` (OpenRouter stays non-default, L1) | block split/replace exactly as `merge_generated_codex_mcp.py`; header regex `^model_providers\.("[^"]+"\|[^.]+)(\..+)?$` and `^profiles\.<managed-id>$` | `wire.responses >= probed` | never emit `wire_api="chat"`; never shadow built-in ids `openai/ollama/lmstudio`; smoke after write |
| **Grok** | `~/.grok/config.toml` | one `[model."<model-id>"]` per *model* (not endpoint): `model=remoteId, base_url, name, description, env_key=[auth.env, ...altEnv], api_backend` (from best available wire: `responses` > `chat_completions`), `context_window, max_completion_tokens`; `[models] default` untouched unless `aliases.grok-default` exists | same block splitter (`^model\."..."$`); `[models]`/`[endpoints]` preserved | `chat_completions >= declared` | never `api_key=`; never `extra_headers` containing a credential-named key; `cursor-grok-4.6` (dedup) is imported as a live-only block if not registry-named |
| **Goose** | `%APPDATA%\Block\goose\config\custom_providers\<id>.json` | one file per endpoint: `name=id, engine="openai", display_name, description="managed-by:.agents/models.json", api_key_env, base_url, base_path="v1/chat/completions", models[{name, context_limit, input/output_token_cost}], supports_streaming, requires_auth, timeout_seconds (x_goose)` | **file-set** merge: write files we own (marker in `description`), delete owned files no longer generated, never touch unmarked files (`goose-cursor-proxy.json` stays if unmarked) | `chat_completions >= declared` | `requires_auth=false` when `auth.scheme=none`; skip + report endpoints whose headers would need a literal secret |
| **Fabric** | `~/.config/fabric/.env` (+ `config.yaml`) | key/value lines inside a `# >>> models.json managed >>>` / `# <<< ... <<<` fence: `LM_STUDIO_API_URL`, `OLLAMA_API_URL`, and for the *one* selected generic endpoint `OPENAI_API_BASE_URL` (+`OPENAI_API_KEY=${...}` **reference only** - Fabric reads the process env, so the wrapper exports it) | fenced-region replace (the exact marker idiom the Codex script *strips* as legacy `promptbridge-codex managed` - here it is the live mechanism, since `.env` has no sections); outside the fence untouched | `chat_completions >= declared`; if `responses < probed` emit `disableResponsesAPI: true` into `config.yaml` **and** print the global-tradeoff warning | Fabric has ONE generic OpenAI base: the materializer picks `aliases.fabric-default`; other endpoints become `fabric-<id>` wrappers (see 4.3) |
| **OpenCode** | `~/.config/opencode/opencode.json` | `provider.<id>` with `npm:"@ai-sdk/openai-compatible", name, options:{baseURL, apiKey:"{env:NAME}"}, models:{<slug>:{name, limit:{context,output}}}` | JSON key merge: replace `provider.<id>` for managed ids, delete managed ids no longer generated, preserve every other key (`$schema`, `model`, `mcp`, unmanaged providers) | `chat_completions >= declared` | dot-free ids; `{env:}` only; never `{file:}` (would name a plaintext file, L6 spirit) |
| **Aider** | `~/.aider.model.metadata.json`, `~/.aider.model.settings.yml`, `~/.aider.conf.yml` `alias:` | metadata entry `openai/<remoteId>` = `{max_input_tokens, max_output_tokens, input_cost_per_token, output_cost_per_token, litellm_provider:"openai"}`; settings entry `{name:"openai/<remoteId>", edit_format: x_aider.edit_format \| "diff", use_repo_map: true}`; alias `"<alias>:openai/<remoteId>"` | JSON key merge / YAML list merge by `name` / alias list merge by prefix; a `# managed` comment on YAML entries | `chat_completions >= declared` | one base per process -> pairs with 4.3 wrappers; validate `litellm_provider == "openai"` prefix rule (#2928 lesson) |
| **Gemini CLI, Agy, Claude, Cursor** | n/a | **no provider block** - they receive the inference MCP via the *existing* `agents.json` merges (+ a new `merge_generated_gemini_mcp.py` for `~/.gemini/settings.json` `mcpServers`, same family) | - | - | Codex #41816-style bricking cannot happen because nothing is written to their model config |

### 4.3 Launch wrappers are part of the materializer (not an afterthought)
- **[FACT]** The estate already materializes *processes*, not just files: `fabric-cursor`,
  `claude-cursor`, `codex-cursor`, `ai-mode`, `grok-mode` in `~/.local/bin` export a base URL/key
  for one process against auth2api (dedup item 3; G-32 "process-local, no persistent global env").
- **[REC]** `merge_generated_wrappers_models.py` renders `~/.local/bin/<runtime>-<endpoint-id>`
  (`.ps1` + `.cmd` shim on Windows) that: reads `auth.env`'s value from `local.json` via
  `auth.localJsonPath` (read-only, never printed), exports it under `auth.env` (and Aider/Fabric's
  `OPENAI_API_BASE(_URL)`), then `exec`s the runtime. Ownership by a header comment
  `# managed-by: .agents/models.json <hash>`; unmarked wrappers untouched. This is the only
  materializer that *needs* the resolver, and it is why `local.json` can stay nested (1.4).
- Runtime-side keys never land in any config file; only NAMES do (L6, and the
  `_validate_reference_map` rule from the MCP plane applied verbatim).

### 4.4 Ordering + orchestration
`sync_shared_state.ps1` gains one step after the three MCP merges:
`models validate -> models probe --stale-only -> merge codex|grok|goose|fabric|opencode|aider|wrappers (each dry-run, then --write) -> smoke each`.
No daemon, no gateway, no new port (L2, L4). Total new code: one control-plane module, seven
small merge scripts sharing the Codex/Claude patterns, one probe script.

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
