# Gem-hunt 2026-09-02 / hosted models / lens 13: skills + MCP servers in the wild, and the meta loop

- Lens id: `13-skills-mcps-in-the-wild-and-meta`
- Mode: discovery only (research + findings). No code changed. No PR.
- Branch: `gemhunt/hosted-models-13-skills-mcps-in-the-wild-and-meta` (cut from `origin/main` at `5fa34fda1`).
- Author: Cursor cloud agent (Claude), 2026-09-02.
- Status: COMPLETE for this run (all 10 sections written); later commits on this branch only refine citations.

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

## 2. Estate ground truth this lens leans on

All items in this section are **FACT** read from the working tree at `origin/main` `5fa34fda1` on 2026-09-02 (tier A, corroborated by direct file read). Paths are repo-relative.

### 2.1 The registry already carries a supervisor contract - it just has no consumer in-repo

`.agents/agents.json` top-level keys: `schemaVersion, instructions, integrations, syncMode, mcp, workspace, lastSync, lastSyncSourceHash`. `syncMode = "source-only"`, `lastSync = 2026-06-15T14:35:24Z` (about 11 weeks stale at time of writing). `mcp` has three children:

- `mcp.servers` - 42 entries (33 `stdio`, 9 `http`). Per-entry keys in use across the fleet: `label, description, targets, enabled, transport, command, args, url, headers, env, requiredEnv, credentialNames, maxPrivateBytes, processMatch, singletonKey, resourceException, tags, x_codex, x_cursor`. Tags in use: `approved` (41), `claude-only` (38), `local` (34), `stdio` (33), `http` (9), `remote` (7), `shared` (4), `remote-required` (2), `resource-exception` (2), and singletons `hosted-inference`, `owner-requested`, `default-off`, `unapproved`, `owner-identity`, `owner-present-write`, `own-feed-write`.
- `mcp.policy` - `{"required": false, "startupTimeoutMs": 30000, "toolTimeoutMs": 30000, "healthProbe": {"kind": "mcp-tools-list", "timeoutMs": 30000}, "toolAllowlist": ["*"], "approvalMode": "native", "maxPrivateBytes": 536870912}`. **A health-probe kind is already declared: `tools/list`.**
- `mcp.supervision` - `{"totalIdlePrivateBytes": 6442450944, "failureThreshold": 3, "failureWindowSeconds": 600, "quarantineScope": "session", "duplicatePolicy": "report-unless-exact-process-tree"}`. **Hysteresis (3 failures / 10 min -> session quarantine) and a 6 GiB idle-RSS fleet budget are already policy.**
- The only server tagged `hosted-inference` is `glm53-space` (`uv run --locked --directory .../tools/mcp/glm53-space python mcp_server.py`, `requiredEnv: ["HUGGINGFACE_TOKEN"]`, tags `approved, claude-only, hosted-inference, owner-requested, stdio`). It is the dedup-set item slated for deprecation.
- `rg` for `failureThreshold|healthProbe|totalIdlePrivateBytes|quarantineScope` across the repo finds **no code consumer** (only a vendored ralph doc). **INFERENCE**: the supervisor *contract* lives in the registry but its *enforcement* is either off-repo (on the Windows box) or not yet built. Section 8 therefore designs against the contract as written and names enforcement as a verify step, not an assumption.
- `.agents/local.json` is not present in this checkout (expected: it is the per-box secrets-by-name file from the brief).

### 2.2 Hooks that already exist and that the meta loop can ride

`hooks/hooks.json` is a Claude-Code-style hooks manifest (`description`, `hooks` keyed by event). Events wired today: `SessionStart` (1), `PreToolUse` (10), `PostToolUse` (8), **`PostToolUseFailure` (1) -> `post:mcp-health-check`**, `PreCompact` (1), `Stop` (4), `SessionEnd` (1). The `hooks/` directory holds ~80 hook packages; the ones this lens rides:

