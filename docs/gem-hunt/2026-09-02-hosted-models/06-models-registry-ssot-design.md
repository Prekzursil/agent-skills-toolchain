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

_(pending)_

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
