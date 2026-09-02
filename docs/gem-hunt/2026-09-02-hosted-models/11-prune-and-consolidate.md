# Gem-hunt 2026-09-02 / hosted models / lens 11: prune and consolidate

Status: IN PROGRESS (sections land in separate commits; each is pushed as soon as it is
written because runs on this platform have died near the 12-minute mark).
Lens: inventory the overlapping model-access wrappers and lanes in this estate and propose
the leanest end state that preserves every capability (no feature removed to buy simplicity).
Discipline: discovery only, no code changed. Every claim carries a URL, a source tier
(A = vendor/primary docs or this repository's own files; B = maintained project README,
changelog or issue tracker; C = blog, forum or other secondary), a corroboration flag
(corroborated / UNVERIFIED) and an access date (all accessed 2026-09-02 unless stated).
Each line is labelled FACT (sourced), INFERENCE (derived from facts) or RECOMMENDATION.

Repo citations use `main@5fa34fda1` (the merge-base of this branch) and the snapshot
branch `live-capture/2026-09-02@726687ecf`. GitHub URLs:
`https://github.com/Prekzursil/agent-skills-toolchain/blob/<ref>/<path>`.

## 1. Estate locks restated as constraints (never proposed against)

| Lock | Text as used in this lens | Source | Tier |
|---|---|---|---|
| L1 OpenRouter | Spend-capped CLI/Codex sidecar only. Never a Cursor BYOK key, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP. | task brief; `.agents/skills/openrouter-routing/SKILL.md` lines 3, 21-27, 62 on main ("NEVER Cursor BYOK or Claude ANTHROPIC_BASE_URL"; "Do not put the OpenRouter secret into Cursor"; "Leave Claude on native Max") | A, corroborated |
| L2 No second runtime | No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory. | task brief; corroborated by `COUNCIL-PREMIUM-GPT56_2026-08-28.md` line 89 on live-capture ("no second orchestrator, new daemon, vector DB") | A, corroborated |
| L3 auth2api | `127.0.0.1:8317` stays the ONLY Cursor-quota OpenAI-compatible bridge and retires within 7 days of an official Cursor `/v1` GA. | task brief; G-32 in `skills/hosted-model-agents/SKILL.md` on live-capture ("`ai-mode` / `*-cursor` stay process-local to auth2api `:8317`; no persistent global Cursor-bridge env") | A, corroborated |
| L4 Owned ports | 8765 (basic-memory), 8812 (agent-mail), 8317 (auth2api) are owned; nothing else binds them. | `memory-contract.md` line 77 and `browser-bridge/SKILL.md` line 40 on live-capture ("Do not use ports 8765, 8812, 8317, 24680, 8787") | A, corroborated |
| L5 Prompt SSOT | `.agents/skills` is the ONE prompt SSOT; Fabric and Goose consume it. | task brief; `memory-map.md` on live-capture ("Skills SSOT `C:\Users\Prekzursil\.agents\skills`"); `AGENTS.md` on main ("`.agents/skills/` is the canonical repo-published skill root") | A, corroborated |
| L6 Credentials | Never rotate credentials; secrets by name only in `.agents/local.json`. | task brief; `.agents/agents.json` server entries carry `credentialNames` only (e.g. `glm53-space.credentialNames = ["HUGGINGFACE_TOKEN"]`) | A, corroborated |
| L7 No feature-for-reliability trades | Never remove a feature to buy reliability; present tradeoffs. | task brief | A (brief) |
| G-36 | At most one `cursor-agent` process (RAM). Not the same axis as IDE Tasks. | `skills/hosted-model-agents/SKILL.md` hard rule 5 and `COUNCIL-ORCH-RELIABILITY_2026-08-28.md` lines 43, 80, 341 on live-capture ("Do not relax.") | A, corroborated |
| G-4 | RAM target 8 GB free; measured free was ~1.8 GB on 2026-08-28. | `COUNCIL-PREMIUM-GROK_2026-08-28.md` line 59 on live-capture | A, single source (a council note, not a live probe) |
| SSOT-WIRE | The GitHub remote is the SSOT for history; `~/source/ast-integrate` is the only edited checkout, `~/source/agent-skills-toolchain` the only executed one. | `CLAUDE.md` on main, SSOT-WIRE block | A, corroborated |