| Hook | Path | Event / role | Why it matters here |
|---|---|---|---|
| mcp-liveness | `hooks/mcp-liveness/liveness.py`, `critical.json` | `SessionStart` always; `PreToolUse(mcp__basic-memory__*)` throttled 60 s | Defines liveness as a **real JSON-RPC `initialize` handshake whose result advertises `capabilities.tools`** (`serves_tools`), not a TCP port; distinguishes `up` / `dead-listening` / `down`; INCONCLUSIVE never manufactures a false DOWN; **fail-open** (any error -> exit 0); auto-restart only for the keystone (`restart-basic-memory.ps1`, detached); `handshake_timeout 5.0`, `tcp_timeout 1.5`, `throttle_seconds 60`. Mirrors `mcp_doctor`'s `_mcp_handshake_ok`. |
| capability-catalog | `hooks/capability-catalog/catalog.json`, `inject.py` | `SessionStart` additionalContext, once per session | A **data-driven "server/skill -> what + WHEN" catalog** already injected to steer tool choice. The natural read-side of a capability score. |
| event-ledger | `hooks/event-ledger/ledger.py` | append-only typed JSONL per project at `~/.claude/event-ledger/<slug>/events.jsonl` + `state.json` projection; `sessionstart-replay.py`, `stop-hook.py`, `prune-report.py` | The place a probe *failure* / *retire* event should be written so it survives compaction and is replayed at SessionStart. |
| heartbeat | `hooks/heartbeat/heartbeat.py` | `SessionStart` always, `Stop` only when noteworthy | One-line durability health banner - the human-facing surface for "endpoint X quarantined". |
| fresh-verify | `hooks/fresh-verify/trigger.py` | `PostToolUse` one-shot directive to run the `fresh-context-verify` skill | Existing "re-verify a stale anchor" trigger; the verify leg of the loop. |
| mcp-canonical-sync | `hooks/mcp-canonical-sync/sync.py` | `SessionStart`: keep every project `.mcp.json` synced to canonical `~/.mcp.json` | Existing *outbound* sync from registry to consumers - the write-back path a deprecation must flow through. |
| mcp-defaults, mcp-userscope-sync | `hooks/mcp-defaults/enforce-mcp-defaults.py`, `hooks/mcp-userscope-sync/heal.py` | enforcement / heal | Existing enforcement points for registry -> client config. |
| bg-registry | `hooks/bg-registry/register.py`, `reconcile.py`, `reconcile_requeue.py` | background-job registry with reconcile + requeue | Precedent for "reconcile a registry against reality and requeue" - the same verb the catalog sync needs. |

### 2.2b Inventory / write-back and probe engines that already exist

- `tools/mcp-manager` (`uv run app.py status | preset list | json`): unified MCP inventory across the **Claude plane** (`~/.claude.json` user scope + per-project `disabledMcpServers`) and the **Funnel plane** (`~/.mcp-funnel-profiles.json` + `mcp-profile.ps1`), with named **presets** for one-action bulk enable/disable; CI enforces 100% branch coverage (`AGENTS.md`). **INFERENCE**: this is the sanctioned *write-back* surface for a retire step - "disable via preset" rather than hand-editing client configs.
- `mcp_doctor.py` / `lib.mcp_doctor_core` is deployed **off-repo** at `~/.local/opt/re-harness/` (per `tools/re-harness/mcp_doc_drift.py`, which describes itself as the "documented-but-missing MCP audit - additive companion to mcp_doctor.py" for servers that are documented but not mounted or failed to connect). `hooks/mcp-liveness` says it mirrors `mcp_doctor`'s `_mcp_handshake_ok`. **INFERENCE**: an L1 handshake engine for the fleet already exists on the box; the probe ladder in 8.3 should wrap it, not re-implement it.
- The gem-hunt skill itself (`.agents/skills/gem-hunt/SKILL.md`) already names this lens's job verbatim: a **meta** lens for "auto-gem-mining, capability-score, the closed failure->gem->verify->retire loop"; step 5 "VERIFY before acting (peer-review) ... findings are claims, not truth"; step 6 "A gem-hunt is discovery, not a build - don't implement mid-hunt"; and a hard rule against any new heavyweight component ("2nd orchestration runtime, vector-DB/KG memory ... OpenRouter MCP, LiteLLM, Cursor BYOK, LangGraph"), preferring "enable a native feature" and "fold into the existing dispatcher" over "new hook file / new MCP". The locks in 1.3 are therefore already doctrine in the skill, not only in the brief.

### 2.3 Scheduling precedent (no new daemon needed)

