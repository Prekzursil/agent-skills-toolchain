# Gem-hunt 2026-09-02 / hosted models / lens 13: skills + MCP servers in the wild, and the meta loop

- Lens id: `13-skills-mcps-in-the-wild-and-meta`
- Mode: discovery only (research + findings). No code changed. No PR.
- Branch: `gemhunt/hosted-models-13-skills-mcps-in-the-wild-and-meta` (cut from `origin/main` at `5fa34fda1`).
- Author: Cursor cloud agent (Claude), 2026-09-02.
- Status: IN PROGRESS - sections are pushed as they land; a section marked `[pending]` has not been written yet.

## 0. How to read this file

Every claim carries a tag in this shape: `[T<tier> <status> <date>] <url>`.

- Tier A = primary source (vendor docs, the repo's own README/manifest/LICENSE, an official changelog).
  Tier B = reputable secondary (maintainer blog, well-known aggregator, conference talk).
  Tier C = community/forum/blog post or a single unverified README claim.
- Status: `corroborated` (a second independent source agrees) or `UNVERIFIED` (one source only; treat as a lead).
- Date: the date the source was checked or last updated, so a future reader can judge staleness.
- Prose is additionally labelled **FACT** (sourced), **INFERENCE** (my reasoning from facts), or **RECOMMENDATION** (what I think the estate should do). Nothing unlabelled is load-bearing.

Estate constraints from the brief are cited as `[LOCK]` and are treated as hard; no find below proposes violating one.

## 1. Scope, dedup set, and locks

### 1.1 Question this lens answers

Two questions, in order:

1. **In the wild:** which OSS skills, MCP servers, and CLIs from roughly the last 12 months give an agent (a) Hugging Face model access, (b) OpenAI-compatible model access, (c) a model catalog it can sync from (models.dev, OpenRouter `/models`, HF router model lists), and (d) provider health probing - and how do they rank on maintenance, license, and security?
2. **Meta loop:** how should the estate registry (`.agents/agents.json` + `.agents/local.json`) keep itself current - scheduled catalog sync, capability re-probe, deprecation of dead endpoints, a capability score per endpoint - and what does the failure -> gem -> verify -> retire loop look like for this domain, riding the existing hooks and the fleet supervisor instead of a new daemon?

### 1.2 Already exists (DEDUP-SET from the brief; not re-proposed)

1. Skill `.agents/skills/hosted-model-agents` on branch `live-capture/2026-09-02` (SKILL.md, environments.md, profiles.md, tool-loop.md, evals.md, recipes/hf-space-openai.md) - current doctrine for hosted/local models.
2. `tools/mcp/glm53-space` on `main` (glm53_core.py, mcp_server.py exposing `glm53_chat`, openai_proxy.py) hardcoded to `router.huggingface.co/v1` + `zai-org/GLM-5.3`; owner has decided to DEPRECATE it in favour of a general integration layer.
3. `auth2api` on `127.0.0.1:8317` - the ONLY Cursor-quota OpenAI-compatible bridge (36 model ids), consumed by goose, grok config.toml, fabric-cursor / claude-cursor / codex-cursor wrappers.
4. Registry `.agents/agents.json` (`mcp.servers`, 42 servers) + secrets by name only in `.agents/local.json`.
5. Installed runtimes on the Windows 11 box (31.6 GB RAM, memory-starved, no GPU assumed): claude, codex, cursor-agent, grok + agent.exe, goose 1.47, fabric 1.4.470, agy, gemini CLI, opencode, aider 0.86, ollama, lms, ralph, basic-memory :8765, agent-mail :8812, browser-bridge hub :8770; wrappers ai-mode, grok-mode, qwen-space, claude-swap.

### 1.3 Estate locks (hard constraints, cited as `[LOCK]`)

- `[LOCK-OR]` OpenRouter is a spend-capped CLI/Codex sidecar only: never a Cursor BYOK key, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP.
- `[LOCK-NO-2ND-RUNTIME]` No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory.
- `[LOCK-BRIDGE]` `auth2api :8317` stays the only Cursor bridge and retires within 7 days of an official Cursor `/v1` GA.
- `[LOCK-PORTS]` Ports 8765 / 8812 / 8317 are owned.
- `[LOCK-SSOT]` `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it).
- `[LOCK-CREDS]` Never rotate credentials.
- `[LOCK-TRADEOFF]` Never remove a feature to buy reliability; present tradeoffs instead.

## 2. Estate ground truth this lens leans on `[pending]`

## 3. Survey: HF model access (skills, MCPs, CLIs)

### 3.1 `huggingface/hf-mcp-server` (official HF MCP server) - FIND W1

- **FACT** Official Hugging Face MCP server; hosted at `https://huggingface.co/mcp`, source on GitHub, MIT licence, created 2025-05-06, ~288 stars / 100 forks / 14 open issues at check time. `[TA corroborated 2026-09-02] https://github.com/huggingface/hf-mcp-server` (mirror of the same repo under the maintainer's account: `https://github.com/evalstate/hf-mcp-server`).
- **FACT** Ships as npm packages `@llmindset/hf-mcp-server` (STDIO) and `@llmindset/hf-mcp-server-http` (stateless Streamable HTTP JSON), and as a Docker image `ghcr.io/evalstate/hf-mcp-server:latest` on port 3000; the public deployment serves an MCP Server Card at `/mcp/server-card` with ETag revalidation. `[TA corroborated 2026-09-02] https://github.com/huggingface/hf-mcp-server/blob/main/README.md`
- **FACT** Configuration knobs relevant to this estate: `TRANSPORT`, `DEFAULT_HF_TOKEN`, `MCP_ALLOWED_HOSTS` (host allow-list), `API_TIMEOUT`, `PROXY_TOOLS_CSV` (proxy extra tools from a CSV), `AUTHENTICATE_TOOL`, `STRICT_COMPLIANCE`. `[TB UNVERIFIED 2026-09-02] https://playbooks.com/mcp/huggingface` (aggregator paraphrasing the README env table; the names are consistent with the README but I did not read the README env table verbatim).
- **FACT** One-line install for Claude Code: `claude mcp add hf-mcp-server -t http https://huggingface.co/mcp?login` (OAuth) or with `-H "Authorization: Bearer <HF_TOKEN>"`. `[TA corroborated 2026-09-02] https://github.com/huggingface/hf-mcp-server`
- **INFERENCE** This is Hub *discovery* (search models/datasets/Spaces, read model cards, call Gradio Spaces) - it is not a chat-completion proxy. The dedup-set skill `hosted-model-agents` already names "HF Hub MCP" as doctrine, so the *server* is not new to us. What is new for us is (a) the **Server Card + ETag** pattern as a cheap liveness/version probe for any remote MCP, and (b) `PROXY_TOOLS_CSV` as a precedent for a *data-driven tool list* - the same idea our registry-driven integration layer needs.
- **Security note (FACT)** `MCP_ALLOWED_HOSTS` exists precisely to stop DNS-rebinding style access to a local HTTP MCP; an estate that runs it locally should set it to loopback only. `[TA UNVERIFIED 2026-09-02] https://github.com/huggingface/hf-mcp-server/blob/main/README.md`

### 3.2 HF Inference Providers router - the OpenAI-compatible surface that `glm53-space` hardcodes

- **FACT** Base URL `https://router.huggingface.co/v1`; OpenAI SDK drop-in for **chat completions only**; server-side provider selection defaults to the `:fastest` policy; `:cheapest` and `:<provider>` suffixes on the model id override it. `[TA corroborated 2026-09-02] https://huggingface.co/inference/get-started`
- **FACT** The legacy `api-inference.huggingface.co/models/{id}` serverless endpoint is decommissioned and returns permanent errors pointing at the router. `[TC UNVERIFIED 2025-11-14] https://huggingface.co/datasets/John6666/knowledge_base_md_for_rag_1/commit/7bc4408b933001aa748b5c07b63e1dbd840d4e66` (community migration notes; consistent with HF docs no longer documenting the old host, but I did not find an official deprecation notice in this pass).
- **INFERENCE** Any estate probe that still targets `api-inference.huggingface.co` is a dead-endpoint candidate for the retire loop in section 8.

### 3.3 HF CLI / Python surfaces `[pending - see 3.4 if this run dies]`

### 3.4 What I did not find (negative results)

- No maintained OSS *skill* (SKILL.md-style) dedicated to HF Inference Providers surfaced in this pass beyond vendor docs; the closest is the estate's own `hosted-model-agents` (dedup set). **UNVERIFIED negative** - a targeted search of skill marketplaces is in section 7.

## 4. Survey: OpenAI-compatible model access

### 4.1 `pyroprompts/any-chat-completions-mcp` - FIND W2 (the generic version of `glm53-space`)

- **FACT** TypeScript MCP server exposing ONE tool, `chat`, that relays a question to any OpenAI-SDK-compatible chat-completions endpoint; configured entirely by env: `AI_CHAT_KEY`, `AI_CHAT_NAME`, `AI_CHAT_MODEL`, `AI_CHAT_BASE_URL`; run via `npx @pyroprompts/any-chat-completions-mcp`; MIT; created 2024-12-02; ~156 stars / 28 forks / 8 open issues. `[TA corroborated 2026-09-02] https://github.com/pyroprompts/any-chat-completions-mcp` + `https://mcp.so/servers/any-chat-completions-mcp`
- **FACT** Multiple providers = repeat the server block with different env values (one process per provider/model). `[TA corroborated 2026-09-02] https://github.com/pyroprompts/any-chat-completions-mcp`
- **FACT (maintenance)** An aggregator lists "Updated 7/30/2025". `[TB UNVERIFIED 2026-09-02] https://www.augmentcode.com/mcp/any-chat-completions-mcp` - so likely >12 months since last release at time of writing; treat as **stale-but-simple**.
- **INFERENCE** This is structurally identical to `tools/mcp/glm53-space/mcp_server.py` (one tool, one hardcoded endpoint) with the hardcoding moved to env vars. It proves the *pattern* is common but also shows its ceiling: one process per model, no catalog, no health, no capability metadata. The owner's "general integration layer" should therefore be **registry-driven** (one process, N endpoints read from `.agents/agents.json`-adjacent data), not env-driven. NATIVE-vs-BUILD: adopting this as-is would only buy us a second `glm53-space`; the value is as a **reference implementation** for the tool schema and env contract, not as a dependency.
- **Security (INFERENCE)** Ships the API key as a plain env var to an `npx`-fetched package; acceptable only if pinned by version and vendored, which is how the estate already treats `npx`-style servers (see `tools/mcp/hacktricks-mcp-server` vendoring precedent in `AGENTS.md`).

### 4.2 OpenRouter `openrouterteam/skills` - FIND W3 (a *skill*, not an MCP; catalog read is keyless)

- **FACT** OpenRouter publishes an official skills repo with an `openrouter-models` SKILL.md documenting `GET /api/v1/models` -> `{ data: Model[] }`, server-side filters `?category=` and `?supported_parameters=tools`, per-token USD string pricing, `expiration_date` non-null = deprecated, and 30-minute rolling health fields `uptime_30m`, `latency_30m_ms.p50/p75/p90/p99`, `throughput_30m_tokens_per_sec`. `[TA corroborated 2026-09-02] https://github.com/openrouterteam/skills/blob/main/skills/openrouter-models/SKILL.md` + `https://openrouter.ai/docs/guides/overview/models`
- **FACT** The `/api/v1/models` catalog endpoint needs **no API key**. `[TB corroborated 2026-09-02] https://raw.githubusercontent.com/jeremylongshore/claude-code-plugins-plus-skills/HEAD/plugins/saas-packs/openrouter-pack/skills/openrouter-model-catalog/SKILL.md` (third-party skill pack; corroborated by the vendor docs listing no auth on that route).
- **`[LOCK-OR]` check** Reading a public, keyless catalog JSON is not a BYOK key, not an `ANTHROPIC_BASE_URL`, and not an MCP. It stays inside the lock as long as it is consumed by a *scheduled catalog-sync script* and never wired as an MCP server or a Cursor provider. **RECOMMENDATION**: allowed as a read-only catalog feed; forbidden as anything else.

### 4.3 Estate-side status (FACT from the brief)

- `auth2api :8317` is the only Cursor bridge and consumes 36 `cursor-*` model ids; `[LOCK-BRIDGE]` applies. No wild find in this section replaces it; the finds only concern *non-Cursor* endpoints.

## 5. Survey: model catalog sources and sync tooling

Three catalogs matter for this estate; all three are plain JSON over HTTPS and need at most one existing secret.

| Catalog | URL | Auth | What it carries | Freshness signal | Source |
|---|---|---|---|---|---|
| models.dev | `https://models.dev/api.json` (providers+models), `/models.json` (model-only facts), `/catalog.json` (both) | none | provider `npm`/`env`/`api` (OpenAI-compatible base URL when `npm=@ai-sdk/openai-compatible`), model limits, pricing, capabilities; TOML-in-git, PR-contributed, GitHub-Action validated; used internally by opencode | git history of `anomalyco/models.dev` (formerly `sst/models.dev`) | `[TA corroborated 2026-09-02] https://github.com/anomalyco/models.dev/` ; `https://dev.opencode.ai/docs/models/` |
| OpenRouter | `https://openrouter.ai/api/v1/models` (+ `?supported_parameters=tools`, `?category=`) | none for the list | `id`, `canonical_slug`, `created`, `context_length`, `architecture`, `pricing`, `top_provider`, `supported_parameters[]`, `default_parameters`, `expiration_date`, `benchmarks`; per-endpoint 30-min `uptime_30m` / latency / throughput | `created` unix ts; `expiration_date` | `[TA corroborated 2026-09-02] https://openrouter.ai/docs/guides/overview/models` ; `https://github.com/openrouterteam/skills/blob/main/skills/openrouter-models/SKILL.md` |
| HF router | `https://router.huggingface.co/v1/models` (+ `/{model_id}` for one) | HF token (Inference Providers permission) - the estate already holds one by name | per model: `id`, `owned_by`, `created`, `architecture.input/output_modalities`; per **provider**: `status: live`, `context_length`, `pricing.input/output` (USD per 1M), `supports_tools`, `supports_structured_output`, `first_token_latency_ms`, `throughput`, `is_model_author` | `created`; `providers[].status` | `[TA corroborated 2026-09-02] https://huggingface.co/docs/inference-providers/hub-api` ; `https://huggingface.co/inference/get-started` |

- **FACT (adoption precedent)** OpenClaw (an OSS agent gateway) discovers HF models by calling `GET router.huggingface.co/v1/models` at onboarding **and again at every gateway startup**, merges the result with a built-in catalog for metadata, and falls back to the built-in catalog if the call fails or no key is set. `[TB UNVERIFIED 2026-09-02] https://docs.openclaw.ai/providers/huggingface` - this is exactly the "sync on start, degrade to last-known-good" shape recommended in section 8.
- **FACT (adoption precedent)** opencode loads its provider/model table from models.dev and supports `OPENCODE_MODELS_PATH` to point at a local `_api.json` for testing. `[TA corroborated 2026-09-02] https://github.com/anomalyco/models.dev/` - so the estate's installed `opencode` already carries a models.dev consumer; **INFERENCE**: a synced local copy of `api.json` could be handed to opencode via that env var, giving one catalog to two consumers without new code in opencode.
- **INFERENCE (why three, not one)** models.dev is the only one of the three that is *provider-neutral and keyless with base URLs*, so it is the natural spine for the "general integration layer": it tells you the OpenAI-compatible `api` URL and the `env` var name for every provider. OpenRouter adds live health for the sidecar; HF router adds per-provider capability flags for the HF path. None of them knows about `auth2api :8317`, `ollama`, or `lms`, so the estate registry must remain the SSOT and merely *ingest* these feeds (section 8).
- **RECOMMENDATION** Do not adopt any third-party "catalog sync" package; the three feeds are single `GET`s. The build is a ~100-line stdlib Python fetcher with an ETag/`If-Modified-Since` cache and a last-known-good file - see section 8.2.

## 6. Survey: provider health probing `[pending]`

## 7. Ranking: maintenance x license x security `[pending]`

## 8. Meta loop design `[pending]`

## 9. Rubric table `[pending]`

## 10. Ten-line summary `[pending]`