INFERENCE: the combination of L3 + G-36 + G-4 means every consolidation below must be judged
by resident memory when idle, not only by file count. A wrapper that is a shell script costs
~0 MB idle; a wrapper that is a daemon costs its RSS forever.

## 2. Inventory of the overlapping lanes (repo evidence)

Legend: **kind** = daemon (resident process), stdio-MCP (spawned per host session, resident
while the host runs), shell wrapper (exits with the CLI), config block (0 MB), skill (0 MB).

| # | Lane | Kind | What it does | Where it lives (evidence) | Tier |
|---|---|---|---|---|---|
| I1 | `auth2api` `127.0.0.1:8317` | daemon | The only Cursor-quota OpenAI-compatible bridge; 36 model ids (`cursor-claude-fable-5-1`, `cursor-grok-4.6`, ...). | task brief; port ownership in `memory-contract.md` line 77 (live-capture); sessions under `Cowork\tools\auth2api` in `session-catalog.md` lines 45-47, 1029-1032 (live-capture). Source tree NOT in this repository on any ref. | A for existence, UNVERIFIED for the 36-id count (brief only) |
| I2 | `tools/mcp/glm53-space` (`glm53_core.py`, `mcp_server.py` -> tool `glm53_chat`, `openai_proxy.py`) | stdio-MCP (+ optional mini HTTP proxy) | One text-only chat tool hard-wired to `router.huggingface.co/v1`, model `zai-org/GLM-5.3`. Owner has decided to DEPRECATE. | Registry entry `.agents/agents.json` -> `mcp.servers.glm53-space` on main (`uv run --locked --directory C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\glm53-space python mcp_server.py`, `targets: ["claude"]`, tags `owner-requested`, `hosted-inference`). **Measured 2026-09-02: the directory `tools/mcp/glm53-space` is present on NONE of the 55 remote refs** (`git fetch origin '+refs/heads/*:refs/remotes/origin/*'` then `git ls-tree -d <ref> -- tools/mcp/glm53-space` over every ref). It exists only in the local Windows executed checkout the registry path names. | A (registry, merge script, tests); the code itself is UNVERIFIED from here |
| I2a | glm53-space attach wiring | config | `CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS = CURSOR_DEFAULT_APPROVED_SERVERS | {"glm53-space"}` - the default Cursor merge attaches the core six plus this one adapter; a live test pins it. | `.agents/scripts/merge_generated_cursor_mcp.py` line 143 (main); `.agents/tests/test_mcp_control_plane_live.py` lines 216, 660 (main); `.provenance/.agents/agents.json.md` lines 46-49 (main); `reconcile-flags/mcp-cursor-merge-lineage-2026-09-02.md` lines 84, 182 (main) | A, corroborated (4 files) |
| I3 | `huggingface` Hub MCP | remote HTTP MCP | Control plane for HF (models, datasets, Spaces, papers). Explicitly NOT an inference runtime. | `.agents/agents.json` -> `mcp.servers.huggingface` (`https://huggingface.co/mcp?login`, `targets: ["claude"]`, description "Do not register a raw inference URL as a second Hub MCP") | A |
| I4 | skill `hosted-model-agents` | skill | Current doctrine: environment x runtime x harness; "an inference URL is not Hub MCP"; "personas are prompt packs". | `skills/hosted-model-agents/{SKILL,environments,profiles,tool-loop,evals}.md`, `recipes/hf-space-openai.md` on live-capture (`valid_as_of: 2026-08-29`) | A |
| I5 | skill `qwen-space-tool-api` (deprecated pointer) | skill (tombstone) | "DEPRECATED. Use hosted-model-agents instead." Keeps the Space wire contract in `reference.md`. The `qwen-space` wrapper in `~/.local/bin` is the matching deprecated pointer. | `skills/qwen-space-tool-api/SKILL.md` (live-capture, `status: deprecated`); `reference.md` line 93 ("`POST /v1/chat/completions` ... **Yes, via process-local `qwen-space`**"); `memory-map.md` line 21 ("Deprecated name: `qwen-space-tool-api`") | A |
| I6 | `ai-mode` (alias `grok-mode`) | shell wrapper / switch | "which backend each CLI is on"; "Native CLIs stay on grok.com / Anthropic / OpenAI; Cursor quota is opt-in." Implemented 2026-08-26. | `session-catalog.md` line 876 (live-capture): "`ai-mode` is on PATH (alias `grok-mode`) ... `ai-mode status`"; hosted-model-agents hard rule 5 names `ai-mode` under G-32 | A for existence; internals UNVERIFIED (script bodies not in repo) |
| I7 | `fabric-cursor`, `claude-cursor`, `codex-cursor` | shell wrappers | Per-CLI launchers that point one CLI at auth2api for one process. | task brief; G-32 "`*-cursor` stay process-local to auth2api `:8317`" (hosted-model-agents SKILL.md, live-capture) | A for the rule; script bodies UNVERIFIED |
| I8 | `claude-swap` | shell wrapper | Named in the brief as an installed wrapper; purpose not evidenced in the repository. | task brief only | UNVERIFIED |
| I9 | Goose provider `goose-cursor-proxy` (`GOOSE_PROVIDER`) | config block | Goose 1.47 pointed at auth2api as a custom provider. | task brief; Goose CLI 1.47.0 (`goose.exe`, 265 MB) measured in `session-catalog.md` line 872 (live-capture) | A for Goose version; provider name UNVERIFIED from repo |
| I10 | Grok CLI `config.toml` `[model."cursor-grok-4.6"]` blocks | config block | Grok CLI model aliases that route to auth2api model ids. | task brief; Grok sessions rooted at `Cowork\tools\auth2api` in `session-catalog.md` lines 1029-1032 (live-capture) show the config was built there | A for sessions; block contents UNVERIFIED |
| I11 | Fabric vendors | config | Fabric 1.4.470 vendor list (which providers are configured). Fabric consumes `.agents/skills` as patterns (L5). | task brief | UNVERIFIED from repo |
| I12 | Local runtimes: `ollama`, `lms` (LM Studio) | daemons (on demand) | Local weights. Weights already moved off the pressured drive: `OLLAMA_MODELS=D:\ai-models\ollama`, LM Studio `downloadsFolder=D:\ai-models\lmstudio`. | `local-models-audit_2026-08-27.md` lines 40, 48 (live-capture) | A |
| I13 | `claude-code-mcp`, `ralph-orchestrator` MCP | stdio-MCP | Not model-access lanes, but they are the two other "an agent as a tool" servers in the registry and set the precedent this lens follows (one MCP per *runtime*, not per *model*). | `.agents/agents.json` on main | A |