`scripts/claude-science/register-tasks.ps1` registers two Windows Scheduled Tasks (`ClaudeScienceWatchdog`, `ClaudeScienceMaintain`) with `MultipleInstances IgnoreNew` at the scheduler plus a `Global\` mutex in the script. **INFERENCE**: the estate already has a sanctioned pattern for "run a maintenance script on a timer without a resident process"; a catalog-sync task is a third registration in the same style, not a daemon.

### 2.4 Repo rules that shape the design

- `AGENTS.md`: "Treat consumer-owned manifests as closed schemas. Never add a manifest key merely to carry provenance; store provenance in `.provenance/<repo-relative-manifest-path>.md`."  -> capability scores go in a **sidecar**, not into `agents.json` entries (8.4).
- `AGENTS.md`: helper scripts "should default to read-only discovery where possible and must document stop rules before any risky workflow." -> the sync/probe script is read-only by default; write-back is a flagged second step (8.5).
- `CLAUDE.md` SSOT-WIRE block: only `~/source/ast-integrate` is edited and only `~/source/agent-skills-toolchain` is executed from; `command-center/ssot/ssot_drift_gate.py` fails closed when the executed checkout is behind `main`. -> the loop must run from the executed checkout and should call the drift gate first (8.5).

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

- **`yejinai/llm-health-monitor` - FIND W4.** **FACT** Zero-database self-hosted monitor that probes each configured model with the cheapest possible request (1 output token), fetches the provider's official Statuspage `status.json` *at the same moment*, and exposes the claim-vs-reality diff as a first-class signal (`/api/health/insights`, Prometheus `llm_health_hidden_degradation`); tunables include `degradedLatencyRatio` (default 2.0 x the model's median baseline) and `confirmationRuns` (consecutive failures before flagging, default 1, "raise to 2-3 to ignore blips"); key management is loopback-only with masked responses; new providers are added by registering in a `ProviderRegistry` plus an optional Statuspage URL. `[TA corroborated 2026-09-02] https://github.com/yejinai/llm-health-monitor` (README for behaviour; GitHub API for metadata: **MIT**, 0 stars, single author, created 2026-07-22, last push 2026-07-21 - so the *design* is citable but the code has no community behind it).
- **`3389ro/ai-status-monitor` - reference only.** **FACT** WPF / .NET 10 single-file Windows desktop console polling 14 providers' *official* feeds every 60 s, normalising to six states, computing 7/30/90-day SLA, with a loopback REST API on `127.0.0.1:12100` (bearer token, per-IP rate limit). It explicitly never sends synthetic requests. `[TA corroborated 2026-09-02] https://github.com/3389ro/ai-status-monitor` (README; GitHub API: licence `NOASSERTION`, 2 stars, last push 2026-05-25) - **INFERENCE**: a resident WPF process on a 31.6 GB, memory-starved box is the wrong shape for us; the value is its feed table (6.1) and its six-state normalisation, both copyable in an hour.
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
| W5 | `mcp-scan` / `snyk/agent-scan` | 3 (Snyk-backed; 2,993 stars, created 2025-04-07, last push 2026-09-01, 10 open issues) | 3 (Apache-2.0) | 2 (cloud default; `--local-only` required) | **8** | Gate + drift signal. `[TA corroborated 2026-09-02] GitHub API repos/snyk/agent-scan` |
| W6 | Official MCP Registry API | 2 (preview; "breaking changes or data resets may occur") | 3 (spec/open) | 3 (read-only JSON, no auth for reads) | **8** | Incremental sync with deletions |
| W3 | `openrouterteam/skills` `openrouter-models` | 3 (vendor-owned; created 2026-01-31, pushed 2026-09-01, 241 stars, 89 open issues) | **0 (no licence file detected by GitHub)** | 3 (keyless read) | **6** | `[LOCK-OR]`: catalog read only. **Do not vendor the SKILL.md text** - cite the vendor docs instead, which say the same thing. `[TA corroborated 2026-09-02] GitHub API repos/openrouterteam/skills` |
| W4 | `yejinai/llm-health-monitor` | 1 (single author, 0 stars, created 2026-07-22, last push 2026-07-21) | 3 (MIT) | 2 (loopback key mgmt; but holds keys) | **6** | Adopt *design*, not code: too young and too thin a bus factor to depend on. `[TA corroborated 2026-09-02] GitHub API repos/yejinai/llm-health-monitor` |
| W2 | `pyroprompts/any-chat-completions-mcp` | 1 (last visible update 2025-07) | 3 (MIT) | 1 (key in env to `npx` package; one tool = one blind relay) | **5** | Reference pattern only; do not adopt |
| - | `3389ro/ai-status-monitor` | 1 (2 stars, created 2026-05-12, last push 2026-05-25) | 0 (`NOASSERTION` - non-standard licence) | 2 (loopback API, bearer) | n/a | Feed table copied as *facts about vendors*; code untouchable; WPF resident process rejected for RAM. `[TA corroborated 2026-09-02] GitHub API repos/3389ro/ai-status-monitor` |
| - | `aidown.io` public API | n/a (SaaS) | n/a | 3 (keyless read) | n/a | Tie-breaker feed only |

**RECOMMENDATION (ranking outcome):** adopt W5 as a gate (it is a CLI, not a runtime, so `[LOCK-NO-2ND-RUNTIME]` is untouched), *read* W6 and the three catalogs of section 5 as feeds, copy the design of W4 into an estate script, and treat W2 as a negative example when designing the `glm53-space` replacement.

## 8. Meta loop design

Everything in this section is **RECOMMENDATION** unless tagged otherwise. It is a design, not code; nothing was built in this run.

### 8.1 Design principles (each traced to a fact above)

