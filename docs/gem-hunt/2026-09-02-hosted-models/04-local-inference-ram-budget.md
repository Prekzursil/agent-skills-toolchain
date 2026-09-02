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

### 4.1 What "works" means here

**[recommendation]** Three independent things must hold, and the layer should test each: (a) the model was *trained* on a tool format (native template) - otherwise the server falls back to a generic/prompted handler; (b) the *server* parses that format into structured `tool_calls` (streaming and non-streaming); (c) the model picks the right function and arguments often enough (BFCL-class accuracy). Most "tools don't work" reports in the trackers are (a) or (b), not (c).

### 4.2 Benchmark evidence (BFCL v4, the standard tool-calling leaderboard)

- The live leaderboard (https://gorilla.cs.berkeley.edu/leaderboard, "Last Updated: 2026-04-12", evaluated at commit f7cf735, `bfcl-eval==2025.12.17`) distinguishes **FC** (native function calling) from **Prompt** (text workaround) modes (Tier A).
- Overall-accuracy snapshot for small open models, from an aggregator mirroring BFCL v4 (Tier B, dataset dated 2025-07-17, https://atlas.kevinhu.io/benchmarks/bfcl-v4-overall-accuracy): **Nanbeige4-3B-Thinking-2511 51.4**, Qwen3-32B 48.7, **Qwen3-8B 42.6**, **Qwen3-30B-A3B-Instruct-2507 41.4**, Qwen3-14B 41.0, **Qwen3-4B-Instruct-2507 35.7**, Command R7B 32.1, Llama-3.3-70B 31.9, **Gemma-3-12B 30.4**, Phi-4 28.8, Qwen3-1.7B 28.4, Mistral-NeMo 27.6. Frontier hosted models sit at 63-78 for scale.
- A second transcription of the leaderboard (Tier B, https://note.com/wayne_chang/n/n7e9ad028dcdc) adds the tool-specialists: **xLAM-2-8b-fc-r 46.56**, xLAM-2-3b-fc-r 40.68, watt-tool-8B 38.69, xLAM-2-1b-fc-r 34.05 (xLAM-2 is CC BY-NC 4.0 - non-commercial), Granite-3.1-8B 26.35, and **Phi-4-mini-instruct (FC) 11.05 with 39.96 s average latency** - i.e. its native FC path was effectively broken in that harness.
- Nanbeige's own reports put **Nanbeige4-3B-Thinking-2511 at 53.8** and Qwen3-4B-2507 at 44.9, Qwen3-8B at 42.2, Qwen3-30B-A3B-2507 at 48.6 (self-reported, Tier B, https://arxiv.org/html/2512.06266v1, Dec 2025); the HF card claims "#25 overall ... among the top 10 open-source models" (https://huggingface.co/Nanbeige/Nanbeige4-3B-Thinking-2511). The follow-up **Nanbeige4.1-3B reports 56.50** (Tier B, https://arxiv.org/html/2602.13367, Feb 2026). **Caveat [inference]:** these are *thinking* models; on a 10 tok/s CPU box a 500-token reasoning preamble is ~50 s before the first tool call, so their BFCL lead is bought with wall-clock the owner does not have.
- **Local numbers come in below API numbers.** BFCL maintainers' issue #1109: Qwen3-8B-FC scored 66.34% via API but 63.16% via local inference (same code), with multi-turn falling from 0.39 to 0.26 (Tier A, https://github.com/ShishirPatil/gorilla/issues/1109, 2025). **[recommendation]** treat every leaderboard number as an upper bound for a Q4 GGUF on this box.
- Two secondary "small-model tool-calling" write-ups disagree sharply: one (Tier C, https://d-central.tech/local-llm-agent-capability/, mid-2026) says reliability "falls off a cliff below about 4B" and calls Phi-4-mini "the safest single pick"; another (Tier C, https://www.ertas.ai/blog/on-device-tool-calling-2026-qwen3-gemma4-phi4) quotes "high 80s" composites it labels illustrative. Given the 11.05 FC score above, **neither is load-bearing**; only a local probe is.

### 4.3 Per-model notes (native template? server support? known bugs?)

| Model (instruct variant) | Native tool template | llama.cpp / Ollama / LM Studio support | Known tool-call bugs (issue tracker) | Grade |
|---|---|---|---|---|
| **Qwen3-8B / Qwen3-4B-Instruct-2507** | yes (Hermes-style `<tool_call>` JSON) | llama.cpp native Qwen/Hermes handler; Ollama library `qwen3` has `tools`; `enable_thinking` toggle | Ollama: `/v1` streaming dropped tool deltas for some clients (see 3.1); thinking-mode preambles before `<tool_call>` are the recurring failure class | **B, corroborated** |
| **Qwen3.5-4B / 9B** (Mar 2026; hybrid Gated-DeltaNet, 3:1 linear-attention -> near-constant KV memory) | yes; Ollama tags `vision tools thinking` | Ollama `qwen3.5:9b-q4_K_M` = 6.6 GB (Tier A, https://ollama.com/library/qwen3.5:9b-q4_K_M); 4B Q4_K_M 2.6-2.7 GB (Tier B, https://huggingface.co/jc-builds/Qwen3.5-4B-Q4_K_M-GGUF) | llama.cpp `peg-native` parser 500s when text precedes `<tool_call>` or on multiple `<tool_call>` blocks; upstream template `\|items` Jinja bug; single-tool-call template workaround (Tier A, https://github.com/ggml-org/llama.cpp/issues/20260 and https://github.com/ggml-org/llama.cpp/issues/21158, 2026). GGUF/Ollama compat issues in Mar 2026 needing newer Ollama (Tier C, https://uravation.com/media/qwen35-local-pc-guide/) | **B, but pin build; probe** |
| **Ministral 3 3B / 8B** (Dec 2025, Apache-2.0, 256k ctx, includes 0.4B vision encoder) | yes ("native function calling and JSON outputting") | official Mistral GGUFs: 3B Q4_K_M **2.15 GB**, 8B Q4_K_M **5.2 GB** (Tier A, https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF, https://huggingface.co/mistralai/Ministral-3-8B-Reasoning-2512-GGUF); Ollama `ministral-3` needs >= 0.13.1 (Tier A, https://ollama.com/library/ministral-3:8b-instruct-2512-q4_K_M); LM Studio 0.4.0 added support | no BFCL v4 number found - **UNVERIFIED** accuracy | **B for support, C for accuracy** |
| **Gemma 4 E2B / E4B** (2026; Apache-2.0) | yes, but a *custom DSL* `<\|tool_call>call:name{k:<\|"\|>v<\|"\|>}<tool_call\|>` (Tier A, Ollama renderer https://github.com/ollama/ollama/blob/d319227d/model/renderers/gemma4.go; Google docs https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4) | Ollama has a dedicated renderer; llama.cpp/LM Studio parser status per build | HF forum catalogue of template/parser bugs across Ollama 0.20.0-rc1 -> 0.30.x, stale GGUF templates, streaming-delta parsers (Tier B, https://discuss.huggingface.co/t/gemma-4-bug-fixes-and-research-request/176979). Gemma **3** had no tool role at all (Tier A, https://github.com/ollama/ollama/issues/9680) | **C until probed** |
| **gpt-oss-20b** (21B total / 3.6B active, MXFP4) | yes (harmony format; "should only be used with the harmony format") | Ollama `gpt-oss:20b` = **14 GB**, "as little as 16GB memory" (Tier A, https://ollama.com/library/gpt-oss:20b; https://huggingface.co/openai/gpt-oss-20b); llama.cpp and LM Studio were launch partners (Tier A, https://openai.com/index/introducing-gpt-oss/) | CPU: "high-effort reasoning on CPU means minutes of thinking" (Tier C, https://lumadock.com/tutorials/ollama-gpt-oss); no parallel tool calls in some servers (Tier C) | **B**; Tier L only |
| **Granite-4.0-h-tiny** (7B-A1B hybrid Mamba-2/MoE) | yes (`<tool_call>` XML) | Q4_K_M **4.30 GB** (Tier A, https://huggingface.co/bartowski/ibm-granite_granite-4.0-h-tiny-GGUF); llama.cpp templates `granite-4.0`/`granite-4.1` in README | template mis-detected as Hermes until PR #16526 (Oct 2025); non-jinja role bug fixed b8634 (Tier A, https://github.com/ggml-org/llama.cpp/issues/16415, https://github.com/ggml-org/llama.cpp/pull/20804) | **B support; accuracy UNVERIFIED** (only Granite-4.0-350m appears in BFCL supported models) |
| **Phi-4-mini-instruct** (3.8B, MIT) | yes (function-call tokens) | Q4_K_M ~2.3-2.5 GB (Tier B) | BFCL v4 FC 11.05 / 40 s latency in the official harness (above) | **C - probe before trusting** |
| **Llama-3.1-8B-Instruct** | yes (Llama 3.x, incl. builtin tools) | llama.cpp native handler (function-calling.md); Q4_K_M **4.92 GB** (Tier B, https://localmodel.run/model/qwen3-8b cross-ref; bartowski) | Ollama users report it "describes tool usage instead of executing" via `/v1` (Tier B anecdote, https://github.com/Gitlawb/openclaude/issues/433) | **B** |
| **Qwen2.5-7B-Instruct** | yes | listed as a *native-support* example in llama.cpp docs: `llama-server --jinja -fa -hf bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M` (Tier A, function-calling.md); Q4_K_M **4.68 GB** | none prominent | **B (older, stable)** |
| **Hermes-3-Llama-3.1-8B** | yes (needs `--chat-template-file ...Hermes-3...tool_use.jinja`) | llama.cpp example command in function-calling.md (Tier A) | template must be overridden | **B** |
| **xLAM-2-8b/3b/1b-fc-r** | yes (FC specialists) | BFCL v4 46.56 / 40.68 / 34.05 (Tier B) | **CC BY-NC 4.0** - licence lock for anything commercial; GGUF template support UNVERIFIED | **C (licence)** |
| **Qwen3-30B-A3B-Instruct-2507 / Qwen3-Coder-30B-A3B** | yes | Q4_K_M **18.6 GB** / 17.3 GB (Tier B, https://huggingface.co/unsloth; https://ahelpme.com/...) | same Qwen3 parser class as above | **B**; Tier L only |
| Gemma 3 (any size) | **no** tool role | Ollama returns 400 "does not support tools" (Tier A, issue #9680); llama.cpp Generic fallback only | - | **do not shortlist** |

**Cross-cutting [inference]:** every 2026 tracker failure above is a *parser/template* failure on a *thinking* model or a *new* template - exactly the two axes a capability probe can detect in seconds (send a canary tool with thinking disabled; then with thinking enabled; check for structured `tool_calls` and `finish_reason == "tool_calls"`). Accuracy differences between Qwen3-8B (42.6) and Qwen3-4B (35.7) matter less on this box than the 2x RAM/2x speed difference between them.

## 5. RAM-budgeted shortlist

How to read the table: **RAM** = working set at the stated context with f16 KV (q8_0 KV in brackets), computed as section 2 (weights from the cited source; KV from the model's published layer/kv-head counts; +0.6-0.8 GB runtime) - **[inference]** unless a source is cited for the total. **tok/s class** = single-stream decode on a dual-channel DDR4-3200 -> DDR5-5600 consumer box, from the bandwidth rule in section 2 - **[inference]**, and thinking models spend that budget on reasoning tokens first. **Tool reliability** = section 4 grade (A/B/C, with the source). Tier L rows exceed the briefed budget and are gated on a live free-RAM check.

| Tier | Model | Quant | RAM (working set) | tok/s class (CPU) | Tool-call reliability | Source(s) |
|---|---|---|---|---|---|---|
| S | **Qwen3-4B-Instruct-2507** (non-thinking) | Q4_K_M, 2.5 GB | ~4.3 GB @8k (3.7 q8 KV); ~6.5 GB @24k | 14-26 | **B** - native Hermes-style template, BFCL v4 35.7-44.9 | https://atlas.kevinhu.io/benchmarks/bfcl-v4-overall-accuracy; https://arxiv.org/html/2512.06266v1; sizes https://huggingface.co/Qwen/Qwen3-8B-GGUF (family) |
| S | **Qwen3.5-4B** (thinking toggle; hybrid linear attention) | Q4_K_M, 2.6-2.7 GB | ~3.6-4.0 GB even @32k (only 8 of 32 layers keep a KV cache) [inference] | 14-24 | **B, pin build** - native tools; llama.cpp PEG-parser bugs with text-before-`<tool_call>` and multi-call (2026) | https://huggingface.co/jc-builds/Qwen3.5-4B-Q4_K_M-GGUF; https://github.com/ggml-org/llama.cpp/issues/20260; https://github.com/ggml-org/llama.cpp/issues/21158 |
| S | **Ministral-3-3B-Instruct-2512** | Q4_K_M, 2.15 GB (+ optional vision mmproj) | ~3.8 GB @8k [inference] | 16-28 | **B support / C accuracy (no BFCL number found)** | https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF; https://ollama.com/library/ministral-3:8b-instruct-2512-q4_K_M |
| S | Nanbeige4.1-3B / Nanbeige4-3B-Thinking-2511 | Q4_K_M, ~2.5 GB [inference from 4B params] | ~4.3 GB @8k [inference] | 14-26 minus thinking preamble | **B accuracy (BFCL v4 51.4-56.5, partly self-reported) / C support (GGUF template support UNVERIFIED)** | https://huggingface.co/Nanbeige/Nanbeige4-3B-Thinking-2511; https://arxiv.org/html/2602.13367 |
| S | Phi-4-mini-instruct | Q4_K_M, ~2.5 GB | ~4.2 GB @8k [inference] | 14-26 | **C** - BFCL v4 FC 11.05 with 40 s latency in the official harness | https://note.com/wayne_chang/n/n7e9ad028dcdc (transcribes https://gorilla.cs.berkeley.edu/leaderboard) |
| M | **Qwen3-8B** (`/no_think` or `enable_thinking=false`) | Q4_K_M, 5.03 GB | ~7.0 GB @8k (6.4 q8 KV); ~8.2 GB @16k; third-party calc: "~6.5 GB @4k" | 7-13 | **B, corroborated** - BFCL v4 42.6; local-vs-API gap documented | https://huggingface.co/Qwen/Qwen3-8B-GGUF; https://localmodel.run/model/qwen3-8b; https://github.com/ShishirPatil/gorilla/issues/1109 |
| M | **Qwen3.5-9B** | Q4_K_M, 5.7 GB (unsloth) / 6.6 GB (Ollama tag) | ~7.0-7.8 GB @32k [inference] | 6-12 | **B, pin build** (same parser class as 4B) | https://ollama.com/library/qwen3.5:9b-q4_K_M; https://benzene.ai/articles/qwen-3-5-small-models-on-device-ai/ |
| M | **Granite-4.0-h-tiny** (7B-A1B, hybrid Mamba-2) | Q4_K_M, 4.30 GB | ~5.5 GB @32k (Mamba state, near-zero KV) [inference]; third-party: "~8 GB system RAM" | **25-45** (1B active) [inference] | **B support (llama.cpp template fixed Oct 2025 / b8634) / accuracy UNVERIFIED** | https://huggingface.co/bartowski/ibm-granite_granite-4.0-h-tiny-GGUF; https://github.com/ggml-org/llama.cpp/pull/20804; https://bestllmfor.com/catalog/granite4-tiny/ |
| M | Ministral-3-8B-Instruct-2512 | Q4_K_M, 5.2 GB | ~7.5 GB @8k [inference]; vendor: "< 12 GB quantised" | 7-12 | **B support / C accuracy** | https://huggingface.co/mistralai/Ministral-3-8B-Reasoning-2512-GGUF; https://huggingface.co/bartowski/mistralai_Ministral-3-8B-Instruct-2512-GGUF |
| M | Llama-3.1-8B-Instruct | Q4_K_M, 4.92 GB | ~6.8 GB @8k | 7-13 | **B** - native Llama 3.x handler; anecdotal `/v1` text-instead-of-call reports | https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md; https://github.com/Gitlawb/openclaude/issues/433 |
| M | Qwen2.5-7B-Instruct | Q4_K_M, 4.68 GB | ~6.0 GB @8k (28 layers x 4 KV heads -> 57 KB/token) | 8-14 | **B** - llama.cpp docs' own native-support example | https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md |
| M | xLAM-2-8b-fc-r | Q4_K_M, ~4.9 GB [inference, Llama-3.1 base] | ~6.8 GB @8k | 7-13 | **B accuracy (BFCL v4 46.56) / C licence (CC BY-NC 4.0)** | https://note.com/wayne_chang/n/n7e9ad028dcdc; https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/SUPPORTED_MODELS.md |
| L | **gpt-oss-20b** (21B / 3.6B active) | MXFP4, 14 GB (Ollama) | ~15-16 GB; vendor: "as little as 16GB memory" | 10-20 minus reasoning | **B** - harmony-native tools/structured outputs; CPU reasoning "minutes" | https://ollama.com/library/gpt-oss:20b; https://huggingface.co/openai/gpt-oss-20b; https://lumadock.com/tutorials/ollama-gpt-oss |
| L | **Qwen3-30B-A3B-Instruct-2507** | Q4_K_M, 18.6 GB | ~20-21 GB @8k (48 layers x 4 KV heads -> 98 KB/token) | 10-25 (measured 10.6 on DDR4-2400) | **B** - BFCL v4 41.4-48.6 | https://inventivehq.com/blog/moe-on-cpu-benchmark; https://atlas.kevinhu.io/benchmarks/bfcl-v4-overall-accuracy |
| L | Qwen3-Coder-30B-A3B-Instruct | Q4_K_M, 17.3 GB | ~19-20 GB @8k | 10-25 (42 on 12-ch DDR5) | **B** - coder-agentic tuned; same parser class | https://ahelpme.com/ai/llamacpp-ai/llama-bench-the-qwen3-coder-30b-a3b-and-amd-epyc-9554-cpu/ |
| - | Gemma 3 (any) | - | - | - | **exclude** - no tool role; Ollama 400 | https://github.com/ollama/ollama/issues/9680 |
| ? | Gemma 4 E4B | Q4_K_M, ~2.5-3 GB [inference] | ~4.5 GB [inference] | 14-24 | **C until probed** - custom tool DSL; 2026 parser-bug catalogue | https://github.com/ollama/ollama/blob/d319227d/model/renderers/gemma4.go; https://discuss.huggingface.co/t/gemma-4-bug-fixes-and-research-request/176979 |

**Picks [recommendation]:**
- **Default Tier S:** Qwen3-4B-Instruct-2507 Q4_K_M with thinking off - best-documented template, smallest bug surface, ~4 GB. Keep Qwen3.5-4B as the *probe-gated* successor (its linear-attention KV is the real RAM win for long tool loops), promote only when the layer's canary passes on the pinned build.
- **Default Tier M:** Qwen3-8B Q4_K_M with thinking off (~7 GB), or **Granite-4.0-h-tiny** when speed matters more than BFCL (1B active -> 2-3x the tok/s of a dense 8B at 4.3 GB of weights) - but its accuracy is unmeasured, so it enters via the eval harness, not by fiat.
- **Tier L** only behind a free-RAM gate (>= 22 GB free measured, not assumed): Qwen3-30B-A3B-Instruct-2507 is the one model class where "31.6 GB RAM, no GPU" beats a 16 GB-VRAM GPU box on quality-per-second.
- **Never shortlisted on this box:** dense >= 12B (Gemma-3-12B, Qwen3-14B: 7-9 GB weights *and* 3-5 tok/s), anything without a native tool template, anything with a non-commercial licence for the owner's paid work (xLAM-2 stays a benchmark reference only).

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