Registry shape (FACT, `.agents/agents.json` on main): 42 servers; `mcp.policy.maxPrivateBytes
= 536870912` (512 MiB per server), `mcp.supervision.totalIdlePrivateBytes = 6442450944`
(6 GiB idle budget for the whole fleet), `duplicatePolicy = report-unless-exact-process-tree`.
INFERENCE: the registry already contains the RAM vocabulary this lens needs; a consolidation
that adds a server must fit under 512 MiB and inside the 6 GiB idle envelope, and the
duplicate policy already flags the failure mode "two adapters for the same upstream".

Overlap map (INFERENCE from I1-I12):

- **Three ways to reach one upstream (HF router).** I2 (`glm53-space` MCP tool), I2's own
  `openai_proxy.py`, and any `hosted-model-agents` recipe all terminate at
  `router.huggingface.co/v1`. Two of the three are code; one is doctrine.
- **Four ways to reach one upstream (auth2api).** I6 `ai-mode`, I7 `*-cursor` wrappers,
  I9 Goose provider, I10 Grok model blocks all terminate at `127.0.0.1:8317` with different
  per-CLI syntax. They are not redundant with each other (each CLI needs its own dialect) but
  they are four hand-maintained copies of the same base-URL + model-id table.
- **Two names for one deprecated thing.** I5 skill `qwen-space-tool-api` and the `qwen-space`
  wrapper are both tombstones pointing at I4.
- **One orphaned registration.** I2a: the registry, the merge script and a live test all pin
  an adapter whose source is not on the SSOT remote (SSOT-WIRE lock). This is the single
  highest-value prune because it is already half-gone.

## 3. Capability matrix: what each lane uniquely provides, and how each consumer already speaks "custom endpoint"

The consolidation question is not "which lane to delete" but "which CLI dialect each lane
is the only speaker of". Vendor docs for every consumer (all Tier A unless marked):