1. **No new daemon.** Three timers already exist in sanctioned shapes: Claude hooks (`SessionStart`, `PreToolUse`, `PostToolUseFailure`, `Stop`), the `mcp.supervision` contract in the registry, and Windows Scheduled Tasks (`register-tasks.ps1` precedent). The loop is three scripts invoked by those, plus one sidecar JSON. (2.2, 2.3)
2. **Fail-open, inject-only, read-only by default.** Copy `mcp-liveness`'s contract verbatim: any error -> exit 0, emit nothing; never block a tool call; write-back is a separate, flagged command. (2.2, 2.4)
3. **Hysteresis is policy, not a constant.** `failureThreshold: 3` / `failureWindowSeconds: 600` from `mcp.supervision`, corroborated by llm-health-monitor's `confirmationRuns` advice. (2.1, 6.2)
4. **Claim and observation are separate columns.** Vendor feed / catalog says X; our probe saw Y; the score uses both and flags the gap. (6.3)
5. **The registry stays SSOT; feeds are ingested, never authoritative.** models.dev / OpenRouter / HF router / MCP Registry know nothing about `auth2api :8317`, `ollama`, `lms`, or the 33 local stdio servers. (5, `[LOCK-BRIDGE]`, `[LOCK-PORTS]`)
6. **Closed schemas.** No new keys on `mcp.servers.*` entries for scores; a sidecar file carries them and `.provenance/` carries the why. (2.4)
7. **Locks are inputs to the state machine.** An endpoint whose *only* path would violate a lock (e.g. OpenRouter as Cursor BYOK) is unreachable by construction, not merely discouraged. (1.3)

### 8.2 Scheduled catalog sync

**What runs:** one stdlib-Python script, working title `command-center/ssot/catalog_sync.py` (sits beside `ssot_drift_gate.py`; not created in this run).

**When:** a third Scheduled Task in the `register-tasks.ps1` style (`MultipleInstances IgnoreNew` + `Global\` mutex), daily at a quiet hour, plus an opportunistic run from the `SessionStart` heartbeat *only if* the last successful sync is older than 7 days (the same "staleness -> nudge" shape `fresh-verify` uses). No run at all if the box is above the `totalIdlePrivateBytes` budget - the sync is a nice-to-have.

**Feeds and caching (all `GET`, all cached with `ETag`/`If-Modified-Since`, all kept as last-known-good on failure):**

| Feed | Key | Purpose | Lock check |
|---|---|---|---|
| `https://models.dev/api.json` | none | provider base URLs + env var names + model limits/prices; spine for the general integration layer | clean |
| `https://openrouter.ai/api/v1/models` | none | `expiration_date` (deprecations), `supported_parameters`, health fields for the *sidecar* only | `[LOCK-OR]` clean: read-only, never wired as MCP/BYOK |
| `https://router.huggingface.co/v1/models` | existing HF token by name (`HUGGINGFACE_TOKEN`, already required by `glm53-space`) | per-provider `status`, `supports_tools`, `supports_structured_output`, latency, throughput, price | clean; `[LOCK-CREDS]` clean (no rotation) |
| `https://registry.modelcontextprotocol.io/v0.1/servers?updated_since=<last>&version=latest` | none | upstream version moves and deletions for the public-package subset of the 42 servers | clean |
| Vendor status feeds (6.1) for providers actually referenced by enabled endpoints | none | claim column | clean |
| `http://127.0.0.1:8317/v1/models` | none (loopback) | the 36 `cursor-*` ids as observed, so a Cursor-side model rename is caught | `[LOCK-BRIDGE]`/`[LOCK-PORTS]` clean: read-only on an owned port |
| `http://127.0.0.1:11434/v1/models` (ollama), LM Studio `/v1/models` when up | none | local model inventory | clean |

**Output:** `state/catalog/<feed>.json` (raw, last-known-good) + `state/catalog/index.json` (normalised: `endpoint_id -> {base_url, auth_env, models[], claims{tools,structured,ctx,price}, source, fetched_at, etag}`) under the estate's state root (the same root `event-ledger` uses, `~/.claude/`, or `command-center/ssot/state/` - owner's choice; **not** in `.agents/agents.json`). The **diff against the previous index is the product**: new models, vanished models, `expiration_date` set, `status != live`, version bump upstream, and "our entry references a URL no feed knows" (a decommissioned host such as `api-inference.huggingface.co`, 3.2).

**Consumers of the index (no new code in them):** `hooks/capability-catalog/inject.py` reads `catalog.json` today; a generated section appended from `index.json` puts "which hosted models actually work right now" in front of the model at SessionStart. `opencode` can be pointed at a synced models.dev copy via `OPENCODE_MODELS_PATH` (5). Fabric/Goose keep reading `.agents/skills` unchanged (`[LOCK-SSOT]`).

