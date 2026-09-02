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

### 3.3 The skills ecosystem the estate publishes into (context for "skills in the wild")

- **FACT** Agent Skills is an open format: a directory with a required `SKILL.md` (YAML frontmatter `name`, `description`; optional `license`, `compatibility`, `metadata` string-map, experimental `allowed-tools`) plus optional `scripts/`, `references/`, `assets/`; progressive loading (~100 tokens of metadata at startup, <5000-token body on activation, resources on demand); project-level cross-client discovery path is **`.agents/skills/`**, user-level `~/.agents/skills/`. `[TA corroborated 2026-09-02] https://agentskills.io/specification` + `https://agentskills.io/skill.md`
- **FACT** Distribution channels: git repo + `npx skills add owner/repo` (Vercel `skills` CLI; skills.sh leaderboard ranks by install telemetry, no submission step), npm via `skillpm` / `skills-npm`, Claude Code plugin marketplaces (`.claude-plugin/marketplace.json`), and an optional `.well-known/agent-skills/index.json` discovery file per domain. `[TB corroborated 2026-09-02] https://vercel.com/kb/guide/agent-skills-creating-installing-and-sharing-reusable-agent-context` + `[TC UNVERIFIED] https://github.com/llodev/skills/blob/main/docs/publishing-guide.md` (the latter also claims SkillsMP indexes ~350k skills in 2026 - single source).
- **INFERENCE** The estate's `.agents/skills/` root *is* the spec's cross-client path, and `AGENTS.md` already restricts frontmatter to `name`+`description` (a strict subset of the spec) - so `[LOCK-SSOT]` is compatible with the wild format and nothing needs to change for Fabric/Goose consumers. The `metadata` map is the spec-sanctioned place for a *skill* version/health tag if the meta loop ever wants one; the estate's current rule forbids it, and I do **not** recommend loosening the rule (a sidecar file does the same job - section 8.4).

### 3.4 What I did not find (negative results)

- No maintained OSS *skill* (SKILL.md-style) dedicated to HF Inference Providers surfaced in this pass beyond vendor docs; the closest is the estate's own `hosted-model-agents` (dedup set). **UNVERIFIED negative** (one search pass over web + skills.sh-adjacent aggregators).
- No OSS tool found that *combines* catalog sync + capability probing + registry write-back; every find covers one leg. **INFERENCE**: this is why section 8 is a build (small), not an adoption.

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

## 6. Survey: provider health probing

Two independent signal families exist; the best OSS tools combine them and treat the *gap* as the signal.

### 6.1 Signal family A - vendor status feeds (what the provider *claims*)

| Provider family | Machine-readable feed | Source |
|---|---|---|
| Anthropic (Claude) | Atlassian Statuspage: `https://status.claude.com/api/v2/summary.json` (components + unresolved incidents + maintenances) and `/api/v2/status.json` (rollup `indicator` in `none|minor|major|critical`) | `[TA corroborated 2026-09-02] https://status.anthropic.com/api/v2/` |
| OpenAI | `https://status.openai.com/api/v2/summary.json` - documented as Statuspage-shaped but has gone 404 for hours during a status-site migration (2025-02-27) | `[TC UNVERIFIED 2025-02-28] https://community.openai.com/t/is-the-status-url-still-up-https-status-openai-com-api-v2-summary-json/1131389` |
| Groq, Cohere, DeepSeek, Replicate, Moonshot, MiniMax, SiliconFlow | Statuspage `summary.json` | `[TB UNVERIFIED 2026-09-02] https://github.com/3389ro/ai-status-monitor` (feed-format table in README) |
| Google Gemini / Vertex | Google Cloud `incidents.json` | same |
| Azure OpenAI / AI Foundry | Azure status RSS | same |
| xAI | custom RSS | same |
| Perplexity | Instatus `summary.json` | same |
| **Hugging Face** | **Better Stack `index.json`** | same |
| **Mistral, Zhipu / GLM** | **no public feed** - reported `Unknown` | same |

- **INFERENCE** The two providers the estate leans on through `router.huggingface.co` for `zai-org/GLM-5.3` (Zhipu upstream) have *no* vendor feed, so for that path only synthetic probing (family B) or the HF router's own `providers[].status` field (section 5) can say anything. This is a concrete reason the retire-loop must not depend on vendor feeds alone.

### 6.2 Signal family B - synthetic probes (what you *observe*)