| Consumer | Native custom-endpoint mechanism (FACT) | Wire protocol it needs | Source |
|---|---|---|---|
| Goose 1.47 | Declarative provider JSON in `~/.config/goose/custom_providers/<name>.json` with `engine: "openai"`, `base_url`, `api_key_env`, `models[]`; selected by `GOOSE_PROVIDER=<name>` or `goose configure`. Alternative: built-in `openai` provider + `OPENAI_HOST` (host only; Goose appends `/v1/chat/completions`). | Chat Completions | https://block-goose.mintlify.app/api/providers/custom ; https://block-goose.mintlify.app/concepts/providers ; https://github.com/block/goose/blob/main/documentation/docs/getting-started/providers.md (A, corroborated by 3 pages) |
| Grok CLI (xAI Grok Build) | `~/.grok/config.toml` `[model."<alias>"]` with `model`, `base_url`, `env_key`, `api_backend` in `chat_completions | responses | messages`; **`[endpoints] models_base_url` / `GROK_MODELS_BASE_URL` pulls the whole model list from `{base_url}/models` and partial `[model.*]` overrides inherit that `base_url`**; five-layer config with `requirements.toml` as a fail-closed pin. | Chat Completions, Responses or Anthropic Messages (per model) | https://docs.x.ai/build/settings/reference ; https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/11-custom-models.md ; https://docs.x.ai/build/enterprise (A, corroborated) |
| Fabric 1.4.470 | Fixed vendor list, each with `<VENDOR>_API_BASE_URL` / `<VENDOR>_API_KEY` in `~/.config/fabric/.env` (e.g. `OPENAI_API_BASE_URL`, `GROQ_API_BASE_URL`); `-V/--vendor` selects; per-pattern `FABRIC_MODEL_<PATTERN>=vendor|model`; "LM Studio", "GrokAI", "OpenRouter", "LiteLLM" are pre-named OpenAI-compatible vendors. | Chat Completions | https://github.com/danielmiessler/Fabric/blob/main/README.md (B) ; https://github.com/danielmiessler/Fabric/issues/883 (B, closed "already available") |
| Codex CLI | `~/.codex/config.toml` `[model_providers.<id>]` with `base_url`, `env_key`; **`wire_api = "chat"` was removed in February 2026 - `responses` is the only value and a leftover `chat` entry hard-fails config load**; built-in `ollama` and `lmstudio` providers are defined with `WireApi::Responses`. | **Responses API only** | https://github.com/openai/codex/blob/main/codex-rs/model-provider-info/src/lib.rs lines 64, 94, 540-544 (A) ; https://github.com/openai/codex/issues/41816 (B) ; https://github.com/openai/codex/discussions/7782 (B, cited by both) |
| Cursor (as *upstream*) | Official Cursor APIs are the Cloud Agents API (`POST /v1/agents`, `GET /v1/models` for *agent* model ids) and "are not a standalone model-inference or chat-completions API". A forum feature request for `POST /v1/chat/completions` is open. | n/a (no official chat endpoint) | https://cursor.com/docs/api ; https://cursor.com/docs/cloud-agent/api/endpoints (A) ; https://forum.cursor.com/t/openai-compatible-v1-chat-completions-for-cloud-api/164522 (C) |

FACT (Tier A, cursor.com/docs/api, accessed 2026-09-02): no official Cursor `/v1/chat/completions`
exists. INFERENCE: the L3 retirement trigger ("within 7 days of an official Cursor /v1 GA") has
NOT fired; auth2api remains the only sanctioned Cursor bridge and every consolidation below
keeps it as the single upstream for Cursor quota.

INFERENCE (load-bearing for Section 4): the four auth2api consumers are not interchangeable
because their wire protocols differ. Goose and Fabric need Chat Completions; Codex needs
Responses; Grok can do either per model; Claude Code needs Anthropic Messages. A bridge that
only speaks Chat Completions cannot serve `codex-cursor` at all after February 2026. Whether
auth2api serves `/v1/responses` and `/v1/messages` today is UNVERIFIED from this checkout
(its source is not in the repository); it is the first thing the migration must probe.

Unique capabilities that must survive (RECOMMENDATION = keep each row):