### 8.3 Capability re-probe ladder

Probes are ordered by cost; a run stops at the first rung that answers the question being asked. Every rung is idempotent and read-only except L4, which spends one token.

| Rung | Probe | Applies to | Cost | Source of the pattern |
|---|---|---|---|---|
| L0 | Static: entry `enabled`, `requiredEnv` names present in `.agents/local.json`, `command` path exists, `url` parses, no `[LOCK]` violated | all 42 | zero | registry (2.1) |
| L1 | JSON-RPC `initialize`; assert `capabilities.tools` present (`serves_tools`); classify `up / dead-listening / down / inconclusive` | http + stdio MCP servers | ~1 s | `mcp-liveness` (2.2) |
| L2 | `tools/list`; **hash the tool names+descriptions**; compare to pinned hash -> `unchanged / changed (rug-pull candidate) / shrunk` | MCP servers | ~1 s | `mcp.policy.healthProbe.kind = mcp-tools-list` (2.1) + mcp-scan rug-pull pinning (7.1) |
| L3 | `GET /v1/models`; compare id set to registry/index; for HF router also read `providers[].status`/`supports_*` | OpenAI-compatible endpoints: HF router, `auth2api :8317`, ollama, lms, any models.dev `api` URL | zero tokens | 5, 6.3 |
| L4 | 1-output-token `chat/completions`; variants `tools=[noop]` and `response_format=json_schema` **only when the claim column says supported and the claim has never been observed** | OpenAI-compatible endpoints, one model per endpoint per run | 1 token each | llm-health-monitor (6.2), HF `supports_tools` (5) |
| L5 | `mcp-scan --local-only --json` over the client configs that `mcp-canonical-sync` writes | all MCP servers | CPU only; no network with `--local-only` | 7.1 |

**Cadence:** L0-L2 every `SessionStart` for servers tagged `shared`/`http` and for whatever the session's `capability-catalog` names (cheap, already half-done by `mcp-liveness`); L3 daily with the catalog sync; L4 weekly or on demand when the score's `claim_gap` is non-zero; L5 weekly and on any L2 `changed`. **Never** probe on every tool call - `mcp-liveness`'s 60 s throttle is the floor.

**Budget rule:** a probe run must finish inside `mcp.policy.startupTimeoutMs` (30 s) per endpoint and must respect `totalIdlePrivateBytes`; stdio servers are probed by *spawning* them, so the run is serialized and skipped when the box is memory-starved (the brief: 31.6 GB, chronically starved).

### 8.4 Capability score per endpoint

A 0-100 integer plus a state, stored per endpoint in a sidecar `capability-scores.json` (never in `agents.json`; the `_meta`-style reverse-DNS namespace `dev.prekzursil.ast/capability` is the label to use if the estate ever exports to a sub-registry, 7.2).

```
score = 40 * availability_30d          # fraction of L1/L3 probes that were `up` in the trailing 30 days
      + 20 * capability_match          # fraction of claimed capabilities (tools, structured, ctx>=needed, modalities) observed true in L4
      + 15 * latency_health            # 1.0 if p50 <= 1.5x own 30-day baseline; linear to 0 at >= 3x (llm-health-monitor's ratio idea)
      + 10 * freshness                 # 1.0 if last successful probe <= 24h; 0.5 <= 7d; 0 otherwise
      + 10 * security                  # 1.0 if L5 clean AND L2 hash unchanged since approval; 0.5 if changed-but-reviewed; 0 if open finding
      +  5 * claim_agreement           # 1.0 when vendor/catalog claim and our observation agree; 0 when they disagree (the gap flag)
```

Weights are a starting point (INFERENCE); the *inputs* are what matter and each maps to a probe rung above. Cost is deliberately **not** in the score - it is a routing preference, and folding it in would let a cheap dead endpoint outrank a pricey live one.

**States derived from score + events, with hysteresis:**

| State | Enter when | Leave when | Effect |
|---|---|---|---|
| `live` | default | - | listed in capability-catalog injection |
| `degraded` | score < 60 **or** `claim_agreement = 0` | score >= 70 for 2 consecutive daily runs | still listed, with a one-line caveat in the heartbeat banner |
| `quarantined` (session) | `mcp.supervision.failureThreshold` (3) failures inside `failureWindowSeconds` (600) - the existing contract | session end (`quarantineScope: session`) | not offered this session; `event-ledger` note written |
| `deprecation-candidate` | `quarantined` in >= 3 distinct sessions within 14 days, **or** upstream `expiration_date` set / registry entry deleted / host decommissioned (8.2 diff) | owner decision | opens a gem-hunt lens (8.5); nothing disabled yet |
| `retired` | owner approves after verify (8.5) | never automatically | `enabled: false`, tag `retired`, `.provenance/.agents/agents.json.md` gains the why + replacement id; entry is **kept** (`[LOCK-TRADEOFF]`: no silent feature removal, history preserved) |

