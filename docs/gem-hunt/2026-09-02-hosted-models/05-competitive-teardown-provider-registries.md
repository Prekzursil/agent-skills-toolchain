# Lens 05 - Competitive teardown: provider/model registries in other harnesses

- Gem-hunt: `2026-09-02-hosted-models` (discovery only; no code changed)
- Lens id: `05-competitive-teardown-provider-registries`
- Branch: `gemhunt/hosted-models-05-competitive-teardown-provider-registries` (from `main` @ `5fa34fda1`)
- Author: cloud agent, one lens of a multi-lens hunt
- Date: 2026-09-02
- Status: IN PROGRESS - sections are appended and pushed one at a time (platform kills runs ~12 min)

## 0. Scope, method, locks

### 0.1 Question this lens answers

How do the other agent harnesses on (or adjacent to) this estate describe a *model endpoint* -
`id`, `base_url`, API shape, auth env-var name, context window, tool support, cost, capability
flags, health probe - and how do they materialize that description into per-runtime config?
Which pieces should the estate's own registry (`.agents/agents.json` + secrets-by-name in
`.agents/local.json`, DEDUP item 4) copy *verbatim*, and which are NATIVE (already shipped by a
runtime we run) vs BUILD (we would have to write it)?

Targets named by the hunt brief: OpenCode (models.dev registry + `provider` config), Goose
`custom_providers`, Aider model settings/metadata, Cline / Roo Code / Continue provider schemas,
Kilo Code, Pi (`pi-mono`) / Oh-my-pi, Hermes Agent, Crush, Codex `model_providers`, Grok CLI
`[model.X]` blocks, Claude Code settings.

### 0.2 Method (deep-research discipline)

- Every claim carries a URL and a grade. Grade = source tier + corroboration + date:
  - **A** = primary artifact (the schema file, the Rust/TS/Go struct, the JSON Schema, official docs).
  - **B** = official docs or maintainer text that describes but is not the artifact.
  - **C** = secondary (blog, issue thread, third-party summary).
  - `corroborated` = two independent sources agree; `UNVERIFIED` = single source or unreachable
    at hunt time; every grade carries the retrieval date `(2026-09-02)`.
- Preference: sources from the last 12 months (2025-09 .. 2026-09). Older sources are flagged.
- Each paragraph is labelled **[FACT]** (sourced), **[INFERENCE]** (my reasoning from facts) or
  **[RECOMMENDATION]** (what the estate should do).
- Verification ladder used: `WebFetch` of the raw schema file on GitHub or the official docs page;
  where a fetch failed, the claim is marked `UNVERIFIED` rather than dropped.

### 0.3 Estate locks (constraints, cited as given by the hunt brief; never violated below)

| Lock | Consequence for this lens |
| --- | --- |
| OpenRouter is a spend-capped CLI/Codex sidecar only; never a Cursor BYOK key, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP | Any "copy models.dev / OpenRouter pricing" finding is registry *metadata*, not a routing change. |
| No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory | Findings that lean on a proxy layer (LiteLLM-style) are marked out-of-bounds and only their *schema* is harvested. |
| `auth2api :8317` stays the only Cursor bridge; retires within 7 days of an official Cursor `/v1` GA | Every per-runtime materialization below points `cursor-*` ids at `127.0.0.1:8317`, never elsewhere. |
| Ports 8765 / 8812 / 8317 are owned | No health-probe or registry service may claim them. |
| `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it) | Provider registry is *config* SSOT, not prompt SSOT; nothing here duplicates prompts. |
| Never rotate credentials | Secrets stay *by name* (`auth_env`), never by value, in any schema proposed. |
| Never remove a feature to buy reliability - present tradeoffs | Deprecating `tools/mcp/glm53-space` (DEDUP item 2) is the owner's decision; this lens only supplies the replacement schema. |

### 0.4 DEDUP-SET acknowledged (not re-proposed)

1. `.agents/skills/hosted-model-agents` on `live-capture/2026-09-02` - current doctrine.
2. `tools/mcp/glm53-space` on `main` - hardcoded to `router.huggingface.co/v1` + `zai-org/GLM-5.3`; to be deprecated in favour of a general integration layer (this lens feeds that layer's schema).
3. `auth2api` on `127.0.0.1:8317` - 36 `cursor-*` model ids; consumed by goose, grok `config.toml`, fabric/claude/codex wrappers.
4. Registry `.agents/agents.json` (`mcp.servers`, 42 servers) + secrets by name in `.agents/local.json`.
5. Installed runtimes on the Windows 11 box (31.6 GB RAM, no GPU assumed): claude, codex, cursor-agent, grok + agent.exe, goose 1.47, fabric 1.4.470, agy, gemini CLI, opencode, aider 0.86, ollama, lms, ralph, basic-memory :8765, agent-mail :8812, browser-bridge hub :8770.

<!-- sections 1..N appended below, one per harness; rubric table last -->