| Capability | Only provider today | Survives as |
|---|---|---|
| C1 Reach Cursor quota from any OpenAI-speaking CLI | auth2api :8317 (I1) | unchanged (L3) |
| C2 Per-process opt-in to Cursor quota for one CLI run | `*-cursor` wrappers (I7) | one wrapper family (Section 4) |
| C3 See / switch which backend each CLI is on | `ai-mode` / `ai-mode status` (I6) | the same wrapper family's `status` verb |
| C4 Goose on Cursor quota | `goose-cursor-proxy` provider JSON (I9) | unchanged: it is already a registry-style entry (0 MB idle) |
| C5 Grok CLI on Cursor quota | `[model."cursor-*"]` blocks (I10) | one `[endpoints]` block + zero-or-few overrides |
| C6 Fabric patterns on Cursor quota | `fabric-cursor` (I7) | wrapper family + `.env` vendor slot |
| C7 Chat with GLM-5.3 on the HF router from Claude as a tool | `glm53-space` MCP tool (I2) | generalised: one hosted-inference MCP whose *model* is a parameter (Section 4, F2) |
| C8 Mini OpenAI proxy in front of HF router | `openai_proxy.py` (I2) | redundant with the router itself (the router *is* OpenAI-compatible); becomes a documented recipe, not code |
| C9 HF Hub control plane | `huggingface` Hub MCP (I3) | unchanged |
| C10 Space wire contract for the Qwen recipe | `qwen-space-tool-api/reference.md` (I5) | folded into `hosted-model-agents/recipes/`; skill folder becomes a redirect tombstone (it already is) |
| C11 Local weights | ollama, lms (I12) | unchanged; both already expose OpenAI-compatible `/v1` (Codex's built-ins target them with the Responses API) |

## 4. Leanest end state that preserves every capability

Principle (INFERENCE from Sections 2-3): there are exactly three *kinds* of thing in this
estate's model-access layer - **an upstream** (auth2api, HF router, Ollama/LM Studio, a
Space), **a consumer dialect** (how each CLI is told about an upstream) and **a persona**
(system prompt + tool list, already declared a prompt pack by `hosted-model-agents`). Today
each upstream x consumer pair is hand-written. The lean end state writes each upstream once
and generates each dialect from it.

### 4.1 What becomes a registry entry

