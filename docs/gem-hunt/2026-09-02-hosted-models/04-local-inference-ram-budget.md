# Gem-hunt 2026-09-02 (hosted-models) - lens 04: local inference on a 31.6 GB RAM Windows box, no known GPU

- **Lens id:** `04-local-inference-ram-budget`
- **Mode:** discovery only (no code changes). One file, committed + pushed per section.
- **Question:** which local inference servers (Ollama, LM Studio `lms`, llama.cpp `llama-server`, vLLM-in-WSL) and which quantized models fit a **6-12 GB RAM budget** on the owner's **31.6 GB RAM, chronically memory-starved Windows 11 box with no GPU assumed**, with tool-calling that actually works; what OpenAI-compatible API parity each server offers (tools, JSON mode, streaming, embeddings); how each releases RAM when idle (keep_alive, JIT load/unload, TTL); Windows-specific pitfalls; and how the replacement integration layer should **probe** capability instead of assuming it.
- **Written:** 2026-09-02 (UTC). Sources preferred from the last 12 months; anything older is flagged.

## 0. Evidence discipline used in this file

Every claim carries a source URL and a grade:

- **Tier A** = primary source (vendor docs, source code, the issue tracker itself, first-party benchmark).
- **Tier B** = reputable secondary (maintainer blog, well-known community measurement, HF model card).
- **Tier C** = forum/anecdote/single-user report.
- **corroborated** = two independent sources agree; **UNVERIFIED** = single source or could not be re-checked from this sandbox.
- Each statement is labelled **[fact]** (sourced), **[inference]** (my reasoning from facts) or **[recommendation]**.
- Dates are the source's publication or last-updated date where visible; **(checked 2026-09-02)** marks what I could fetch live.

Sandbox limits: this run had no access to the owner's Windows box, so nothing here is a measurement on the target machine. All RAM/tok-s figures are budgets derived from published quant sizes and community CPU numbers; **the integration layer must measure, not trust this table** (see section 8).

## 1. Dedup-set and estate locks (constraints, not proposals)

Already exists - not re-proposed here:

1. Skill `.agents/skills/hosted-model-agents` (branch `live-capture/2026-09-02`): SKILL.md, environments.md, profiles.md, tool-loop.md, evals.md, recipes/hf-space-openai.md. Current doctrine for hosted/local models. This lens feeds it; it does not replace it.
2. `tools/mcp/glm53-space` (main): `glm53_core.py`, `mcp_server.py` (one tool `glm53_chat`), `openai_proxy.py`, hardcoded to `router.huggingface.co/v1` model `zai-org/GLM-5.3`. Owner has decided to DEPRECATE and replace with a general integration layer - this lens is input to that layer's local-backend adapter.
3. `auth2api` on `127.0.0.1:8317` - the ONLY Cursor-quota OpenAI-compatible bridge (36 `cursor-*` model ids); consumed by goose, grok `config.toml`, fabric/claude/codex wrappers in `~/.local/bin`.
4. Registry `.agents/agents.json` (`mcp.servers`, 42 servers) + secrets by name only in `.agents/local.json`.
5. Installed runtimes on the Windows 11 box: claude, codex, cursor-agent, grok + agent.exe, goose 1.47, fabric 1.4.470, agy, gemini CLI, opencode, aider 0.86, **ollama**, **lms (LM Studio)**, ralph, basic-memory :8765, agent-mail :8812, browser-bridge hub :8770; wrappers ai-mode, grok-mode, qwen-space (deprecated pointer), claude-swap.

Estate locks (hard; every recommendation below is checked against them):

- OpenRouter = spend-capped CLI/Codex sidecar only; never Cursor BYOK, never Claude `ANTHROPIC_BASE_URL`, never a new OpenRouter MCP.
- No LiteLLM, no LangGraph, no second orchestration runtime, no vector-DB memory.
- `auth2api :8317` stays the only Cursor bridge; retires within 7 days of an official Cursor `/v1` GA.
- Ports 8765 / 8812 / 8317 are owned. (Also observed in dedup-set: 8770 browser-bridge.) Local servers' defaults - Ollama 11434, LM Studio 1234, llama-server 8080, vLLM 8000 - do not collide with these. [fact, from each server's docs cited below]
- `.agents/skills` is the ONE prompt SSOT (Fabric/Goose consume it).
- Never rotate credentials; never remove a feature to buy reliability - present trade-offs instead.

## 2. The RAM reality on this box (what "6-12 GB budget" actually means)

_(section pending - written in the next commit)_

## 3. Server-by-server: API parity, idle/unload behaviour, Windows pitfalls

_(pending)_

## 4. Which small models have tool-calling that actually works (benchmarks + issue trackers)

_(pending)_

## 5. RAM-budgeted shortlist

_(pending)_

## 6. Exact server flags / commands

_(pending)_

## 7. vLLM / WSL2: is it worth it here?

_(pending)_

## 8. How the integration layer should PROBE capability instead of assuming it

_(pending)_

## 9. Per-find rubric table

_(pending)_

## 10. Ten-line summary

_(pending)_
