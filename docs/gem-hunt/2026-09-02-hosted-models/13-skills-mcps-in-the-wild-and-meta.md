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

## 3. Survey: HF model access (skills, MCPs, CLIs) `[pending]`

## 4. Survey: OpenAI-compatible model access `[pending]`

## 5. Survey: model catalog sources and sync tooling `[pending]`

## 6. Survey: provider health probing `[pending]`

## 7. Ranking: maintenance x license x security `[pending]`

## 8. Meta loop design `[pending]`

## 9. Rubric table `[pending]`

## 10. Ten-line summary `[pending]`
