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

### 3.1 Ollama (installed on the box; default port 11434)

**API parity [fact, Tier A, checked 2026-09-02, https://docs.ollama.com/api/openai-compatibility]:**
- `/v1/chat/completions`: chat, streaming, JSON mode, `response_format`, `tools`, `seed`, `stream_options.include_usage`, `reasoning_effort` for thinking models. **Not** supported: `tool_choice`, `logprobs`, `logit_bias`, `n`. The readthedocs mirror is stale ("Tools (streaming support coming soon)", Tier B, https://ollama.readthedocs.io/en/openai/); the current docs.ollama.com page lists streaming and tools both ticked. Structured outputs: JSON schema via native `format` or OpenAI `response_format` (Tier A, https://github.com/ollama/ollama/blob/main/docs/api.md).
- `/v1/embeddings`: `input` string or array, `encoding_format`, `dimensions` (Tier A, same page). Native `/api/embed` also exists.
- `/v1/responses`: streaming + tools supported; **stateful** fields (`previous_response_id`, `conversation`) not supported (Tier A, same page).
- Native `/api/chat` is the more battle-tested tool path: a 2026 client write-up reports the `/v1` streaming path dropped tool-call delta chunks (tracked as Ollama issue #5769) and that the fix was to switch to `/api/chat` (Tier C, https://www.betterclaw.io/blog/openclaw-model-does-not-support-tools, 2026). Third-party trackers also show `/v1` returning tool JSON inside `message.content` with no `tool_calls` field for some models (Tier B, https://github.com/Gitlawb/openclaude/issues/433, 2026). **[recommendation]** probe tools on the exact endpoint the layer will use, streaming and non-streaming separately.
- Capability discovery is **first-class**: `POST /api/show` returns a `capabilities` array (e.g. `completion`, `tools`, `thinking`, `vision`, `embedding`); `GET /api/ps` returns loaded models with `size`, `size_vram`, `context_length`, `expires_at` (Tier A, https://github.com/ollama/ollama/blob/main/docs/openapi.yaml; https://docs.ollama.com/api/ps). A model whose template lacks the tools capability yields HTTP 400 "does not support tools" (Tier A issue thread, https://github.com/ollama/ollama/issues/9680). Caveat from the maintainers: GGUFs pulled straight from HF via `hf.co/...` "generally don't come with the template that ollama uses to detect capabilities" - use the Ollama library tag or merge the library Modelfile (Tier A maintainer comment, https://github.com/ollama/ollama/issues/13820, 2026-01).

**Idle / unload [fact, Tier A, corroborated]:** default `keep_alive` = **5 minutes** per model, timer restarts after each request; `OLLAMA_KEEP_ALIVE` sets the server default; per-request `keep_alive` overrides it; `0` unloads immediately after the response; any negative value = forever; `ollama stop <model>` unloads now (https://github.com/ollama/ollama/blob/main/docs/faq.mdx, checked 2026-09-02; corroborated by https://www.ssdnodes.com/learn/ollama-keep-model-loaded, Aug 2026). `OLLAMA_MAX_LOADED_MODELS` default = 3 on CPU; the scheduler evicts an idle model (even a `-1` one) when a new model needs memory (same sources). `OLLAMA_NUM_PARALLEL`: the current FAQ says default 1 and "Required RAM will scale by OLLAMA_NUM_PARALLEL * OLLAMA_CONTEXT_LENGTH" (Tier A, faq.mdx); the readthedocs mirror still says "auto-select 4 or 1" (Tier B, stale). `OLLAMA_KV_CACHE_TYPE=q8_0` halves KV memory; `OLLAMA_FLASH_ATTENTION` became a three-state auto override in Oct 2025 (Tier B, https://modelpiper.com/blog/ollama-environment-variables, 2026).

**Windows-specific pitfalls [fact unless marked]:**
1. Env vars must be set as *user environment variables* and the tray app restarted; a shell `export` does nothing for the background app (Tier A, faq.mdx "How do I configure Ollama server" Windows steps).
2. Ollama runs as a native Windows tray app (`ollama app.exe`) on Windows 10 22H2+; a standalone `ollama-windows-amd64.zip` (CLI + libs only) exists for running `ollama serve` as a service via NSSM (Tier A, https://docs.ollama.com/windows).
3. **mmap -> pre-allocation regression (0.20.x):** an issue reports that 0.20.x load requests show `UseMmap:false`, so the runner pre-allocates the full weight buffer instead of lazily mapping the file; on a 16 GB Windows box with 24 GB VRAM this broke loads of >10 GB models because WDDM backs GPU allocations with system RAM (Tier A issue, https://github.com/ollama/ollama/issues/15352; resolution status **UNVERIFIED** from this sandbox). **[inference]** for a CPU-only, RAM-starved box the practical consequence is the same: assume Ollama commits the *entire* weight size to RAM at load, no lazy paging. `OLLAMA_USE_MMAP` exists as a global knob since mid-2025 (Tier A, https://github.com/ollama/ollama/pull/8895).
4. **Zombie runners hold memory:** race conditions in the scheduler have left `ollama_llama_server`/runner processes alive after `ollama ps` shows nothing (Tier A issues https://github.com/ollama/ollama/issues/10433, https://github.com/ollama/ollama/issues/7606 - the latter still reporting "Stopping..." hangs on v0.32.4 in 2026). Windows-specific server-side VRAM growth was also reported (https://github.com/ollama/ollama/issues/10597). **[recommendation]** the layer's health check must compare `Get-Process ollama*` count against `/api/ps` and kill orphans.
5. **Vulkan on Windows** is enabled by default in current Ollama and is the recommended fallback for AMD/iGPU; `OLLAMA_VULKAN=0` disables, `GGML_VK_VISIBLE_DEVICES` selects (Tier A, https://docs.ollama.com/gpu, checked 2026-09-02). Known bug: the bundled `vulkan-1.dll` loader found 0 devices where the system loader worked, fixed by PR #16869 "use host Vulkan loader on Windows" (Tier A, https://github.com/ollama/ollama/issues/16677, Ollama 0.30.7, 2026). The original Vulkan PR notes the scheduler "will need some adjusting to be iGPU aware instead of naively favoring the GPU with the most VRAM" (Tier A, https://github.com/ollama/ollama/pull/11835, Aug 2025).
6. Default model store is `%USERPROFILE%\.ollama\models` on the system drive; relocate with `OLLAMA_MODELS` (Tier A, faq.mdx).
7. Version drift is fast: issues in 2026 reference Ollama 0.20.x, 0.30.7 and 0.32.4 (sources above). **[recommendation]** the layer records `GET /api/version` alongside every probe result so a regression can be tied to a build.

### 3.2 LM Studio (installed on the box as `lms`; default port 1234)

**Headless is now first-class [fact, Tier A]:** LM Studio 0.4.0 shipped `llmster`, "the LM Studio Daemon for headless deployments w/o GUI", installed on Windows with `irm https://lmstudio.ai/install.ps1 | iex`, driven by `lms daemon up`, `lms get <model>`, `lms server start`, `lms chat` (https://lmstudio.ai/changelog/lmstudio/lmstudio-v0.4.0; https://lmstudio.ai/blog/0.4.0; https://lmstudio.ai/docs/developer/core/headless, checked 2026-09-02). The alternative is the desktop app in headless mode ("run the LLM server on login", minimises to tray) with `lms server start` restoring last server state (same headless page). The 0.4.0 notes also fixed "certain settings may get adjusted unexpectedly when using llmster (for example, the JIT model loading may become disabled)" - **[recommendation]** the layer must verify JIT is on rather than assume it.

**API parity [fact, Tier A, checked 2026-09-02]:**
- `/v1/chat/completions` with `tools`: LM Studio "parses the text output from the model into an OpenAI-compliant chat.completion response"; `finish_reason` = `tool_calls`; streaming sends tool calls in chunks via `delta.tool_calls.function.name/arguments`. For models without a native tool format it still attempts to parse tool calls from text (https://lmstudio.ai/docs/developer/openai-compat/tools). **[inference]** this "attempt to parse" is exactly why a probe must check for structured `tool_calls`, not just a 200.
- Structured output: `response_format: {type: json_schema, json_schema: {...}}` on `/v1/chat/completions`, with the explicit warning "Not all models are capable of structured output, particularly LLMs below 7B parameters" (https://lmstudio.ai/docs/developer/openai-compat/structured-output).
- `/v1/embeddings` supported (https://lmstudio.ai/docs/developer/openai-compat/embeddings); `/v1/responses` and an Anthropic-compatible `/v1/messages` also exist; the native stateful `/api/v1/chat` adds MCP tools, load-progress streaming and per-request context length, but **not** custom tools - the feature matrix is on https://lmstudio.ai/docs/developer/rest.
- Discovery: legacy `GET /api/v0/models` returns `type` (`llm`/`vlm`/`embeddings`), `quantization`, `state` (`loaded`/`not-loaded`), `max_context_length` per model (https://lmstudio.ai/docs/developer/rest/endpoints); 0.4.0 recommends the v1 REST API under `/api/v1/*` with `POST /api/v1/models/load` / `unload`. `lms ps --json` shows loaded models and queue state (https://deepwiki.com/lmstudio-ai/docs/2-api-server-architecture, Tier B).

**Idle / unload [fact, Tier A, corroborated by the docs corpus https://www.lmstudio.ai/llms-full.txt]:** JIT loading is on by default: with JIT ON, `/v1/models` lists *all downloaded* models and any inference call loads the model; with JIT OFF, `/v1/models` lists only loaded models and you must `lms load` first (headless page). **Idle TTL default = 60 minutes** for JIT-loaded models, overridable per request with a `ttl` field (seconds) or as an app default; **Auto-Evict is ON by default** and keeps at most **1** JIT-loaded model resident; models loaded via `lms load` have **no TTL** unless `--ttl <seconds>` is passed, and are not auto-evicted (https://lmstudio.ai/docs/cli/local-models/load; llms-full.txt "Idle TTL and Auto-Evict"). `lms unload --all` frees everything. **[recommendation]** on this box: keep JIT on, set app-default TTL to 300-600 s (not 60 min), never `lms load` without `--ttl`, and use `lms ps --json` in the health check.

**Windows pitfalls [fact unless marked]:**
1. x64 Windows requires **AVX2**; LM Studio "recommends" 16 GB RAM and 4 GB dedicated VRAM (https://www.lmstudio.ai/llms-full.txt system requirements) - the VRAM line is a recommendation, CPU-only runs work with the CPU llama.cpp runtime (`lms runtime update llama.cpp`, blog 0.4.0).
2. Two daemons can fight: the GUI app and `llmster` are separate processes bound to the same default port 1234; the changelog notes settings drift when both are used. **[recommendation]** pick one (llmster) and have the layer detect the other by port owner.
3. The 60-minute default TTL means a JIT-loaded 8B model silently holds ~7 GB for an hour after the last call - the single largest idle-RAM risk among the three servers on a memory-starved box [inference from the defaults above].

### 3.3 llama.cpp `llama-server` (not yet on the box; prebuilt Windows zips exist; default port 8080)

**Windows builds [fact, Tier A]:** every release ships `llama-bXXXX-bin-win-cpu-x64.zip` and `llama-bXXXX-bin-win-vulkan-x64.zip` (plus CUDA/HIP/SYCL) - e.g. release b8634 lists both (https://github.com/ggml-org/llama.cpp/releases/tag/b8634, 2026). No install, no service: unzip and run.

**API parity [fact, Tier A, tools/server/README.md at HEAD, checked 2026-09-02, https://github.com/ggml-org/llama.cpp/blob/HEAD/tools/server/README.md]:**
- OpenAI-compatible `/v1/chat/completions`, `/v1/completions`, `/v1/embeddings`, `/v1/responses`, `/v1/models`; Anthropic `/v1/messages`; `/reranking`; token-counting endpoints; `/v1/chat/completions/control` to stop reasoning mid-stream.
- **Tools:** "Function calling / tool use for ~any model" via `common/chat.h`; `--jinja` is now **default enabled**; native handlers for Llama 3.x, Functionary, Hermes 2/3, Qwen 2.5, Mistral Nemo, Firefunction v2, Command R7B, DeepSeek R1, Granite and many more, with a **Generic** fallback when the template is unrecognised (log shows `Chat format: Generic`) that "may consume more tokens" (https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md; mirror https://ggml-org-llama-cpp.mintlify.app/advanced/function-calling). `parallel_tool_calls` is off by default and "only supported on some models, verification is based on jinja template" (README). The function-calling doc's own probe: inspect `chat_template` / `chat_template_tool_use` in `GET /props`.
- **JSON mode / schema:** `response_format` supports `json_object` and `json_schema` (grammar-constrained), plus raw `grammar` / `json_schema` fields (README).
- **Streaming** with tool calls is supported and the parser is streaming-aware (the Granite 4 detection bug below surfaced *only* in streamed, fragmented tool JSON).

**Idle / unload [fact, Tier A]:** two mechanisms:
1. **Sleep mode:** `--sleep-idle-seconds N` unloads "the model and its associated memory (including the KV cache)" after N seconds without tasks and reloads on the next task; works in single- and multi-model mode; `GET /health`, `/props`, `/models`, `/metrics` do **not** reset the timer or wake the model (README "sleep mode", PR #18228).
2. **Router mode:** start without `-m` (auto-discovers `LLAMA_CACHE`) or with `--models-dir PATH` / `--models-preset file.ini`; models load on first request (`--models-autoload`, default on), one child *process* per model so a crash is isolated, LRU eviction at `--models-max N` (default 4, 0 = unlimited); explicit `POST /models/load` / `POST /models/unload`, `GET /models` with per-model `status`, `GET /models/sse` events; `?autoload=false` per request (README "Using multiple models"; https://huggingface.co/blog/ggml-org/model-management-in-llamacpp, Dec 2025). There is no unload-all endpoint - iterate `GET /models` (Tier B, https://www.glukhov.org/llm-hosting/llama-cpp/llama-server-router-mode/). `--models-autoload` means "load when requested", not "preload at start" (maintainer clarification, https://github.com/ggml-org/llama.cpp/issues/18035).

**Windows / memory pitfalls [fact unless marked]:**
1. `--mmap/--no-mmap/--mlock` are **deprecated** in favour of `--load-mode {auto|none|mmap|mlock|mmap+mlock|dio}` (README; Debian manpage https://manpages.debian.org/unstable/llama.cpp-tools/llama-server.1.en.html). With mmap (default) Windows shows the model in *both* page cache and process working set, which reads as "RAM = VRAM" in Task Manager; `--no-mmap`/`--load-mode none` "reduced the RAM usage significantly" in one Windows report (Tier B, https://github.com/ggml-org/llama.cpp/discussions/19883, 2026). `--load-mode mlock` now *implies* mmap; a 2026 issue documents `--load-mode none` letting the OS swap out CPU-resident tensors under sustained load (throughput 25 -> 7.5 tok/s) (https://github.com/ggml-org/llama.cpp/issues/26110). **[recommendation]** on a RAM-starved Windows box prefer `--load-mode mmap` (default) so idle pages are reclaimable standby memory, and rely on `--sleep-idle-seconds` for real release; never `--mlock` a model that is a large fraction of free RAM.
2. Windows trims working sets aggressively below a few hundred MB free and pages to the same disk the model streams from - one Windows CPU project reports stock llama.cpp dying at 2 tokens until it capped the working set (Tier C, https://github.com/Heman10x-NGU/expert-stream/blob/main/README.md). **[inference]** keep >= 2 GB headroom over the working-set budget.
3. Template detection bugs are model-specific and get fixed in point releases: Granite 4.0 was mis-detected as Hermes and crashed on fragmented streamed tool JSON until PR #16526 (https://github.com/ggml-org/llama.cpp/issues/16415, Oct 2025); the non-jinja C++ path emitted a literal `assistant_tool_call` role until PR #20804 / b8634 (https://github.com/ggml-org/llama.cpp/pull/20804). **[recommendation]** pin a build number in the layer's probe record and always run with `--jinja` (the default).
4. Context defaults: `-c 0` means "loaded from model", i.e. Qwen3 would allocate KV for its full 32-40k native context [inference from README default]; always set `-c` explicitly on this box.

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