- **`yejinai/llm-health-monitor` - FIND W4.** **FACT** Zero-database self-hosted monitor that probes each configured model with the cheapest possible request (1 output token), fetches the provider's official Statuspage `status.json` *at the same moment*, and exposes the claim-vs-reality diff as a first-class signal (`/api/health/insights`, Prometheus `llm_health_hidden_degradation`); tunables include `degradedLatencyRatio` (default 2.0 x the model's median baseline) and `confirmationRuns` (consecutive failures before flagging, default 1, "raise to 2-3 to ignore blips"); key management is loopback-only with masked responses; new providers are added by registering in a `ProviderRegistry` plus an optional Statuspage URL. `[TA UNVERIFIED 2026-09-02] https://github.com/yejinai/llm-health-monitor` (single source: its README; licence and commit cadence not confirmed in this pass - **check before adopting**).
- **`3389ro/ai-status-monitor` - reference only.** **FACT** WPF / .NET 10 single-file Windows desktop console polling 14 providers' *official* feeds every 60 s, normalising to six states, computing 7/30/90-day SLA, with a loopback REST API on `127.0.0.1:12100` (bearer token, per-IP rate limit). It explicitly never sends synthetic requests. `[TA UNVERIFIED 2026-09-02] https://github.com/3389ro/ai-status-monitor` - **INFERENCE**: a resident WPF process on a 31.6 GB, memory-starved box is the wrong shape for us; the value is its feed table (6.1) and its six-state normalisation, both copyable in an hour.
- **`aidown.io` (AI Down) - external free feed.** **FACT** Aggregates 50+ providers from three sources (official feeds, synthetic probes routed through OpenRouter every 1-5 min measuring latency and TTFT, crowdsourced reports) and exposes a public REST API: `/api/v1/status`, `/api/v1/status/{provider}`, `/api/v1/incidents`, `/api/v1/uptime/{provider}`, `/api/v1/timeline`, `/api/v1/correlation`. `[TB UNVERIFIED 2026-09-02] https://aidown.io/docs` - **INFERENCE**: a keyless third-party read; useful as a *tie-breaker* when our own probe and the vendor feed disagree, never as the primary signal (single vendor, no SLA to us).
- **Catalog-embedded health (already found in section 5).** OpenRouter's per-endpoint `uptime_30m` / `latency_30m_ms` / `throughput_30m_tokens_per_sec` and the HF router's per-provider `status`, `first_token_latency_ms`, `throughput` mean two of our three catalogs *are* health feeds. `[TA corroborated 2026-09-02]` (sources in section 5 table).

### 6.3 Design principles extracted (INFERENCE, feeding section 8)