### 8.5 The failure -> gem -> verify -> retire loop for hosted models

```
        PostToolUseFailure (existing hook: post:mcp-health-check)
                 |  writes {endpoint, error class, ts} to event-ledger  (existing ledger.py)
                 v
   [FAILURE]  supervision counter: 3 in 600s  -> quarantined(session)  (existing contract, enforcement TBV)
                 |  heartbeat banner names it at Stop/SessionStart      (existing heartbeat.py)
                 v
   catalog_sync daily run (8.2) + probe ladder (8.3) confirm across sessions/days
                 |  score falls, state -> deprecation-candidate; diff shows if upstream also deprecated
                 v
   [GEM]      gem-hunt lens opened with the dedup-set = everything still live in the index
                 |  candidates ranked with the section-7 rubric; models.dev/HF/OR index supplies the shortlist
                 v
   [VERIFY]   hosted-model-agents/evals.md run against the candidate (dedup-set item 1 owns this)
                 |  L4 probes must observe every claimed capability the retiring endpoint provided
                 |  ssot_drift_gate.py must pass first (loop runs from the executed checkout only)
                 v
   [RETIRE]   owner-approved, flagged write-back: enabled:false + tag retired + .provenance note
                 |  mcp-canonical-sync / mcp-defaults propagate to ~/.mcp.json and client configs (existing)
                 |  capability-catalog entry rewritten to name the replacement
                 v
              scores sidecar keeps the retired row for 90 days so a resurrection is measurable
```

Stop rules (per `AGENTS.md`): the loop never disables, deletes, rotates (`[LOCK-CREDS]`), or opens ports; every transition past `quarantined` is a proposal in the heartbeat banner + a ledger event until a human runs the write-back command.

### 8.6 Worked example: retiring `glm53-space` (the owner's stated decision)

- L0: entry is `enabled: true`, `hosted-inference`, needs `HUGGINGFACE_TOKEN`. L1/L2: it is stdio, so a probe spawns `uv run --locked ... mcp_server.py` (RAM cost) and hashes its single tool `glm53_chat`. L3 against `router.huggingface.co/v1/models` tells us whether `zai-org/GLM-5.3` still lists `status: live` providers and their `supports_tools` - the *upstream* half of the decision. The vendor feed for Zhipu does not exist (6.1), so L3/L4 are the only truth.
- State today (INFERENCE from the brief): `deprecation-candidate` by owner decision, not by failure. The loop still applies: the **gem** step is this gem-hunt; the **verify** step is `hosted-model-agents/evals.md` against the general integration layer; the **retire** step keeps the entry with `enabled:false` and a `.provenance` note pointing at the replacement.
- What the replacement should *not* be: another single-tool relay (W2 pattern). What it should be: one MCP server (or one skill + CLI) that reads `state/catalog/index.json` and exposes `list_endpoints`, `chat(endpoint_id, ...)`, `probe(endpoint_id)`; the model id and base URL come from the index, the secret comes by name from `.agents/local.json`. That is the "general integration layer" the owner asked for, and it is what makes the score self-feeding: every real `chat` call is an L4 observation for free.

### 8.7 Tradeoffs presented, not decided (`[LOCK-TRADEOFF]`)

| Choice | Option A | Option B | What you give up |
|---|---|---|---|
| Where the score lives | sidecar JSON in state root | `_meta`-style block inside `agents.json` | B breaks the closed-schema rule and churns a file 42 consumers read; A needs a second file to open |
| L4 token spend | weekly, one model per endpoint | never (L3 only) | B never verifies `supports_tools` claims; HF router already publishes them, so B is acceptable for HF but not for `auth2api`/ollama |
| Probing stdio servers | spawn each weekly | rely on L2 at SessionStart only | A costs RAM on a starved box; B misses servers no session opened |
| mcp-scan mode | `--local-only` | cloud Guardrails | B is more accurate but ships 42 servers' tool descriptions off-box |
| Deprecation authority | human approves every retire | auto-retire after N days | B is simpler; violates the spirit of `[LOCK-TRADEOFF]` and can retire a paused-but-wanted endpoint |

### 8.8 Verify-before-trust list (things this lens could not confirm from the repo)

