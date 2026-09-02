# Gem-hunt 2026-09-02 / hosted models / lens 01 - native-capability audit

**Lens id:** `01-native-capability-audit`
**Mode:** discovery, ENABLE-not-BUILD. No code changed. One file, committed after each section.
**Question:** for every runtime installed on the Windows 11 box, what does it *natively* offer
for pointing at a custom model provider (OpenAI-compatible base URL, Anthropic-compatible
endpoint, per-model config blocks, provider registries such as models.dev, MCP sampling), and
which of those doors can consume a Hugging Face router / Space / Inference Endpoint or a local
Ollama / LM Studio server with **zero code**? Where a door is bolted shut by an estate lock, say
so, so the integration layer that replaces `tools/mcp/glm53-space` knows where an MCP tool is the
only remaining entrance.

## 0. Grading key, dedup-set and estate locks (read first)

**Confidence grades.** Every sourced claim carries `[A|B|C, corroborated|UNVERIFIED, YYYY-MM]`.
A = official docs or the vendor's own repo/reference page; B = vendor blog, release notes, or a
high-signal third party (models.dev, a maintainer's issue reply); C = community post, forum, or
inference from code. `corroborated` = two independent sources agree; `UNVERIFIED` = one source
only or I could not open the page in this run. The date is the month the source was fetched or
last known updated. Sentences are tagged **[fact]**, **[inference]** or **[recommendation]**.

**Dedup-set (exists, not re-proposed):** (1) skill `.agents/skills/hosted-model-agents` on
`live-capture/2026-09-02` (HF Hub MCP + Spaces + Endpoints, Modal/RunPod/Lightning, Azure
Foundry, llama.cpp, Cursor Max via auth2api); (2) `tools/mcp/glm53-space` on `main`, hardcoded to
`router.huggingface.co/v1` + `zai-org/GLM-5.3`, being DEPRECATED for a general integration layer;
(3) auth2api on `127.0.0.1:8317`, the ONLY Cursor-quota OpenAI-compatible bridge (36 `cursor-*`
model ids), consumed by goose (`GOOSE_PROVIDER goose-cursor-proxy`), grok `config.toml`
`[model."cursor-grok-4.6"]`, and the `fabric-cursor` / `claude-cursor` / `codex-cursor` wrappers
in `~/.local/bin`; (4) registry `.agents/agents.json` (`mcp.servers`, 42 servers) + secrets by
name only in `.agents/local.json`; (5) installed runtimes: claude (Claude Code), codex,
cursor-agent, grok + agent.exe, goose 1.47, fabric 1.4.470, agy, gemini CLI, opencode, aider
0.86, ollama, lms (LM Studio), ralph (cargo), basic-memory :8765, agent-mail :8812,
browser-bridge hub :8770; wrappers ai-mode, grok-mode, qwen-space (deprecated pointer),
claude-swap.

**Estate locks (hard constraints, cited as such below, never proposed against):**

| Lock | Consequence for this lens |
|---|---|
| OpenRouter = spend-capped CLI/Codex sidecar only; never a Cursor BYOK key, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP | Any "route Claude Code through OpenRouter" or "put OpenRouter into Cursor Models settings" finding is marked **LOCKED**, not recommended. |
| No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory | Findings that require a proxy such as LiteLLM to translate protocols are marked **LOCKED**; only the vendor-native door or an MCP tool inside the existing registry qualifies. |
| auth2api `:8317` stays the only Cursor bridge; retires within 7 days of an official Cursor `/v1` GA | I do not propose a second Cursor bridge. I record what an official Cursor `/v1` would replace. |
| Ports 8765 / 8812 / 8317 owned | No new listener may claim them; Ollama (11434) and LM Studio (1234) defaults do not collide. |
| `.agents/skills` is the ONE prompt SSOT (Fabric / Goose consume it) | Provider config lives in each runtime's own file; prompts do not move. |
| Never rotate credentials; never remove a feature to buy reliability | Tradeoffs are presented, nothing is retired in this lens. |

## 1. Method

1. For each runtime, open the current official configuration reference (or the repo README /
   `config` docs where no separate site exists) and record: the config file path, the exact keys
   for (a) OpenAI-compatible base URL + API-key env, (b) Anthropic-compatible endpoint,
   (c) per-model blocks, (d) provider registry (models.dev or similar), (e) MCP sampling
   (server-initiated `sampling/createMessage`), and (f) whether a HF router / Space / Endpoint or
   a local Ollama / LM Studio server can be consumed with zero code.
2. Cross-check against a second source where one exists (release notes, models.dev, the HF
   router docs) and grade.
3. Overlay the estate locks and mark each cell ENABLE / LOCKED / IMPOSSIBLE / MCP-ONLY.
4. Produce the runtime x mechanism matrix and the per-find rubric table.

Sections 2-15 are one runtime each, in the dedup-set order. Section 16 is the matrix, 17 the
Hugging Face and local-server consumption view, 18 the rubric, 19 the summary.

## 2. Claude Code (`claude`)

- **[fact]** Provider override is environment-driven and Anthropic-Messages-only. `ANTHROPIC_BASE_URL`
  points the client at any host that speaks the Messages API; the credential goes in
  `ANTHROPIC_AUTH_TOKEN` (sent as `Authorization: Bearer`) or `ANTHROPIC_API_KEY` (sent as
  `x-api-key`), or is fetched by an `apiKeyHelper` command. Model names are overridden with
  `ANTHROPIC_MODEL` and the `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL` family. All of these may
  live in the `env` block of `~/.claude/settings.json` (or a project / managed settings file).
  [A, corroborated, 2026-09] https://code.claude.com/docs/en/llm-gateway-connect ,
  https://code.claude.com/docs/en/llm-gateway-rollout , https://code.claude.com/docs/en/settings
- **[fact]** First-party cloud routes are switched with `CLAUDE_CODE_USE_BEDROCK=1`,
  `CLAUDE_CODE_USE_VERTEX=1`, `CLAUDE_CODE_USE_FOUNDRY=1` plus `ANTHROPIC_BEDROCK_BASE_URL` /
  `ANTHROPIC_VERTEX_BASE_URL` / `ANTHROPIC_FOUNDRY_BASE_URL` (or `ANTHROPIC_FOUNDRY_RESOURCE`) and
  the `CLAUDE_CODE_SKIP_*_AUTH` flags. Foundry has no wizard; env vars are the only path.
  [A, corroborated, 2026-09] https://code.claude.com/docs/en/microsoft-foundry
- **[fact]** Per-model config keys in settings: `model`, `fallbackModel`, `modelOverrides`,
  `availableModels` (allowlist); `--model` beats `ANTHROPIC_MODEL` beats the file.
  [A, UNVERIFIED single source, 2026-09] https://code.claude.com/docs/en/settings
- **[fact]** While a gateway credential is active the claude.ai subscription is *not* used and
  traffic is billed to whoever owns the forwarded credential. Setting only `ANTHROPIC_BASE_URL`
  without a credential keeps the subscription login active. [A, 2026-09]
  https://code.claude.com/docs/en/llm-gateway
- **[fact]** There is no OpenAI-compatible mode. A C-tier blog claims Claude Code reads
  `OPENAI_BASE_URL` for OpenAI-model ids; I found no official page for it. [C, UNVERIFIED, 2026-09]
  https://therouter.ai/blog/cursor-custom-api-endpoint-llm-router-guide/
- **[fact]** Zero-code local targets exist because two local servers now speak Messages natively:
  Ollama >= 0.14.0 (`ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_BASE_URL=http://localhost:11434
  claude --model qwen3-coder`, or `ollama launch claude [--config]` which writes it for you)
  [A, corroborated, 2026-09] https://ollama.com/blog/claude ,
  https://github.com/ollama/ollama/blob/main/docs/api/anthropic-compatibility.mdx ; and LM Studio
  >= 0.4.1 (`lms server start --port 1234`, `ANTHROPIC_BASE_URL=http://localhost:1234
  ANTHROPIC_AUTH_TOKEN=lmstudio`, optional `CLAUDE_CODE_ATTRIBUTION_HEADER=0`)
  [A, corroborated, 2026-09] https://lmstudio.ai/docs/integrations/claude-code ,
  https://lmstudio.ai/docs/developer/anthropic-compat
- **[fact]** The Hugging Face router exposes OpenAI chat-completions and Responses, not
  `/v1/messages`, so Claude Code cannot consume it without a protocol translator (see s.15).
  [B, absence claim, 2026-09]
- **[fact]** MCP sampling: not supported (client matrix shows Sampling = no; Roots yes).
  [B, corroborated, 2026-09] https://github.com/apify/mcp-client-capabilities/ ,
  https://modelcontextprotocol.info/docs/clients/
- **ESTATE:** the brief marks the Claude base-URL override as **LOCKED** (the only sanctioned use
  is the existing `claude-cursor` wrapper toward auth2api :8317, and OpenRouter is forbidden as
  `ANTHROPIC_BASE_URL`). **[inference]** Therefore HF / Ollama / LM Studio reach Claude Code only
  through an MCP tool registered in `.agents/agents.json`. **[recommendation]** Record the
  Ollama/LM Studio Messages path as a *documented, dormant* option so the tradeoff (subscription
  off, local model on) is visible when the owner revisits the lock.

## 3. Codex CLI (`codex`)

- **[fact]** Config is `~/.codex/config.toml` (user level; `model_provider` / `model_providers`
  in a project-local `.codex/config.toml` are ignored). A custom provider is a
  `[model_providers.<id>]` table with `name`, `base_url`, `env_key` (must name an env var; no
  literal keys), `env_key_instructions`, `wire_api`, `http_headers`, `env_http_headers`,
  `query_params`, `request_max_retries`, `stream_max_retries`, `stream_idle_timeout_ms`; selected
  by top-level `model_provider = "<id>"` + `model = "..."` or inside `[profiles.<name>]`.
  The ids `openai`, `ollama`, `lmstudio` are reserved and force built-in behaviour (localhost,
  fixed protocol), so a remote Ollama must use a different id or `CODEX_OSS_BASE_URL`.
  [B, corroborated by 3 sources + maintainer issue reply, 2026-09]
  https://codex.danielvaughan.com/2026/04/23/codex-cli-custom-model-providers-configuration-guide/ ,
  https://www.devshorts.in/p/how-to-run-custom-models-in-codex ,
  https://github.com/openai/codex/issues/8240 . The official reference
  https://developers.openai.com/codex/config-reference timed out twice in this run
  [A, UNVERIFIED in-run, 2026-09]; the repo `docs/config.md` now only redirects there
  https://raw.githubusercontent.com/openai/codex/main/docs/config.md [A, 2026-09].
- **[fact]** `wire_api = "chat"` was removed in Feb 2026; the only value is `"responses"`, so every
  target must implement `/v1/responses`. [B, corroborated, 2026-09]
  https://www.alexdunlop.com/writing/codex-cli-config-toml , https://docs.greenpt.ai/coding/codex-cli
- **[fact]** Targets that speak Responses today: Ollama (`/v1/responses` since 0.13.3; `ollama
  launch codex` writes the profile) [C, 2026-09]
  https://www.ssdnodes.com/learn/use-ollama-with-your-coding-agent ; the HF router
  (`https://router.huggingface.co/v1/responses`, beta, "all chat-completion models should be
  compatible") [A, 2026-09] https://huggingface.co/docs/inference-providers/main/en/guides/responses-api ;
  LM Studio (has an official Codex integration page) [B, UNVERIFIED, 2026-09]
  https://lmstudio.ai/docs/integrations/claude-code (links "Codex - Use Codex with LM Studio").
- **[fact]** MCP sampling: no; elicitation (form): yes. [B, 2026-09]
  https://github.com/apify/mcp-client-capabilities/
- **ESTATE:** the `codex-cursor` wrapper already targets auth2api; OpenRouter as a Codex sidecar is
  *permitted* (spend-capped). **[recommendation]** A zero-code HF block is the cleanest native door
  in the whole estate: `[model_providers.hf] name="Hugging Face router"
  base_url="https://router.huggingface.co/v1" env_key="HF_TOKEN" wire_api="responses"` with a
  `[profiles.hf]` selecting e.g. `model="zai-org/GLM-5.3:novita"`. It replaces `openai_proxy.py`
  from `tools/mcp/glm53-space` for the Codex consumer with no code.

## 4. Cursor (IDE + `cursor-agent` CLI)

- **[fact]** IDE: Settings -> Models offers OpenAI / Anthropic / Google API-key toggles, an
  "Override OpenAI Base URL" checkbox, and "+ Add Model" for custom model ids; the override only
  covers chat / plan / agent panel traffic, while Tab, inline edit and Apply stay on Cursor's
  backend; custom models may be unavailable to subagents. [B, corroborated (three vendor guides,
  no official page fetched), 2026-09]
  https://www.coderouter.io/blog/override-openai-base-url-cursor-configuration-guide ,
  https://docs.llmgateway.io/guides/cursor ,
  https://therouter.ai/blog/cursor-custom-api-endpoint-llm-router-guide/
- **[fact]** CLI: `cursor-agent` authenticates with `CURSOR_API_KEY`; which provider answers is
  decided by the Cursor account settings and cannot be changed programmatically or per run.
  [A (Vercel AI SDK harness doc), 2026-09] https://ai-sdk.dev/providers/ai-sdk-harnesses/cursor
- **[fact]** MCP: tools, prompts, resources, discovery, roots, form elicitation = yes; sampling =
  no. [B, 2026-09] https://github.com/apify/mcp-client-capabilities/
- **ESTATE:** Cursor BYOK and base-URL override are **LOCKED** (never an OpenRouter key; the
  brief locks BYOK generally). auth2api :8317 is the sanctioned Cursor-quota *outbound* bridge and
  retires within 7 days of an official Cursor `/v1` GA. **[inference]** Inbound custom models
  into Cursor therefore have exactly one door: an MCP server in the registry. **[recommendation]**
  The glm53 replacement should be an MCP server whose tool takes `provider`+`model` arguments
  rather than one hardcoded pair, because Cursor cannot be pointed anywhere else.

## 5. Grok CLI (`grok`, Grok Build, `agent.exe`)

- **[fact]** Config is `~/.grok/config.toml` (Windows `%USERPROFILE%\.grok\config.toml`, or
  `$GROK_HOME`); scopes: env `GROK_*`, user, project `.grok/config.toml` (MCP/plugins/permissions
  only), managed `/etc/grok/managed_config.toml`, policy `requirements.toml`. Custom models are
  `[model."<id>"]` tables with `model`, `base_url`, `name`, `description`, `api_key` or `env_key`,
  **`api_backend = "chat_completions" | "responses" | "messages"`**, `temperature`, `top_p`,
  `max_completion_tokens`, `context_window`, `extra_headers`, `query_params`,
  `env_http_headers`, `supports_backend_search`, `supports_reasoning_effort` /
  `reasoning_effort`, `stream_tool_calls`, `max_retries`, `inference_idle_timeout_secs`; defaults
  via `[models] default = "<id>"`, `web_search = "<id>"`. [A, corroborated, 2026-09]
  https://docs.x.ai/build/settings , https://docs.x.ai/build/settings/reference ,
  https://docs.x.ai/build/overview ,
  https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/11-custom-models.md
- **[fact]** Provider-registry style discovery: `[endpoints] models_base_url = ".../v1"` or env
  `GROK_MODELS_BASE_URL` (+ `GROK_MODELS_LIST_URL`) makes Grok fetch `{base}/models` and inherit
  `base_url` into partial `[model.*]` overrides; key from `XAI_API_KEY` / `GROK_CODE_XAI_API_KEY`.
  Auth precedence: per-model `api_key`/`env_key` > session token > `XAI_API_KEY`;
  `[auth] auth_provider_command` can mint tokens. [A, 2026-09] (same sources)
- **[fact]** The estate already uses this door: `[model."cursor-grok-4.6"]` -> auth2api.
- **[inference]** Grok is the most protocol-flexible runtime on the box: HF router works with
  `api_backend="chat_completions"` or `"responses"` and `env_key="HF_TOKEN"`; Ollama and LM Studio
  work with any of the three backends; `[endpoints] models_base_url =
  "https://router.huggingface.co/v1"` would auto-populate the picker from the router's
  `/v1/models` (which carries provider, pricing and `supports_tools` metadata, s.15).
  **[recommendation]** ENABLE, zero code; the only estate check is that no `[model.*]` names an
  OpenRouter URL.
- **[fact]** MCP sampling: not listed as supported anywhere I could find. [C, UNVERIFIED, 2026-09]

## 6. Goose 1.47

- **[fact]** Built-in OpenAI provider reads `OPENAI_API_KEY`, `OPENAI_HOST` (custom endpoint),
  `OPENAI_BASE_PATH` (default `v1/chat/completions`), `OPENAI_CUSTOM_HEADERS`; selection via
  `GOOSE_PROVIDER` / `GOOSE_MODEL` (config `~/.config/goose/config.yaml`). Ollama and Docker Model
  Runner are separate providers. [A, 2026-09]
  https://github.com/block/goose/blob/main/documentation/docs/getting-started/providers.md
- **[fact]** Declarative custom providers: JSON files in `~/.config/goose/custom_providers/<id>.json`
  with `name`, `engine` (`openai` | `anthropic` | `ollama`), `display_name`, `description`,
  `api_key_env`, `base_url`, optional `base_path`, `models[{name, context_limit, max_tokens}]`,
  `headers`, `requires_auth`, `supports_streaming`, `timeout_seconds`; the same file is what
  `goose configure` writes when you add a custom provider (engines `openai_compatible`,
  `anthropic_compatible`, `ollama_compatible`). Declarative providers cannot do OAuth or
  request rewriting. [A, corroborated, 2026-09] https://block-goose.mintlify.app/api/providers/custom ,
  https://block-goose.mintlify.app/development/declarative-providers ,
  https://github.com/block/goose/blob/58f3cc9e/crates/goose/src/config/declarative_providers.rs
- **[fact]** The estate's `GOOSE_PROVIDER=goose-cursor-proxy` is exactly such a declarative file.
- **[fact]** MCP sampling: no (Goose = tools only in the community matrix). [B, 2026-09]
  https://modelcontextprotocol.info/docs/clients/
- **[recommendation]** ENABLE: one more JSON per target (`hf-router.json` with
  `base_url="https://router.huggingface.co"`, `base_path="v1/chat/completions"`,
  `api_key_env="HF_TOKEN"`; `lmstudio.json` engine `openai` at `http://127.0.0.1:1234`; Ollama via
  the built-in provider). Zero code, and the `.agents/skills` SSOT is untouched.

## 7. Fabric 1.4.470

- **[fact]** Config is `~/.config/fabric/.env`, written by the `fabric --setup` wizard. The
  OpenAI vendor honours `OPENAI_API_BASE_URL` (maintainer reply 2025-08); LM Studio is its own
  vendor keyed by `LM_STUDIO_API_URL=http://<host>:1234/v1` (the `/v1` suffix is required for
  model discovery); defaults are `DEFAULT_VENDOR`, `DEFAULT_MODEL`,
  `DEFAULT_MODEL_CONTEXT_LENGTH`. [B (maintainer comments in issues), corroborated, 2026-09]
  https://github.com/danielmiessler/fabric/issues/1199 ,
  https://github.com/danielmiessler/Fabric/issues/1558
- **[fact]** Older `OPENAI_BASE_URL` / `OPENAI_API_BASE` spellings from the Python era appear in
  discussions and do not apply to the Go binary. [B, 2026-09]
  https://github.com/danielmiessler/Fabric/issues/883
- **[fact]** Fabric is not an MCP client; there is no MCP door and no sampling. Prompts (patterns)
  come from `.agents/skills` per the estate SSOT.
- **[recommendation]** ENABLE: HF router as the OpenAI vendor
  (`OPENAI_API_BASE_URL=https://router.huggingface.co/v1`, `OPENAI_API_KEY=$HF_TOKEN`); Ollama and
  LM Studio via their own vendors. Tradeoff: one `.env` = one active OpenAI base URL, so the
  existing `fabric-cursor` wrapper and an HF profile need separate `.env` files or wrapper scripts.

## 8. Agy (Google Antigravity CLI)

- **[fact]** `agy` is the Google Antigravity CLI: a TUI on the same agent harness as Antigravity
  2.0, sharing settings/permissions with it, authenticating via the system keyring with a
  Google Sign-In fallback; it took components from Gemini CLI and Google positions it as the
  Gemini-CLI successor. Headless use: `agy -p "..." --output-format json --mode plan|accept-edits`.
  [A, corroborated, 2026-09] https://github.com/google-antigravity/antigravity-cli ,
  https://antigravity.google/docs/cli/overview/ ,
  https://antigravity.google/blog/introducing-google-antigravity-cli ,
  https://www.antigravity.google/docs/cli/getting-started
- **[fact]** No custom model-provider, base-URL or BYOK key is documented in the CLI docs or
  README; models are Google-managed through the account. Slash commands expose plugins, MCP,
  skills and hooks. [B, absence claim, 2026-09] (same sources; product page
  https://antigravity.google/product/antigravity-cli/ mentions "proxy configuration" only as a
  network proxy).
- **[fact]** MCP sampling: not documented. [C, UNVERIFIED, 2026-09]
- **[inference]** Zero-code HF / Ollama / LM Studio consumption is **IMPOSSIBLE**; door = MCP tool
  only (it is an MCP client). Same shape as Cursor: inbound custom models only via the registry.

## 9. Gemini CLI

- **[fact]** The CLI speaks the Gemini native protocol (`@google/genai`), not OpenAI's. Endpoint
  override is `GOOGLE_GEMINI_BASE_URL` (honoured after fixes #25356/#25357; earlier the CLI ignored
  it when a cached login existed) and the proposed `GEMINI_API_BASE_URL` (PR #16010, passed to the
  SDK as `httpOptions.baseUrl`); `GOOGLE_VERTEX_BASE_URL` for Vertex. Settings live in
  `~/.gemini/settings.json`. [B (PRs/issues), corroborated, 2026-09]
  https://github.com/google-gemini/gemini-cli/issues/15430 ,
  https://github.com/google-gemini/gemini-cli/pull/16010 ,
  https://github.com/google-gemini/gemini-cli/pull/5346
- **[fact]** No official per-provider block or OpenAI-compatible mode exists in the upstream CLI;
  the `modelProviders` JSON seen in guides belongs to a fork (langcli), not to `gemini`.
  [B, 2026-09] https://langcli.com/docs/model_providers
- **[fact]** MCP sampling: no. [B, 2026-09] https://github.com/apify/mcp-client-capabilities/
- **[inference]** Neither HF router, Ollama nor LM Studio serves the Gemini `generateContent`
  shape, so zero-code consumption is **IMPOSSIBLE** and a translator would breach the
  no-LiteLLM lock. Door: MCP tool only.

## 10. OpenCode

- **[fact]** Providers come from the models.dev registry (75+) plus custom entries in
  `opencode.json` / `~/.config/opencode/opencode.json(c)`: `provider.<id>` with
  `npm` (`@ai-sdk/openai-compatible`, `@ai-sdk/anthropic`, ...), `name`, `options.baseURL`,
  `options.apiKey`, and `models.<id>`; the same `baseURL` option overrides any built-in provider.
  Official recipes exist for Ollama (`http://localhost:11434/v1`), LM Studio
  (`http://127.0.0.1:1234/v1`), llama.cpp, vLLM; `ollama launch opencode` writes the config.
  [A, 2026-09] https://opencode.ai/docs/providers/
- **[fact]** Credentials via `opencode auth login` / `/connect`; a small "title" model defaults
  to a Zen-hosted gpt-5-nano unless pinned. Plugins that reuse Claude Pro/Max are called out as
  prohibited by Anthropic. [A, 2026-09] (same page)
- **[fact]** MCP: tools + discovery yes; sampling no. [B, 2026-09]
  https://github.com/apify/mcp-client-capabilities/
- **[recommendation]** ENABLE: an `hf` provider block with `npm="@ai-sdk/openai-compatible"`,
  `options.baseURL="https://router.huggingface.co/v1"`, `options.apiKey="{env:HF_TOKEN}"` and the
  models you want; local servers via the documented recipes. Zero code.

## 11. Aider 0.86

- **[fact]** Any OpenAI-compatible endpoint: `OPENAI_API_BASE=<endpoint>` + `OPENAI_API_KEY` and
  `aider --model openai/<model-name>`; unknown models trigger a warning, not a refusal.
  [A, 2026-09] https://aider.chat/docs/llms/openai-compat.html
- **[fact]** Ollama and LM Studio have dedicated pages (`OLLAMA_API_BASE` + `--model
  ollama_chat/<m>`; `LM_STUDIO_API_BASE` + `LM_STUDIO_API_KEY` + `--model lm_studio/<m>`), and
  per-model tuning goes in `.aider.model.settings.yml` / `.aider.model.metadata.json`.
  [A, UNVERIFIED in-run (pages not fetched this run), 2026-09] https://aider.chat/docs/llms/ollama.html ,
  https://aider.chat/docs/llms/lm-studio.html , https://aider.chat/docs/config/adv-model-settings.html
- **[fact]** Aider is not an MCP client; no sampling. It embeds the `litellm` Python *library*
  for model routing. **[inference]** The estate lock forbids a LiteLLM *proxy/runtime*; the
  vendored library inside aider is pre-existing and not a new orchestration runtime, but it is
  worth stating so nobody reads the lock as "uninstall aider".
- **[recommendation]** ENABLE for HF: `OPENAI_API_BASE=https://router.huggingface.co/v1
  OPENAI_API_KEY=$HF_TOKEN aider --model openai/zai-org/GLM-5.3:novita` (model-id slashes and
  `:provider` suffix pass through as an opaque string after the `openai/` prefix - verify once).

## 12. Ralph (`ralph-cli`, cargo)

- **[fact]** Ralph is a hat-based loop orchestrator that shells out to an installed coding CLI.
  Config precedence: `~/.ralph/config.yml` (user) -> `ralph.yml` (or `$RALPH_CONFIG` / `-c`) ->
  `-c core.field=value`. Backend is `cli.backend` (`claude`, `kiro`, `gemini`, `codex`, `forge`,
  `amp`, `copilot`, `opencode`, `pi`, `custom`) with `cli.prompt_mode: arg|stdin`; each hat can set
  its own `backend`; `ralph run --backend X -- <custom backend args>` passes flags through.
  [A, corroborated, 2026-09] https://mikeyobrien.github.io/ralph-orchestrator/guide/configuration/ ,
  https://mikeyobrien.github.io/ralph-orchestrator/guide/cli-reference/ ,
  https://github.com/mikeyobrien/ralph-orchestrator
- **[fact]** Ralph has no model-provider layer of its own; it inherits whatever the chosen CLI is
  configured to use (Codex `[profiles.*]`, Claude env, OpenCode `opencode.json`, ...).
  [A, 2026-09] (same sources)
- **[inference]** Ralph therefore consumes HF / Ollama / LM Studio exactly when its backend does:
  `backend: codex` + a Codex HF profile (`-- -p hf`) is zero code; `backend: claude` inherits the
  Claude lock. **[recommendation]** Treat Ralph as a multiplier of the per-runtime findings, not a
  runtime to configure; per-hat `backend` lets a cheap HF/local model take `research`/`review`
  hats while `code-assist` stays on the primary model - a tradeoff surface, not a retirement.

## 13. LM Studio (`lms`)

- **[fact]** `lms server start --port 1234` serves OpenAI-compatible `/v1/*` and, since 0.4.1
  (2026-01-30), an Anthropic-compatible `POST /v1/messages` with SSE streaming and tool use; with
  "Require Authentication" on, a token is accepted as `x-api-key` or `Authorization: Bearer`;
  LM Link lets a laptop use a remote rig's model. [A, corroborated, 2026-09]
  https://lmstudio.ai/docs/developer/anthropic-compat , https://lmstudio.ai/blog/claudecode ,
  https://lmstudio.ai/docs/integrations/claude-code
- **[fact]** Consumers with zero code: Claude Code (Messages), Goose/OpenCode/Aider/Fabric/Grok
  (OpenAI), Codex (only if `/v1/responses` is served - LM Studio ships a Codex integration page,
  so likely yes) [B, UNVERIFIED, 2026-09].
- **[inference]** On the 31.6 GB, GPU-less Windows box this is CPU inference; keep context
  >= 25-32k as both vendors advise, which caps usable models at small MoE/8B-class. Tradeoff, not
  a blocker.

## 14. Ollama

- **[fact]** `localhost:11434` serves OpenAI `/v1/chat/completions`, `/v1/models`,
  `/v1/embeddings`, `/v1/responses` (0.13.3+) and Anthropic `/v1/messages` (0.14.0+); cloud models
  use a `:cloud` suffix through ollama.com; `ollama launch claude|codex|opencode|droid [--config]`
  writes each tool's config; `OLLAMA_CONTEXT_LENGTH` should be >= 64k for Claude Code. Known gaps
  in the Messages layer: no `tool_choice`, no prompt caching, no token-count endpoint.
  [A for endpoints/launch, C for gaps and 0.13.3, corroborated, 2026-09]
  https://ollama.com/blog/claude ,
  https://github.com/ollama/ollama/blob/main/docs/api/anthropic-compatibility.mdx ,
  https://www.ssdnodes.com/learn/use-ollama-with-your-coding-agent
- **[fact]** Port 11434 does not collide with the owned 8765 / 8812 / 8317.
- **[recommendation]** `ollama launch <tool> --config` is the single highest-leverage zero-code
  move for local models: it emits correct, current config for four of the installed runtimes.

## 15. Hugging Face router / Spaces / Endpoints as a target

- **[fact]** `https://router.huggingface.co/v1` is a drop-in OpenAI base URL keyed by `HF_TOKEN`
  (token needs inference permission). Model ids take routing suffixes: `:<provider>` (e.g.
  `zai-org/GLM-5.3:novita`), `:fastest` (default), `:cheapest`, `:preferred` (your settings
  order). `GET /v1/models` lists models with per-provider `status`, `context_length`, `pricing`,
  `supports_tools`, `supports_structured_output`, latency and throughput. A Responses API (beta)
  is served at `/v1/responses`. Image generation is not available through the OpenAI client.
  [A, corroborated, 2026-09] https://huggingface.co/docs/inference-providers/en/index ,
  https://huggingface.co/docs/inference-providers/main/en/hub-api ,
  https://huggingface.co/docs/inference-providers/main/en/guides/responses-api ,
  https://huggingface.co/docs/hub/en/models-inference
- **[fact]** No Anthropic Messages endpoint was found on the router. [B, absence claim, 2026-09]
- **[inference]** Consequence table (zero code): Codex (Responses) yes; Grok, Goose, OpenCode,
  Aider, Fabric (chat completions) yes; Claude Code no; Cursor locked; Gemini CLI impossible.
  Dedicated Inference Endpoints and Spaces running TGI/vLLM expose the same OpenAI shape at their
  own base URL and slot into the same config keys - already doctrine in the dedup-set skill, so
  not re-proposed here.

## 16. Matrix - runtime x mechanism (exact file and keys)

Legend: **E** = ENABLE, native, zero code | **L** = native door exists but estate-LOCKED |
**X** = IMPOSSIBLE natively (protocol or product) | **M** = MCP tool is the only door |
**n/a** = the runtime has no MCP client. Grades are in the per-runtime sections above.

| Runtime | OpenAI-compatible base URL + key env | Anthropic-compatible endpoint | Per-model config blocks | Provider registry | MCP sampling (server->client) | Config file |
|---|---|---|---|---|---|---|
| Claude Code | X (Messages only) | **L** `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_API_KEY`/`apiKeyHelper`; allowed only toward auth2api via `claude-cursor` | E `model`, `fallbackModel`, `modelOverrides`, `availableModels`, `ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_*_MODEL` | X (Bedrock/Vertex/Foundry switches only) | no | `~/.claude/settings.json` `env` block; managed settings |
| Codex CLI | E `[model_providers.<id>] base_url, env_key, wire_api="responses"` (Responses API required; ids `openai/ollama/lmstudio` reserved) | X | E `[profiles.<n>] model_provider, model`; `model_catalog_json` | X (built-ins only) | no (elicitation yes) | `~/.codex/config.toml` (user level only) |
| Cursor IDE | **L** Settings->Models: OpenAI key + "Override OpenAI Base URL" + "Add Model" (chat/agent only) | **L** Anthropic key toggle (no base URL) | L custom model names | X | no | GUI settings (no file documented) |
| Cursor agent CLI | X (`CURSOR_API_KEY` only; provider fixed by account) | X | X | X | no | none |
| Grok CLI | E `[model."<id>"] base_url, env_key, api_backend="chat_completions"|"responses"` | E `api_backend="messages"` | E full per-model table (`context_window`, `extra_headers`, `reasoning_effort`, ...) | E `[endpoints] models_base_url` / `GROK_MODELS_BASE_URL` -> `{base}/models` | UNVERIFIED | `~/.grok/config.toml` (`$GROK_HOME`), managed + requirements.toml |
| Goose 1.47 | E `OPENAI_HOST`, `OPENAI_BASE_PATH`, `OPENAI_API_KEY`; or `custom_providers/<id>.json` `engine:"openai"` | E `custom_providers/<id>.json` `engine:"anthropic"` | E `models[{name, context_limit}]` per provider file | X | no | `~/.config/goose/config.yaml` + `~/.config/goose/custom_providers/*.json` |
| Fabric 1.4.470 | E `OPENAI_API_BASE_URL` + `OPENAI_API_KEY`; `LM_STUDIO_API_URL` (needs `/v1`) | X | E `DEFAULT_VENDOR`, `DEFAULT_MODEL`, `DEFAULT_MODEL_CONTEXT_LENGTH` | X | n/a | `~/.config/fabric/.env` via `fabric --setup` |
| Agy (Antigravity CLI) | X | X | X | X | UNVERIFIED | keyring / shared Antigravity settings |
| Gemini CLI | X (Gemini protocol only; `GOOGLE_GEMINI_BASE_URL` / `GEMINI_API_BASE_URL` need a Gemini-shaped target) | X | X | X | no | `~/.gemini/settings.json`, env |
| OpenCode | E `provider.<id>.npm="@ai-sdk/openai-compatible"`, `options.baseURL`, `options.apiKey` | E `npm="@ai-sdk/anthropic"` + `options.baseURL` | E `provider.<id>.models.<id>` | E models.dev (75+), `opencode auth login` | no (discovery yes) | `opencode.json` / `~/.config/opencode/opencode.json(c)` |
| Aider 0.86 | E `OPENAI_API_BASE` + `OPENAI_API_KEY` + `--model openai/<m>`; `LM_STUDIO_API_BASE` + `LM_STUDIO_API_KEY` + `lm_studio/<m>`; `OLLAMA_API_BASE` + `ollama_chat/<m>` | X (via embedded litellm lib only for Anthropic cloud) | E `.aider.model.settings.yml`, `.aider.model.metadata.json` | X | n/a | `.aider.conf.yml`, `.env`, env |
| Ralph | inherits backend | inherits backend | E per-hat `backend`, `-- <args>` | X | n/a | `~/.ralph/config.yml`, `ralph.yml` |
| LM Studio (server) | serves `/v1/chat/completions`, `/v1/responses`, `/v1/models` | serves `/v1/messages` (>= 0.4.1) | n/a (server) | n/a | n/a | `lms server start --port 1234`; API token optional |
| Ollama (server) | serves `/v1/chat/completions`, `/v1/responses` (0.13.3+), `/v1/models` | serves `/v1/messages` (>= 0.14.0) | n/a (server) | `ollama launch claude|codex|opencode|droid --config` writes client configs | n/a | `OLLAMA_HOST`, `OLLAMA_CONTEXT_LENGTH` |

**[fact]** No installed runtime supports MCP sampling; only VS Code Copilot does in the community
matrix. [B, corroborated, 2026-09] https://github.com/apify/mcp-client-capabilities/ ,
https://modelcontextprotocol.info/docs/clients/ . **[inference]** So "the MCP server asks the host
model to think" is not an available door anywhere on this box; an MCP tool that needs a model
must carry its own provider call (the glm53 pattern) or return data for the host to reason over.

## 17. Who can consume what with zero code

| Target -> Runtime | Claude Code | Codex | Cursor | Grok | Goose | Fabric | Agy | Gemini CLI | OpenCode | Aider | Ralph |
|---|---|---|---|---|---|---|---|---|---|---|---|
| HF router `router.huggingface.co/v1` (chat + responses) | X -> **M** | **E** (responses) | **L** -> **M** | **E** | **E** | **E** | **M** | X -> **M** | **E** | **E** | via backend |
| HF Inference Endpoint / Space (OpenAI shape) | X -> **M** | E only if it serves `/v1/responses` (vLLM does, TGI check) | **L** -> **M** | **E** | **E** | **E** | **M** | X -> **M** | **E** | **E** | via backend |
| Ollama `:11434` | **L** (native `/v1/messages`, `ollama launch claude`) -> **M** | **E** (`ollama launch codex`) | **L** -> **M** | **E** (any backend) | **E** (built-in provider) | **E** (Ollama vendor) | **M** | X -> **M** | **E** (`ollama launch opencode`) | **E** (`ollama_chat/`) | via backend |
| LM Studio `:1234` | **L** (native `/v1/messages`) -> **M** | **E** (`codex --oss`, `/v1/responses`) | **L** -> **M** | **E** | **E** | **E** (`LM_STUDIO_API_URL`) | **M** | X -> **M** | **E** | **E** (`lm_studio/`) | via backend |

**[inference]** Read across: six runtimes (Codex, Grok, Goose, Fabric, OpenCode, Aider) reach
every target natively; three (Claude Code, Cursor, Agy) plus Gemini CLI need the MCP door. That
split is the design input for the glm53 replacement: it must serve exactly those four hosts, and it
does not need to exist for the other six.

## 18. Rubric - per find

| # | Name | What | Why THIS estate | How to build or adopt | Source | Value x effort | Novelty-for-us | NATIVE-vs-BUILD |
|---|---|---|---|---|---|---|---|---|
| 1 | Codex HF Responses profile | `[model_providers.hf]` -> `router.huggingface.co/v1`, `wire_api="responses"`, `env_key="HF_TOKEN"`, `[profiles.hf]` per model | Retires `openai_proxy.py` for the Codex consumer; HF router already speaks Responses; OpenRouter sidecar unaffected | 8 lines in `~/.codex/config.toml`; document in the hosted-model-agents skill | s.3, s.15 (A/B) | high x trivial | new (glm53 assumed a wrapper was needed) | NATIVE |
| 2 | Grok `[endpoints] models_base_url` catalog | Point Grok's model list at the HF router `/v1/models`; per-model overrides inherit `base_url` | Router metadata (provider, price, `supports_tools`) lands in the picker; `[model."cursor-grok-4.6"]` shows the pattern is already trusted | `[endpoints] models_base_url="https://router.huggingface.co/v1"` + `XAI_API_KEY`-style key mapping check (Grok reads `XAI_API_KEY`; confirm `env_key` per model can point at `HF_TOKEN`) | s.5 (A) | high x low | new | NATIVE |
| 3 | Grok `api_backend="messages"` | Grok can talk Anthropic Messages to Ollama / LM Studio | Gives a second Messages-speaking client besides Claude Code without touching the Claude lock | one `[model.*]` table per local model | s.5 (A) | medium x trivial | new | NATIVE |
| 4 | `ollama launch <tool> --config` | Ollama writes correct Claude / Codex / OpenCode / Droid configs | Four installed runtimes configured by the vendor, tracked with Ollama releases | run once per tool; commit the emitted config to the skill's recipes | s.14 (A) | high x trivial | new | NATIVE |
| 5 | Goose declarative provider files | `~/.config/goose/custom_providers/hf-router.json`, `lmstudio.json` | Same mechanism as the existing `goose-cursor-proxy`; SSOT prompts untouched | 2 JSON files; `GOOSE_PROVIDER` switch | s.6 (A) | medium x trivial | low (pattern in use) | NATIVE |
| 6 | OpenCode `hf` provider block | `@ai-sdk/openai-compatible` at the router with `{env:HF_TOKEN}` | models.dev registry + custom block = broadest catalog on the box | 15 lines of `opencode.json` | s.10 (A) | medium x trivial | low | NATIVE |
| 7 | Fabric HF vendor profile | `OPENAI_API_BASE_URL=router...` in a second `.env` | Fabric already consumes `.agents/skills`; cheap open models for patterns | wrapper `fabric-hf` alongside `fabric-cursor` selecting `.env` | s.7 (B) | medium x low | low | NATIVE |
| 8 | Aider HF / local flags | `OPENAI_API_BASE`, `lm_studio/`, `ollama_chat/` prefixes | Zero-code pair-programming on open models; note embedded litellm *library* is not the locked proxy | shell aliases in `~/.local/bin` | s.11 (A) | medium x trivial | low | NATIVE |
| 9 | Ralph per-hat backend routing | `hats.<h>.backend` -> a CLI already pointed at HF/local | Cheap hats (research/review) on open models, primary hat unchanged; no second orchestrator | edit `ralph.yml` | s.12 (A) | medium x low | new | NATIVE |
| 10 | Documented-dormant Claude Messages path | Ollama >= 0.14 / LM Studio >= 0.4.1 speak `/v1/messages`; `ANTHROPIC_BASE_URL` would work zero-code | Lock says no; recording the tradeoff (subscription off, local on, no `tool_choice`/caching) keeps the decision reversible | write-up only, no config change | s.2, s.13, s.14 (A) | medium x zero | new | NATIVE but LOCKED |
| 11 | MCP-door spec for the glm53 successor | One MCP server, tool args `provider`, `model`, `base_url` from `.agents/agents.json` + named secret; serves Claude Code, Cursor, Agy, Gemini CLI only | Those four hosts have no native door; the other six do not need the server; no host supports sampling so the tool must call the model itself | build (out of scope for this lens; input to the build lens) | s.4, s.8, s.9, s.16 (A/B) | high x medium | refines glm53 | BUILD (minimal) |
| 12 | Cursor `/v1` GA watch item | Official Cursor OpenAI-compatible endpoint would retire auth2api within 7 days | Lock already binds the timing; no doc found yet for an official `/v1` | monitor Cursor changelog; no action | s.4 (B) | n/a | n/a | NATIVE (future) |

## 19. Summary (10 lines)

1. Six of the installed runtimes - Codex, Grok, Goose, Fabric, OpenCode, Aider - reach the HF router, HF Endpoints/Spaces, Ollama and LM Studio with **zero code** through documented config keys (s.16-17).
2. Codex needs a Responses-API target and the HF router now serves `/v1/responses`, so an 8-line `[model_providers.hf]` block replaces `openai_proxy.py` for Codex (find 1).
3. Grok CLI is the most flexible: `api_backend` = chat_completions | responses | messages, plus `[endpoints] models_base_url` auto-catalog from `/v1/models` (finds 2-3).
4. `ollama launch <tool> --config` emits vendor-maintained configs for Claude Code, Codex, OpenCode and Droid (find 4).
5. Claude Code's only door is `ANTHROPIC_BASE_URL` (Messages), which the estate locks; Ollama >= 0.14 and LM Studio >= 0.4.1 would satisfy it natively - recorded as a dormant tradeoff, not proposed (find 10).
6. Cursor BYOK/base-URL override is locked and `cursor-agent` cannot route providers at all; Agy has no provider setting; Gemini CLI speaks only the Gemini protocol - all four are **MCP-only**.
7. No installed runtime supports MCP sampling, so an MCP tool must carry its own model call (s.16).
8. The glm53 successor therefore needs to serve exactly four hosts and should take provider/model/base URL as arguments (find 11); everything else is config, not code.
9. Estate locks were honoured throughout: no OpenRouter anywhere new, no LiteLLM/LangGraph translator, auth2api untouched, ports untouched, prompts stay in `.agents/skills`.
10. Weakest evidence: the official Codex config reference timed out (relied on three corroborating B sources + a maintainer issue), Grok/Agy MCP-sampling status is UNVERIFIED, and Cursor's Models UI is documented here from vendor guides rather than an official page.
