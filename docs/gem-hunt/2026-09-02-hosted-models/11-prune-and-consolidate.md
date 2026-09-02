# Gem-hunt 2026-09-02 / hosted models / lens 11: prune and consolidate

Status: COMPLETE 2026-09-02 (sections landed in separate commits; each was pushed as soon as it was
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

## 5. RAM and latency argument per consolidation

Box facts (FACT unless marked): 31.6 GB RAM (brief); G-4 target 8 GB free, measured ~1.8 GB
free on 2026-08-28 (`COUNCIL-PREMIUM-GROK_2026-08-28.md` line 59, live-capture); browsers alone
held Chrome ~1.05 GB / Edge ~1.65 GB / Node ~578 MB across 42 processes at one snapshot
(`session-catalog.md` line 870, live-capture); registry caps one MCP server at 512 MiB private
and the idle fleet at 6 GiB (`.agents/agents.json` on main). Goose binary is 265 MB on disk
(`session-catalog.md` line 872) - disk, not RSS, but a proxy for a heavy Rust/Electron client.

| Consolidation | Idle RAM before -> after | Latency before -> after | Reasoning (INFERENCE) |
|---|---|---|---|
| R1 `upstreams` registry table | 0 -> 0 | n/a | Pure data. The only cost is at generation time (a Python script that already exists in spirit: `merge_generated_cursor_mcp.py` renders Cursor's `mcp.json` from the same registry). |
| R2 `glm53-space` -> `hosted-inference` | one `uv run` Python stdio server (~40-80 MB RSS typical for a Python MCP process; UNVERIFIED on this box) -> the same one process. **No change in count**, but it stops growing: each new hosted model would otherwise have been *another* stdio server under the 512 MiB cap and inside the 6 GiB idle budget. | one stdio hop + one HTTPS call -> identical | Cursor keeps "core six + one" attached (Section 2, I2a). `mcp-fleet-curation` (cited by `hosted-model-agents` hard rule 2) already warns that per-URL servers "explode the tool catalogue"; one server with a `model` parameter is the catalogue-neutral form. |
| R3 wrapper family | N shell scripts -> N shell scripts (each ~0 MB when not running; they `exec` the CLI) | +0 ms: a wrapper that only exports variables and `exec`s adds one process spawn, no extra network hop | The alternative that L2 forbids (a resident LiteLLM/gateway) would add a permanent process *and* a loopback hop to every call. The wrapper family keeps the hop count at "CLI -> upstream". |
| R3 for Grok: 36 blocks -> `[endpoints]` | 0 -> 0 | Grok fetches `{base_url}/models` at startup (one extra loopback GET per session, sub-10 ms on 127.0.0.1; UNVERIFIED on this box) | Model list becomes discoverable, not hand-copied; when auth2api adds an id, Grok sees it without a config edit. Tradeoff (L7): a per-model `context_window` override is lost unless the block is kept - keep blocks only for models that need one. |
| R3 for Goose | 0 -> 0 (Goose provider JSON is already the declarative form) | unchanged | Already at the end state; only its *source* changes (generated from the registry instead of hand-written). |
| Delete `openai_proxy.py` | one Python HTTP process when used (~30-60 MB; UNVERIFIED) -> 0 | CLI -> proxy -> router (two hops) -> CLI -> router (one hop) | The HF router is natively OpenAI-compatible at `https://router.huggingface.co/v1/chat/completions` with `:provider` suffixes on the model id (FACT, https://huggingface.co/docs/inference-providers/index, A). |
| Local runtimes (no consolidation, but a setting) | Ollama keeps a model resident 5 min by default (`OLLAMA_KEEP_ALIVE`), and `OLLAMA_MAX_LOADED_MODELS` defaults to 3 per GPU (CPU box: 3) - i.e. up to three models could be co-resident on a 31.6 GB box (FACT, https://docs.ollama.com/faq, A). LM Studio: JIT loading ON by default, Idle TTL 60 min by default, Auto-Evict ON (at most 1 JIT model resident) (FACT, https://lmstudio.ai/docs/developer/core/ttl-and-auto-evict and https://lmstudio.ai/docs/developer/core/headless, A). | cold-load on first call after TTL vs resident | RECOMMENDATION: the registry row for `ollama` carries `env: {OLLAMA_MAX_LOADED_MODELS: "1"}` and a short `OLLAMA_KEEP_ALIVE`; the `lmstudio` row records that the estate relies on Auto-Evict=ON. Both are settings, not features removed (L7): the tradeoff is cold-load latency (seconds) against multi-GB idle RSS on a box that is below its G-4 target. |
| auth2api itself | unchanged (L3) | unchanged | Not this lens's to change; noted only that every consolidation above routes *through* it rather than beside it, so no second bridge process appears. |

Latency observation (INFERENCE): none of the consolidations add a network hop; two remove one
(`openai_proxy.py`, and any future "MCP per URL" that R2 pre-empts). The only added cost is a
startup `GET /models` for Grok, which is loopback.

## 6. Migration order and rollback

Order is chosen so that each step is independently revertible and no step removes a capability
before its replacement is proven (L7). Everything is on the *editing* checkout
(`~/source/ast-integrate`) and lands on GitHub before the executed checkout pulls it (SSOT-WIRE).

| Step | Action | Proof it worked | Rollback |
|---|---|---|---|
| M0 Probe (read-only) | `curl http://127.0.0.1:8317/v1/models` and one request each to `/v1/chat/completions`, `/v1/responses`, `/v1/messages` on auth2api; record which protocols exist. Same for `:11434/v1` and `:1234/v1`. | A JSON receipt committed under `docs/gem-hunt/2026-09-02-hosted-models/` (this lens's folder), one line per upstream x protocol. | none needed (read-only) |
| M1 Registry `upstreams` table | Add the table (R1) with the probed `protocols`; extend the control-plane tests to validate it (closed schema, credential *names* only, `sidecarOnly` on OpenRouter). | `pytest .agents/tests/test_mcp_control_plane*.py` green; `merge_generated_cursor_mcp.py --check` still `drift=0 managed=7`. | `git revert` one commit; no live file changed yet. |
| M2 Generators (dry-run only) | One script `render_upstream_consumers.py --check` that emits Goose JSON, Grok `[endpoints]`+overrides, Codex `[model_providers.*]` (Responses-only guard), Fabric `.env` lines, and the wrapper family scripts to a temp dir and diffs against the live files. | Diff shows only expected changes (e.g. Grok 36 blocks -> 1 endpoint + k overrides). | delete the script; nothing written. |
| M3 `hosted-inference` MCP (R2) beside `glm53-space` | Add the new server disabled in the registry; run it once by hand with `upstream=hf-router model=zai-org/GLM-5.3` and compare the answer shape to `glm53_chat`. | Same tool surface (one text-only tool), same secrets policy line, `mcp-tools-list` health probe passes. | disable/remove the new entry; `glm53-space` untouched. |
| M4 Swap the attach slot | Enable `hosted-inference`, mark `glm53-space` `enabled: false` with the DEPRECATED description (4.3), move the name in `CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS` and the two test assertions (lines 216, 660). | `--check` reports `managed=7`; Cursor shows one hosted-inference tool after reload; Claude lists it. | flip the two booleans back and restore the set; both servers remain defined so the revert is a two-line diff. |
| M5 Wrapper family `--write` | Generate into `~/.local/bin` beside the old names; old names become one-line shims to the new ones. | `ai-mode status` shows every CLI on `native`; each `<cli>-on-cursor` completes an `E2E_OK` one-liner (the estate already uses this exact receipt: `session-catalog.md` lines 45-47). | the old scripts are kept as `*.pre-R3` for one release; `ai-mode rollback` copies them back. |
| M6 Grok `[endpoints]` | Write `[endpoints] models_base_url = "http://127.0.0.1:8317/v1"` *only when M0 proved `/v1/models`*; keep per-model overrides that set `api_backend`/`context_window`. | `grok -m cursor-grok-4.6 "Reply with exactly: E2E_OK"`. | Grok config is a single TOML file; back it up as `config.toml.bak-<date>` (the estate already does this: `session-catalog.md` line 878 mentions `config.toml.bak-20...`). |
| M7 Delete | Remove `openai_proxy.py`, then the rest of `tools/mcp/glm53-space` from the executed checkout; drop the disabled `glm53-space` registry entry after one release. | Cursor approval store shows no orphan `glm53-space-<hex>` prompt; `--check` `drift=0`. | The directory is not on the remote (Section 2), so keep a tarball of the local copy under `D:\` before deleting; restoring is untar + re-enable the entry. |

Stop rules (RECOMMENDATION): abort M4 if `hosted-inference` cannot reproduce a `glm53_chat`
answer for GLM-5.3 (capability loss, L7); abort M6 if `/v1/models` on auth2api is absent or
returns fewer than the current 36 ids (capability loss); never run M5/M6 while a `cursor-agent`
process is alive (G-36 is about process count, and these steps launch CLIs for receipts).

## 7. Finds and rubric table

Scoring: value and effort on 1-5 (5 = highest value / most effort); `value x effort` is written
as `V/E` so a high-value low-effort find reads 5/1. Novelty-for-us: NEW (nothing in the
dedup-set does it), EXTENDS (builds on a dedup-set item), CONFIRMS (already true, now cited).
NATIVE = adopt a vendor mechanism as-is; BUILD = write code in this repo; DATA = registry/config only.

| # | name | what | why THIS estate | how to build or adopt | source | V/E | novelty-for-us | NATIVE-vs-BUILD |
|---|---|---|---|---|---|---|---|---|
| F1 | glm53-space is an orphan on the SSOT remote | Registry, merge script and a live test pin an adapter whose source dir exists on none of 55 remote refs (measured 2026-09-02). | SSOT-WIRE says the remote is the SSOT; the executed checkout is running bytes the remote does not hold. Deprecating it costs nothing on GitHub. | Treat as evidence for M7; tarball the local copy first. | this repo: `.agents/agents.json`, `merge_generated_cursor_mcp.py:143`, `test_mcp_control_plane_live.py:216,660`, `CLAUDE.md` SSOT-WIRE (A, corroborated) | 4/1 | NEW | DATA |
| F2 | `hosted-inference` MCP with `upstream`+`model` parameters | The general integration layer the owner asked for, as a *replacement* of `glm53-space` in the same registry slot. | Keeps Cursor at "core six + one"; catalogue-neutral; fits 512 MiB/6 GiB caps; honours `hosted-model-agents` rule "an inference URL is not Hub MCP". | Lift two constants out of `glm53_core.py` into tool params validated against R1. | `hosted-model-agents/SKILL.md` rules 2-4 (A); `agents.json` policy caps (A) | 5/2 | EXTENDS (2) | BUILD (small) |
| F3 | `upstreams` table in the ONE registry | Write each upstream once; generate every CLI dialect from it. | L2 forbids a resident gateway; a data table is the non-resident equivalent. Reuses the closed-schema and credential-name-only conventions already tested. | Add table + tests (M1); generator (M2). | `AGENTS.md` closed-schema rule (A); Goose/Grok/Codex/Fabric vendor docs (A/B) | 5/2 | NEW | DATA + BUILD (generator) |
| F4 | Grok `[endpoints] models_base_url` collapses 36 blocks to 1 | Grok fetches the model list from `{base_url}/models` and lets partial `[model.*]` overrides inherit `base_url`. | The `[model."cursor-*"]` blocks are the largest hand-copied table in the estate. | M6, gated on M0 proving `/v1/models` on auth2api. | https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/11-custom-models.md ; https://docs.x.ai/build/settings/reference (A, corroborated) | 4/1 | NEW | NATIVE |
| F5 | Codex needs Responses API since Feb 2026 | `wire_api = "chat"` removed; a leftover `chat` provider bricks *all* Codex commands. | `codex-cursor` only works if auth2api speaks `/v1/responses`; otherwise it is a dead wrapper, and any stale block would break `codex` outright. | M0 probe; generator refuses Codex output for chat-only upstreams. | https://github.com/openai/codex/blob/main/codex-rs/model-provider-info/src/lib.rs:64,94 (A); https://github.com/openai/codex/issues/41816 (B) | 5/1 | NEW | NATIVE (constraint) |
| F6 | Goose provider JSON is already the end state | Declarative `custom_providers/<name>.json` with `engine: openai`. | `goose-cursor-proxy` needs no consolidation, only to be *generated* from F3 so its model list cannot drift from auth2api's. | Generator emits the JSON; nothing else changes. | https://block-goose.mintlify.app/api/providers/custom (A) | 3/1 | CONFIRMS (3) | NATIVE |
| F7 | No official Cursor `/v1` chat API exists | Cursor docs: Cloud Agents API "are not a standalone model-inference or chat-completions API". | The L3 retirement trigger has not fired; auth2api stays. Anything that assumes a Cursor `/v1/chat/completions` is speculative. | Re-check the same URL at each gem-hunt; no build. | https://cursor.com/docs/api (A); https://forum.cursor.com/t/openai-compatible-v1-chat-completions-for-cloud-api/164522 (C) | 4/1 | CONFIRMS (3) | n/a |
| F8 | Delete `openai_proxy.py` | The HF router is natively OpenAI-compatible with `:provider` model suffixes. | Removes a process and a hop; every consumer supports `env_key`, so the proxy's token-hiding role is redundant. | M7. | https://huggingface.co/docs/inference-providers/index (A) | 3/1 | EXTENDS (2) | DELETE |
| F9 | One wrapper family + `ai-mode` switchboard | `<cli>-on-<upstream>` generated scripts; old names become shims. | Preserves C2/C3; keeps G-32 process-local by construction; 0 MB idle. | M5. | G-32 text in `hosted-model-agents/SKILL.md` (A); `session-catalog.md:876` (A) | 4/2 | EXTENDS (dedup 3) | BUILD (shell) |
| F10 | Local-runtime residency settings | Ollama default keep-alive 5 min and up to 3 co-resident models; LM Studio JIT + 60-min TTL + Auto-Evict. | Box is below G-4; a stray 3-model Ollama residency could be >20 GB. | `OLLAMA_MAX_LOADED_MODELS=1` and a short `OLLAMA_KEEP_ALIVE` on the registry row; record LM Studio Auto-Evict=ON. | https://docs.ollama.com/faq ; https://lmstudio.ai/docs/developer/core/ttl-and-auto-evict (A) | 3/1 | NEW | NATIVE (settings) |
| F11 | Grok `requirements.toml` as a fail-closed pin | Five-layer config; `~/.grok/requirements.toml` cannot be overridden by `config.toml` or env. | A place to pin "default model = native xAI" so Cursor quota stays opt-in even if `config.toml` drifts (matches the estate's opt-in stance). | One-line pin; optional. | https://docs.x.ai/build/enterprise (A) | 2/1 | NEW | NATIVE |
| F12 | Fabric has a fixed vendor set | Custom endpoints go through a pre-named vendor's `<VENDOR>_API_BASE_URL`; there is no free-form vendor. | `fabric-cursor` must reuse a slot (OpenAI or "LM Studio") per process; the generator must not try to add a vendor. | Generator emits `.env` lines + `-V`; document which slot is borrowed. | https://github.com/danielmiessler/Fabric/blob/main/README.md (B); issue #883 (B) | 2/1 | NEW | NATIVE (constraint) |

## 8. Ten-line summary

1. Measured: `tools/mcp/glm53-space` exists on none of the 55 remote refs; only the registry entry, the merge script's attach set and one live test pin it (F1).
2. No official Cursor `/v1/chat/completions` exists (cursor.com/docs/api), so the auth2api retirement trigger has not fired and `:8317` stays the only Cursor bridge (F7, L3).
3. Every consumer already has a native custom-endpoint mechanism: Goose provider JSON, Grok `[model.*]`/`[endpoints]`, Fabric `<VENDOR>_API_BASE_URL`, Codex `[model_providers.*]` (F4, F6, F12).
4. Codex removed Chat Completions in Feb 2026 (Responses only) - `codex-cursor` is only alive if auth2api serves `/v1/responses`; probe first (F5, M0).
5. Leanest end state: one `upstreams` table in `.agents/agents.json` (data, 0 MB) from which every CLI dialect is generated (F3, R1).
6. `glm53-space` becomes `hosted-inference` (tool `chat(upstream, model, ...)`) in the *same* registry slot, so Cursor stays at "core six + one" and the server count stays 42 (F2, R2).
7. All `*-cursor`/`ai-mode`/`grok-mode` scripts become one generated `<cli>-on-<upstream>` family plus the `ai-mode` switchboard; old names stay as shims (F9, R3).
8. Grok's 36 `[model."cursor-*"]` blocks collapse to one `[endpoints]` block gated on `/v1/models` existing; `openai_proxy.py` is deleted because the HF router is already OpenAI-compatible (F4, F8).
9. RAM/latency: no consolidation adds a process or a hop; two remove one; local runtimes get residency caps (Ollama 3 co-resident by default) because the box is below its 8 GB-free target (F10).
10. Migration M0-M7 is probe -> data -> dry-run -> side-by-side -> swap -> delete, each step with a receipt and a two-line rollback; nothing is removed before its replacement passes an `E2E_OK` receipt (L7).

Status: COMPLETE 2026-09-02. Discovery only; no code changed.
