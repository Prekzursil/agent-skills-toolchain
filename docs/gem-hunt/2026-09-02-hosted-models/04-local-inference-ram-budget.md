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

**[inference]** A local model's steady-state footprint is `weights + KV cache + compute buffers + runtime`, not the GGUF file size alone. On a 31.6 GB box that is "chronically memory-starved", the number that matters is *free* RAM at the moment of load, so every budget below is a **working-set** budget, and the integration layer must read the actual free-RAM counter before loading (section 8).

Working-set arithmetic (all [inference] from published model configs; grade B):

- **KV cache per token** = `2 x layers x kv_heads x head_dim x bytes`. Qwen3-4B and Qwen3-8B both use 36 layers x 8 KV heads x 128 head-dim (Qwen3 HF `config.json`, Apr 2025; https://huggingface.co/Qwen/Qwen3-8B) -> 73,728 values/token -> **~144 KB/token at f16**, so 8k context = ~1.15 GB, 32k = ~4.6 GB. Llama-3.1-8B (32 layers x 8 x 128) is ~128 KB/token -> 8k = ~1 GB. Quantising the KV cache to q8_0 halves this (Ollama `OLLAMA_KV_CACHE_TYPE=q8_0`; llama.cpp `--cache-type-k q8_0 --cache-type-v q8_0`; both documented in section 6).
- **Weights** at Q4_K_M: ~2.3-2.5 GB for 3.8-4B dense, ~4.3-5.1 GB for 7-9B dense, ~4.3 GB for Granite-4.0-h-tiny (7B-A1B MoE), ~17-19 GB for Qwen3-30B-A3B-class MoE (per-model sizes with sources in section 5).
- **Runtime + compute buffers**: budget 0.4-1.0 GB (Ollama runner process, llama-server slots, LM Studio runtime). Community calculators use ~600 MB baseline for Ollama/llama.cpp (Tier C, https://bestllmfor.com/catalog/granite4-tiny/, 2026).

Budget tiers used in the rest of this file:

| Tier | Working-set ceiling | What fits | Typical arithmetic |
|---|---|---|---|
| **S** | <= 6 GB | 3.8-4B dense Q4_K_M at 8k ctx | 2.5 GB weights + 1.2 GB KV + 0.6 GB runtime = ~4.3 GB |
| **M** | <= 12 GB | 7-9B dense Q4_K_M at 8-16k ctx; Granite-4.0-h-tiny at 32k | 5 GB + 1.2-2.3 GB + 0.8 GB = ~7-8 GB |
| **L (stretch)** | 13-20 GB, only when *measured* free RAM >= 22 GB | Qwen3-30B-A3B-class MoE Q4_K_M; gpt-oss-20b MXFP4 | outside the briefed 6-12 GB budget; listed because MoE-on-CPU speed is the one place a RAM-rich, GPU-less box wins |

**Speed class is memory-bandwidth-bound, not compute-bound [fact, corroborated].** Single-user decode on CPU reads every *active* weight byte per token, so `tok/s ~= effective RAM bandwidth / active bytes per token`. InventiveHQ measured a Qwen3-30B-A3B MoE Q4_K_M decoding at **10.6 tok/s vs 11.8 tok/s for a dense 3B** on the same i7-8700 / dual-channel DDR4-2400 box, CPU-only (`-ngl 0`, 6 threads) - MoE runs at its *active* size (Tier B, 2026, https://inventivehq.com/blog/moe-on-cpu-benchmark; harness https://github.com/InventiveHQ/local-llm-benchmarks/tree/main/experiments/moe-on-cpu). At the other extreme a 12-channel DDR5 EPYC 9554 (460 GB/s) runs Llama-3.1-8B Q4_K_M at 49.6 tok/s and Qwen3-Coder-30B-A3B Q4_K_M at 42.2 tok/s (Tier B, 2025, https://ahelpme.com/ai/llm-inference-benchmarks-with-llamacpp-with-amd-epyc-9554-cpu/ and https://ahelpme.com/ai/llamacpp-ai/llama-bench-the-qwen3-coder-30b-a3b-and-amd-epyc-9554-cpu/). A Raspberry Pi 5 (17 GB/s) does the same MoE at ~8 tok/s (Tier B, https://github.com/geerlingguy/ai-benchmarks/issues/47).

**[inference]** A consumer desktop/laptop with dual-channel DDR4-3200 (~35-40 GB/s effective) or DDR5-5600 (~60-70 GB/s effective) therefore lands at roughly **7-13 tok/s for 8B Q4_K_M, 14-26 tok/s for 4B Q4_K_M, 10-25 tok/s for a 30B-A3B MoE**. These are classes, not measurements: the owner's DIMM/LPDDR configuration is unknown from this sandbox, so section 8 has the layer measure tok/s on first load and persist it.

**Is there really no GPU? [recommendation]** Budget as if none, but *probe*: most Windows 11 machines have an Intel/AMD iGPU, and both Ollama and llama.cpp ship Vulkan backends on Windows (section 3). An iGPU shares the same RAM bandwidth, so it does **not** raise the decode ceiling much [inference], but it can take prompt-processing compute off the CPU. A Ryzen AI 890M iGPU was detected by Ollama as `type=iGPU total="17.8 GiB"` via `OLLAMA_VULKAN=1` (Tier C single report, 2026-04-12, https://www.binwh.com/en/2026/04/12/vulkan-ollama-amd-gpu/). Treat as a probe result, never a plan.

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