1. Whether anything on the Windows box enforces `mcp.supervision` today (no in-repo consumer, 2.1). If nothing does, 8.5's `[FAILURE]` stage is a hook+ledger write only until the supervisor exists.
2. What `post:mcp-health-check` (`hooks/hooks.json`, `PostToolUseFailure`) actually does - its script is referenced via `${CLAUDE_PLUGIN_ROOT}/scripts/hooks/...`, i.e. it lives in the installed plugin, not this repo.
3. `mcp_doctor.py` / `lib.mcp_doctor_core` lives off-repo at `~/.local/opt/re-harness/` (2.2b). Confirm on the box whether it already walks all 42 registry servers (L1) and whether it does `tools/list` (L2); if yes, the probe script is a thin wrapper plus the hash pin, and `tools/re-harness/mcp_doc_drift.py` already covers the "documented but not mounted" half of L0.
5. Whether `tools/mcp-manager` presets are the right retire write-back (2.2b) or whether the owner prefers `enabled:false` in `agents.json` propagated by `mcp-canonical-sync`; the two are not exclusive but one must be the source.
4. Licences and commit cadence of W4 (`llm-health-monitor`) and W3's repo before any code is copied rather than re-derived.

## 9. Rubric table

Columns per the brief. `value x effort` is 1-5 for each (5 = high value / 5 = high effort) written as `V/E`. `novelty-for-us` = new to this estate (checked against the dedup set and section 2). `NATIVE-vs-BUILD`: NATIVE = adopt the thing; BUILD = write estate code inspired by it; READ = consume as a feed only.

| # | name | what | why THIS estate | how to build or adopt | source | value x effort | novelty-for-us | NATIVE-vs-BUILD |
|---|---|---|---|---|---|---|---|---|
| W1 | `huggingface/hf-mcp-server` Server Card + `PROXY_TOOLS_CSV` | Official HF MCP; remote card at `/mcp/server-card` with ETag; CSV-driven extra tools | We already run HF Hub MCP as doctrine; the *card+ETag* is a free L1 probe for remote MCPs and the CSV pattern is precedent for a data-driven tool list | Add `GET /mcp/server-card` + ETag compare to the L1 rung for `remote` servers that publish one | `[TA corroborated 2026-09-02] https://github.com/huggingface/hf-mcp-server` | 3/1 | medium (server known; probe pattern new) | NATIVE (server) + BUILD (probe rung) |
| W2 | `pyroprompts/any-chat-completions-mcp` | One-tool env-configured OpenAI-compatible relay, MIT, last seen updated 2025-07 | It is `glm53-space` generalised by env vars - proves the pattern's ceiling; the owner's replacement must be registry-driven instead | Do **not** adopt; reuse its tool schema/env contract as the reference when writing the registry-driven layer (8.6) | `[TA corroborated 2026-09-02] https://github.com/pyroprompts/any-chat-completions-mcp` | 2/1 | low | neither (negative example) |
| W3 | `openrouterteam/skills` `openrouter-models` | Vendor skill documenting keyless `GET /api/v1/models`, `expiration_date`, `supported_parameters`, 30-min health fields | Deprecation + capability + health for the sidecar's OpenRouter models without any key or MCP - inside `[LOCK-OR]` | Feed row in `catalog_sync.py` (8.2); never wire as MCP/BYOK; cite `openrouter.ai/docs`, not the unlicensed SKILL.md | `[TA corroborated 2026-09-02] https://openrouter.ai/docs/guides/overview/models` (skill repo has no licence file) | 3/1 | medium | READ |
| W4 | `yejinai/llm-health-monitor` design | 1-token probes + simultaneous Statuspage read; claim-vs-reality gap as a signal; `confirmationRuns`, `degradedLatencyRatio` | Gives the estate the *shape* of L4 and the `claim_agreement` / `latency_health` score inputs; a resident monitor itself is wrong for a starved box | Re-derive as functions inside the probe script; do not run the service | `[TA corroborated 2026-09-02] https://github.com/yejinai/llm-health-monitor` (MIT; 0 stars) | 4/2 | high | BUILD |
| W5 | `mcp-scan` / `snyk/agent-scan` `--local-only` | Apache-2.0 CLI scanning MCP configs + skills for injection/poisoning/rug-pull via tool-description hashes | Security gate for 42 servers **and** the L2 drift hash for free; CLI, so no second runtime | Weekly Scheduled Task + on any L2 `changed`; `--json` into the ledger | `[TA corroborated 2026-09-02] https://github.com/invariantlabs-ai/mcp-scan/blob/608b50b0/README.md` | 4/1 | high | NATIVE |
| W6 | Official MCP Registry `updated_since` sync | `GET /v0.1/servers?updated_since=&version=latest` with deletions included; `server.json` 2025-12-11; `_meta` namespace | Upstream deletions/version moves for the public subset of the 42 become deprecation-candidate signals automatically | Feed row (8.2); cross-reference by npm/pypi identifier | `[TA corroborated 2026-09-02] https://modelcontextprotocol.io/registry/registry-aggregators` | 3/1 | high | READ |
| W7 | models.dev `api.json` as spine | Keyless provider table with OpenAI-compatible `api` URL + `env` var names; opencode consumes it via `OPENCODE_MODELS_PATH` | The general integration layer needs exactly base-URL + env-name per provider; also lets installed opencode share the synced copy | Feed row (8.2); point opencode at the synced file | `[TA corroborated 2026-09-02] https://github.com/anomalyco/models.dev/` | 4/1 | medium | READ |
| W8 | HF router `/v1/models` per-provider capability flags | `providers[].status/supports_tools/supports_structured_output/latency/throughput/price` | The only truth source for GLM/Zhipu-backed models (no vendor status feed); feeds `capability_match` directly | Feed row (8.2) using the existing HF token by name | `[TA corroborated 2026-09-02] https://huggingface.co/docs/inference-providers/hub-api` | 4/1 | medium | READ |
| M1 | Probe ladder L0-L5 riding `mcp-liveness` | Cost-ordered re-probe: static -> initialize -> tools/list hash -> /v1/models -> 1-token -> mcp-scan | Extends an existing keystone hook instead of adding a daemon; respects `startupTimeoutMs`, `totalIdlePrivateBytes` | Extend `hooks/mcp-liveness` with an `all` mode + a daily task; ~200 lines stdlib | 2.2, 8.3 | 5/2 | high | BUILD |
| M2 | Capability score sidecar + states | 0-100 score, `live/degraded/quarantined/deprecation-candidate/retired` with hysteresis from `mcp.supervision` | Turns the registry's dormant supervisor contract into something visible via heartbeat + capability-catalog | Sidecar JSON; generated block into `capability-catalog/catalog.json`; `.provenance` on retire | 2.1, 8.4 | 5/2 | high | BUILD |
| M3 | `catalog_sync.py` Scheduled Task | Daily ETag-cached pull of 6-7 feeds, normalised index, diff as product | Registry `lastSync` is 11 weeks stale; sync-on-start + last-known-good is the OpenClaw/opencode precedent | Third task in `register-tasks.ps1` style; stdlib only | 2.3, 5, 8.2 | 4/2 | high | BUILD |
| M4 | Registry-driven hosted-model MCP (glm53-space successor) | One server: `list_endpoints`, `chat(endpoint_id)`, `probe(endpoint_id)` reading the synced index; secrets by name | The owner's stated replacement; makes every real call an L4 observation | New `tools/mcp/hosted-models/`; schema borrowed from W2; evals from `hosted-model-agents` | 8.6, 4.1 | 5/3 | medium (owner already decided the *what*) | BUILD |

