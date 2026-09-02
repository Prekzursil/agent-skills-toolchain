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