1. **Probe with the cheapest legal call.** For OpenAI-compatible endpoints that is `GET /v1/models` (no tokens) first, then a 1-token `chat/completions` only when capability must be re-verified. HF router and OpenRouter `GET /models` are free; `auth2api :8317` `GET /v1/models` spends no Cursor quota (FACT from the brief: it lists 36 ids).
2. **Hysteresis before retirement.** `confirmationRuns >= 2-3` (llm-health-monitor's own advice) - a single failed probe must never deprecate an endpoint; `[LOCK-TRADEOFF]` demands the tradeoff be shown, not the feature removed.
3. **Record claim and observation separately** and score the gap; a provider that says `operational` while our probe fails is a *different* state from one that is honestly down.
4. **Compare against the model's own baseline**, not a global constant (`degradedLatencyRatio` semantics).

## 7. Ranking: maintenance x license x security

### 7.1 Security tooling that should gate any adoption - FIND W5

- **`mcp-scan` (Invariant Labs -> Snyk `agent-scan`).** **FACT** Open-source CLI that auto-discovers Claude / Cursor / Windsurf-style MCP configs, connects to each server, pulls tool descriptions and statically checks them for prompt injection, tool poisoning, cross-origin escalation (tool shadowing) and *rug pulls* via **hash-based pinning of tool descriptions**; issue codes E001/E002; `--json` for CI; `uvx mcp-scan@latest scan --local-only` avoids the cloud Guardrails API at some accuracy cost. `[TA corroborated 2026-09-02] https://github.com/invariantlabs-ai/mcp-scan/blob/608b50b0/README.md` + `https://invariantlabs.ai/blog/introducing-mcp-scan`
- **FACT** As of the 0.4 line it inventories **harnesses, MCP servers *and skills*** and shipped a technical report on threats in the agent-skill ecosystem. `[TA UNVERIFIED 2026-09-02] https://github.com/invariantlabs-ai/mcp-scan/blob/608b50b0/README.md`
- **FACT** Launched April 2025; project acquired by Snyk and now lives at `github.com/snyk/agent-scan` with >2,600 stars; Apache-2.0 (forks show the licence). `[TB corroborated 2026-09-02] https://gingerlabs.ai/blog/how-to-audit-mcp-servers-using-mcp-scan` + fork metadata at `https://github.com/gmlglzh/mcp-scan`
- **Privacy caveat (FACT)** Default mode shares tool names and descriptions with invariantlabs.ai under their ToS; `--local-only` keeps everything on the box. `[TA corroborated 2026-09-02] https://github.com/chatlotus/mcp-scan` (fork README mirrors upstream text) - **RECOMMENDATION**: estate use must be `--local-only`; 42 registry servers include private tooling.
- **INFERENCE (why this matters for the meta loop)** "Hash-pinned tool descriptions, alarm on change" *is* a capability re-probe. The same hash the scanner computes for security is the drift signal the registry needs; one probe, two consumers.

### 7.2 Catalog-of-MCP-servers feed - FIND W6

- **FACT** The official MCP Registry (`registry.modelcontextprotocol.io`, preview; backed by Anthropic, GitHub, PulseMCP, Microsoft) exposes `GET /v0.1/servers` with cursor pagination, `search=`, `version=latest`, and **`updated_since=<RFC3339>`** for incremental sync; `include_deleted` flips to `true` automatically when `updated_since` is supplied, so **deletions propagate**. Entries follow `server.json` (schema `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`) with `packages[].registryType/identifier/version/transport`, `remotes[]`, `environmentVariables[]`, and a reverse-DNS-namespaced `_meta` extension block that sub-registries use for ratings, download counts and **security-scan results**. The registry is explicitly *not* meant for direct host consumption; hosts should read a sub-registry (e.g. PulseMCP `com.pulsemcp/server-version.status`). `[TA corroborated 2026-09-02] https://modelcontextprotocol.io/registry/registry-aggregators` + `https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/official-registry-api.md` + `https://modelcontextprotocol.io/registry/about` + `[TB] https://www.pulsemcp.com/api/docs/v0.1`
- **INFERENCE** Of the 42 servers in `.agents/agents.json`, those that are public npm/pypi packages can be *cross-referenced* against this feed: a server that upstream marks deleted, or whose `latest` version moves, is a retire/upgrade candidate. `_meta` shows the industry pattern for attaching a per-server score without touching the schema - which matches the repo rule in `AGENTS.md` ("treat consumer-owned manifests as closed schemas; store provenance in `.provenance/`").

### 7.3 Ranking table

Scores are 0-3 per axis (3 = best). Maintenance = release/commit recency and bus-factor; Licence = permissive and unambiguous; Security = attack surface + default posture. **Sourced facts feed the score; the score itself is INFERENCE.**

| # | Find | Maint. | Licence | Security | Total | Notes |
|---|---|---|---|---|---|---|
| W1 | `huggingface/hf-mcp-server` | 3 (vendor-owned, active 2025-05 -> now) | 3 (MIT) | 2 (needs `MCP_ALLOWED_HOSTS` pinned; OAuth or bearer) | **8** | Already doctrine; new value is Server Card/ETag probe + `PROXY_TOOLS_CSV` pattern |
| W5 | `mcp-scan` / `snyk/agent-scan` | 3 (Snyk-backed, 2.6k stars) | 3 (Apache-2.0) | 2 (cloud default; `--local-only` required) | **8** | Gate + drift signal |
| W6 | Official MCP Registry API | 2 (preview; "breaking changes or data resets may occur") | 3 (spec/open) | 3 (read-only JSON, no auth for reads) | **8** | Incremental sync with deletions |
| W3 | `openrouterteam/skills` `openrouter-models` | 3 (vendor-owned) | UNVERIFIED (repo licence not read) | 3 (keyless read) | **6+** | `[LOCK-OR]`: catalog read only |
| W4 | `yejinai/llm-health-monitor` | UNVERIFIED (README only) | UNVERIFIED | 2 (loopback key mgmt; but holds keys) | **2+** | Adopt *design*, not code, until verified |
| W2 | `pyroprompts/any-chat-completions-mcp` | 1 (last visible update 2025-07) | 3 (MIT) | 1 (key in env to `npx` package; one tool = one blind relay) | **5** | Reference pattern only; do not adopt |
| - | `3389ro/ai-status-monitor` | UNVERIFIED | UNVERIFIED | 2 (loopback API, bearer) | n/a | Feed table copied; WPF resident process rejected for RAM |
| - | `aidown.io` public API | n/a (SaaS) | n/a | 3 (keyless read) | n/a | Tie-breaker feed only |

**RECOMMENDATION (ranking outcome):** adopt W5 as a gate (it is a CLI, not a runtime, so `[LOCK-NO-2ND-RUNTIME]` is untouched), *read* W6 and the three catalogs of section 5 as feeds, copy the design of W4 into an estate script, and treat W2 as a negative example when designing the `glm53-space` replacement.

## 8. Meta loop design `[pending]`

## 9. Rubric table `[pending]`

## 10. Ten-line summary `[pending]`
