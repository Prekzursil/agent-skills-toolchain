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

_(pending)_

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