RECOMMENDATION R1: add an **`upstreams`** table to the ONE registry (`.agents/agents.json`,
schema is owner-controlled; per `AGENTS.md` "treat consumer-owned manifests as closed schemas"
so this goes in the *owner-owned* registry, not in any CLI's file). Each entry: `id`,
`base_url`, `protocols: ["chat_completions","responses","messages"]`, `credentialName`
(name only, L6), `models` (static list or `"discover": "/v1/models"`), `ramClass`
(`remote` | `loopback-daemon` | `on-demand-local`). Seed rows:

| id | base_url | protocols (UNVERIFIED until probed) | credential | ramClass |
|---|---|---|---|---|
| `cursor-auth2api` | `http://127.0.0.1:8317/v1` | chat_completions (+responses? +messages?) | none (loopback) | loopback-daemon (already resident; L3) |
| `hf-router` | `https://router.huggingface.co/v1` | chat_completions | `HUGGINGFACE_TOKEN` (name already in registry) | remote |
| `ollama` | `http://127.0.0.1:11434/v1` | chat_completions, responses (Codex built-in uses Responses) | none | on-demand-local |
| `lmstudio` | `http://127.0.0.1:1234/v1` | chat_completions, responses (Codex built-in uses Responses) | none | on-demand-local |
| `openrouter` | `https://openrouter.ai/api/v1` | chat_completions | `OPENROUTER_API_KEY` | remote; **flag `sidecarOnly: true`** so generators refuse to emit it for Cursor/Claude (L1) |

Why registry and not a new daemon: 0 MB idle, versioned on the SSOT remote, already
validated by the existing control-plane tests (`.agents/tests/test_mcp_control_plane*.py`),
and the registry already carries the RAM vocabulary (`maxPrivateBytes`,
`totalIdlePrivateBytes`). L2 forbids LiteLLM precisely because it would be a *resident*
translation layer; a registry table is data.

RECOMMENDATION R2 (replaces `glm53-space`, honours the owner's deprecation decision): one
generalised stdio MCP **`hosted-inference`** with one tool `chat(upstream, model, user_prompt,
system_prompt="")` where `upstream` is validated against the registry's `upstreams` table and
`model` against that upstream's list. It is the same shape as `glm53_chat` (separate
`user_prompt` and blank-default `system_prompt`, text only, "never send secrets or raw private
transcripts") with two parameters lifted out of the hard-coded constants. It inherits
`glm53-space`'s registry slot (`targets: ["claude"]`, `owner-requested`, `hosted-inference`
tag, `credentialNames: ["HUGGINGFACE_TOKEN"]`) and its place in
`CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS`, so the Cursor surface stays at "core six + one". This
is NATIVE-vs-BUILD = BUILD (small), but it is a *replacement*, not an addition: the server
count stays 42.

### 4.2 What becomes one wrapper family

RECOMMENDATION R3: `ai-mode`, `grok-mode`, `fabric-cursor`, `claude-cursor`, `codex-cursor`
(and `claude-swap` if it is a backend switch - UNVERIFIED) become **one generated family**
`<cli>-on-<upstream>` (e.g. `codex-on-cursor`, `fabric-on-hf-router`, `goose-on-ollama`) plus
the single switchboard `ai-mode status|use <cli> <upstream>|native <cli>`. Each generated
wrapper is a shell script that sets *only* the process-local variables that CLI's vendor docs
name (Section 3), then `exec`s the CLI:

| CLI | Variables / flags the wrapper sets per process | Source |
|---|---|---|
| goose | `GOOSE_PROVIDER=<upstream-id>` (declarative provider JSON generated from the registry row into `~/.config/goose/custom_providers/<upstream-id>.json`) | Goose custom providers (A) |
| grok | `-m <alias>` where `[endpoints] models_base_url` is generated once and `[model."<alias>"]` overrides only where needed; or `GROK_MODELS_BASE_URL=<base_url>` per process | docs.x.ai settings reference (A) |
| fabric | `-V <vendor>` with the vendor's `<VENDOR>_API_BASE_URL` exported per process (Fabric has a fixed vendor set; reuse an OpenAI-compatible slot such as "LM Studio" or the OpenAI slot, per process) | Fabric README (B) |
| codex | `-c model_provider=<upstream-id>` with `[model_providers.<upstream-id>]` generated (Responses API only; the generator MUST refuse to emit a Codex provider for an upstream whose `protocols` lacks `responses`) | openai/codex lib.rs (A) |
| claude | `ANTHROPIC_BASE_URL=<base_url>` per process only for upstreams whose `protocols` include `messages`; never OpenRouter (L1) | L1 text; Claude Code env var usage UNVERIFIED for auth2api specifically |
| aider / opencode / gemini | out of scope for the auth2api family until probed; aider and opencode accept OpenAI-compatible bases natively (UNVERIFIED here); Gemini CLI targets Gemini/Vertex only (UNVERIFIED) | - |

The existing names stay as **aliases** (symlinks or one-line shims) so every muscle-memory
command still works (L7). The switchboard keeps the current opt-in stance ("Native CLIs stay
on grok.com / Anthropic / OpenAI; Cursor quota is opt-in" - session-catalog line 876) and G-32
(process-local, no global bridge env) by construction: the generated scripts never write to
the user profile.

### 4.3 What is a redirect tombstone (kept, not deleted)

- `qwen-space-tool-api` skill: already a tombstone (`status: deprecated`); keep as is, but move
  `reference.md` (the Space wire contract) under `hosted-model-agents/recipes/` and leave a
  one-line pointer. `qwen-space` wrapper: already a pointer; leave it.
- `glm53-space` registry name: keep the *name* as a disabled entry with `description:
  "DEPRECATED -> hosted-inference (upstream=hf-router, model=zai-org/GLM-5.3)"` for one
  release, because the Cursor approval store keys on `<server-name>-<16 hex>` ids
  (`CURSOR_APPROVAL_ID_RE`, merge script line 148) and a silent rename would look like an
  unapproved new server.
- `grok-mode`: alias of `ai-mode` today; stays an alias.

### 4.4 What is deleted

- `tools/mcp/glm53-space/openai_proxy.py`: the HF router is already OpenAI-compatible, so a
  loopback OpenAI proxy in front of it adds a process (RAM) and a hop (latency) and no
  capability. Its one arguable capability - hiding the token from a CLI that cannot read env -
  is already covered by every consumer in Section 3 supporting `env_key`/`api_key_env`.
- `tools/mcp/glm53-space/{glm53_core.py,mcp_server.py}` and the `uv.lock`: deleted from the
  executed checkout **after** R2 is green; note they are absent from the SSOT remote already
  (Section 2, I2), so on GitHub this is a no-op.
- The 35 duplicate `[model."cursor-*"]` blocks in `~/.grok/config.toml` once `[endpoints]`
  discovery is verified against auth2api's `/v1/models` (keep the blocks for models that need
  per-model `api_backend`/`context_window` overrides).

Nothing else is deleted. Every current command keeps working via alias.