## 10. Ten-line summary

1. Nothing in the wild does catalog sync + capability probing + registry write-back together; every OSS find covers one leg, so the meta loop is a small BUILD, not an adoption.
2. The registry already declares the supervisor: `mcp.policy.healthProbe = tools/list` and `mcp.supervision` (3 failures / 600 s -> session quarantine, 6 GiB idle budget) - but no code in this repo consumes them (verify off-repo).
3. `hooks/mcp-liveness` already implements the right liveness definition (JSON-RPC `initialize` + `capabilities.tools`, fail-open, throttled); the probe ladder extends it rather than replacing it.
4. Three keyless-or-existing-key catalogs are enough: models.dev `api.json` (base URLs + env names), OpenRouter `/api/v1/models` (deprecations + 30-min health; read-only keeps `[LOCK-OR]`), HF router `/v1/models` (per-provider `status`/`supports_tools`; the only truth for GLM/Zhipu, which has no status feed).
5. The official MCP Registry's `updated_since` (deletions included) turns upstream retirements of public servers into deprecation-candidate signals for free.
6. `mcp-scan --local-only` (Apache-2.0, Snyk-maintained) is both the security gate and the L2 drift hash; run weekly as a CLI, never as a runtime.
7. `pyroprompts/any-chat-completions-mcp` is `glm53-space` with env vars; its ceiling (one process per model, no catalog/health) is the argument for a registry-driven successor exposing `list_endpoints / chat / probe`.
8. Capability score = availability, capability-match, latency-vs-own-baseline, freshness, security, claim-agreement; cost deliberately excluded; stored in a sidecar, never in `agents.json` (closed-schema rule).
9. Failure -> gem -> verify -> retire rides `PostToolUseFailure` + `event-ledger` -> supervision quarantine -> daily sync confirms -> gem-hunt lens -> `hosted-model-agents/evals.md` -> owner-approved `enabled:false` + `.provenance` note; entries are kept, never deleted.
10. Scheduling reuses the `register-tasks.ps1` Windows Scheduled Task pattern (mutex + IgnoreNew); no daemon, no LiteLLM/LangGraph, no new ports, no credential rotation, no OpenRouter MCP.
