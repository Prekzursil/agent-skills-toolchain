# Gem-hunt lens 02 - Hugging Face inference surfaces (2026)

- Hunt: `2026-09-02-hosted-models`
- Lens id: `02-huggingface-inference-surfaces`
- Mode: discovery only. No code changed. Findings, citations, decision table, rubric.
- Author: Cursor cloud agent (Claude), 2026-09-02.
- Branch: `gemhunt/hosted-models-02-huggingface-inference-surfaces` (from `main`).

## 0. Reading guide and grading scheme

Every claim carries a grade in square brackets:

- Tier: `A` = primary source (HF docs, HF blog, HF pricing page, HF GitHub repo, HF changelog),
  `B` = secondary but reputable (provider docs, major outlets, well-maintained third-party docs),
  `C` = forum/thread/community post/inferred from behaviour.
- Corroboration: `corr` = two or more independent sources agree; `UNVERIFIED` = single source or
  not re-checked live from this sandbox.
- Date: the date the source was published or last updated, when the page states it; otherwise the
  fetch date (`f:2026-09-02`).
- Kind: `[fact]` = sourced, `[infer]` = inference from facts, `[rec]` = recommendation.

Estate locks (hard constraints, restated so no finding below can be read as violating them):

- OpenRouter is a spend-capped CLI/Codex sidecar only; never a Cursor BYOK key, never
  `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP.
- No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory.
- `auth2api` on `127.0.0.1:8317` stays the ONLY Cursor bridge; retires within 7 days of an
  official Cursor `/v1` GA. Ports 8765/8812/8317 are owned.
- `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it).
- Never rotate credentials. Never remove a feature to buy reliability; present trade-offs instead.

Dedup-set (exists; not re-proposed): `hosted-model-agents` skill (branch
`live-capture/2026-09-02`), `tools/mcp/glm53-space` (deprecation decided), `auth2api :8317`,
`.agents/agents.json` + `.agents/local.json`, the installed Windows runtimes and wrappers.

## 1. Status

Sections are appended as research lands; each section is committed and pushed on completion.

- [ ] 2. router.huggingface.co/v1 (Inference Providers)
- [ ] 3. Inference Endpoints (dedicated)
- [ ] 4. Spaces as inference hosts (Gradio MCP, /v1 Spaces, ZeroGPU, sleep/wake, owner recipe)
- [ ] 5. Official Hugging Face MCP server
- [ ] 6. HF token scopes
- [ ] 7. Decision table: router vs endpoint vs space vs local
- [ ] 8. Stale claims in the current `hosted-model-agents` skill
- [ ] 9. Rubric table
- [ ] 10. Ten-line summary
