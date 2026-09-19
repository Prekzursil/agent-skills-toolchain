<!-- verbatim final report of background subagent a4749a80d6d0329ae, saved 2026-09-19 -->

## Directions

### 1. Serve a prebuilt block-FP8 of the same checkpoint instead of on-the-fly NF4
- What: Load transformers-native FP8 (`quant_method: fp8`, e4m3, 128x128 blocks) through `FineGrainedFP8Config`. The Triton kernel downloads from the Hub (`kernels-community/finegrained-fp8`), so nothing compiles. `magiccodingman/Qwen3.8-27B-heretic-ara-fp8`@`ae4c4a3` (30.9 GB) is that build of the owner's exact checkpoint.
- Why: Boot spends 4m14s quantizing 54 GB on CPU (runlog) and races the ~300 s restart. FP8 is also higher fidelity than NF4.
- Feasibility:
  - Verified: config and size.
  - Peer evidence: a public Space written for ZeroGPU uses this path (`limegreenpeper1/Chat-Qwen-Qwen3.8-27B-FP8`). Its source budgets 0.045 s/token and reports ~21 s fixed cost per call.
  - Trap, reproduced locally: the skip-list has 65 `...mlp.gate` entries that prefix-match `gate_proj` (LIB `quantizers/quantizers_utils.py:39`), so `gate_proj` stays unconverted. Filter those entries before loading.
  - Unverified: the decode gain (estimate 1.5-2.5x).
  - Cost: the pack grows from ~18 to ~30 GB, so cold leases cost more.
- Effort: S-M.
- Decision: Which artifact serves?
  - Options: on-the-fly NF4 / own prebuilt NF4 (the in-flight export; fixes boot only) / third-party FP8 pinned by sha / self-built FP8, built offline and not inside a production lease.
  - Recommend: third-party FP8 to measure, self-built to keep.
  - Trade-off: bigger per-lease transfer. Spot-check tensors against bf16 and set `trust_remote_code=False`.

### 2. Sparse sibling: Qwen3.6-35B-A3B, FP8 only
- What: Qwen3.8 has no small MoE (Hub lists 27B, 180B Flash-Next, 2.4T). The newest A3B is `Qwen/Qwen3.6-35B-A3B` (40 layers, 256 experts, 8 active). Verified same-style derivatives:
  - `trohrbaugh/Qwen3.6-35B-A3B-heretic-v2` (bf16)
  - `llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved` (bf16)
  - `protoLabsAI/Qwen3.6-35B-A3B-uncensored-heretic-FP8` (native FP8, 36.6 GB)
- Why: On this GPU class, llama.cpp Q8_0 measures 193 tok/s for A3B against 46 for dense Qwen3.6-27B, a 4.2x gap (jarvislabs.ai).
- Feasibility:
  - Verified blocker: experts are fused 3-D `nn.Parameter`s (LIB `models/qwen3_5_moe/modeling_qwen3_5_moe.py:732`), and bnb swaps only `nn.Linear` (`integrations/bitsandbytes.py:189`).
  - Consequence: NF4 leaves ~70 GB in bf16, which needs `xlarge` at 2x quota (as `artificialguybr/Qwen3.6-35B-A3B-zero` does).
  - Only FP8 (`FP8Experts`, `integrations/finegrained_fp8.py:588`) fits `large`.
  - Estimate 2-3x in this stack, which looks launch-bound rather than bandwidth-bound; untested.
- Effort: M.
- Decision: Trade quality for speed?
  - Evidence: official cards give SWE-bench Pro 49.5 (A3B), 53.5 (3.6-27B), 61.7 (3.8-27B).
  - Options: stay on 27B / A3B as default / A3B as a "fast" preset.
  - Recommend: the preset, gated by the harness in item 3.
  - Trade-off: weaker agentic coding and a 37 GB pack.

### 3. A 12-prompt, backend-agnostic eval harness
- What: A client script against the Space's own `/v1/chat/completions`, at temperature 0 with a 192-token cap.
  - Prompts: tool-call, JSON-schema, checkable-answer and one 8k-retrieval prompt.
  - Metrics: TTFT, decode tok/s, `finish_reason=="length"` rate, think-token share, GPU-seconds, and tool validity via the repo's `tool_parse.validate_tool_calls`.
  - Output: JSONL appended per run, keyed by model sha and quant.
- Why: "9.2 tok/s" exists only in a commit message, while the code assumes 22. Quota is per account, so a run must stay near 2k tokens (~4 min at 9 tok/s).
- Feasibility: Pure client code plus a `[timing]` log line like the FP8 peer Space.
- Effort: S.
- Decision: Where do quality checks run?
  - Options: production / a duplicate Space (same quota) / an off-ZeroGPU endpoint plus a 35 s speed probe in production.
  - Recommend: the last.
  - Trade-off: two environments to maintain.

### 4. Speculation: delete the dead draft; native MTP needs another runtime
- What: The 2B draft has never run.
  - The checkpoint ships MTP (15 `mtp.*` tensors in `model-auxiliary.safetensors`), but transformers drops them at load (LIB `models/qwen3_5/modeling_qwen3_5.py:807`).
  - Transformers also rejects assisted generation for stateful models (`:812`; `generation/utils.py:1578-1582`).
  - `_generate_kwargs` (SPACE `app.py:389-423`) swallows that error and retries plain.
- Why: The draft still costs 18 s of boot and ~4.5 of the 22.3 GB streamed per cold lease. The README's "up to ~2x" claim is false.
- Feasibility:
  - Verified in source.
  - MTP does work in llama.cpp: 45.8 to 79.4 tok/s for dense Qwen3.6-27B at Q8_0 on the same GPU (jarvislabs.ai).
  - MTP GGUFs of this checkpoint exist (`cygnal/Qwen3.8-27B-heretic-ara-Q4_K_M-MTP-GGUF`).
  - I found no evidence that llama.cpp can use a ZeroGPU GPU (docs: PyTorch-based).
- Effort: S to delete; L to change runtime.
- Decision: Stay on ZeroGPU?
  - Evidence: overage is $1 per 10 min ($6/h) at ~9 tok/s; a dedicated L40S is $1.80/h and can sleep when idle.
  - Options: stay / dedicated GPU with GGUF+MTP / hybrid.
  - Recommend: delete the draft now and revisit the runtime after measurements.
  - Trade-off: hourly billing.

### 5. Hard thinking budget
- What: `reasoning_effort` is only a system-prompt sentence, and `medium` adds nothing (checkpoint `chat_template.jinja`). Add a `LogitsProcessor` that forces `</think>` after N thinking tokens, and show think tokens per answer.
- Why: 2,000 thinking tokens take 3.7 min, which is 9% of the daily 40 min.
- Feasibility: Standard HF hook, untested here. The model card warns that low effort can raise retries in agentic loops.
- Effort: S.
- Decision: Default cap?
  - Options: none / 512 / 1024 / per preset.
  - Recommend: per preset, with thinking off for tool rounds.
  - Trade-off: truncated reasoning on hard tasks.

### 6. Overflow tier on a serverless provider
- What: The Hub API shows `featherless-ai` serving `heretic-org/Qwen3.8-27B-heretic-ara` live. Route overflow or tool rounds through `router.huggingface.co/v1`. A local `Qwen/Qwen3.5-9B` tier is the alternative.
- Why: Same weights, zero GPU quota, no boot. PRO includes $2/month, then pass-through pricing.
- Feasibility: The provider mapping is verified. Price, context cap, speed and template-kwarg support are unverified.
- Effort: S-M.
- Decision: Second tier?
  - Options: none / remote same checkpoint / local 9B (older generation, +6 GB pack).
  - Recommend: remote, opt-in.
  - Trade-off: prompts leave the private Space.

## Killed ideas
- NVFP4 in transformers: rejects pre-quantized checkpoints and needs a real sm100+ GPU at load (LIB `quantizers/quantizer_nvfp4.py:49,73`). ZeroGPU emulation defaults to capability 9.0.
- AWQ/GPTQ: need `gptqmodel` (`quantizers/quantizer_awq.py:49`), AWQ forces fp16, and there is no fused-expert support. Wheels are unverified.
- DFlash drafts (`z-lab/Qwen3.8-27B-DFlash2`): `speculation_type="dflash"` is wired for another model family, and stateful targets are still rejected.
- `Qwen/Qwen3.8-Flash-Next`: 180B parameters.
- `xlarge` for speed: 2x quota for at most 2x bandwidth in a launch-bound stack.
- CPU llama.cpp behind a dummy `@spaces.GPU` (seen in `apathy-exe/Qwen3.8-27B`): misuses the hardware class.

## Biggest unknown
The true decode rate on `large`, and where the time goes. Dense 27B reaches 46 tok/s at Q8_0 in llama.cpp on the full card, so ~9 tok/s at 4-bit is not a hardware limit. Decode runs pure-torch delta-rule code unless Hub kernels load (LIB `models/qwen3_5/modeling_qwen3_5.py:509-522`), and the `kernels` package is not installed. Cheapest test: one 128-token greedy lease with per-phase timing, NF4 versus FP8.

LIB = /tmp/claude-1000/-workspaces-agent-skills-toolchain/ca9aa7a4-16ad-4e9d-bafe-00eed0171063/scratchpad/libsrc/transformers/transformers; SPACE = /tmp/claude-1000/-workspaces-agent-skills-toolchain/ca9aa7a4-16ad-4e9d-bafe-00eed0171063/scratchpad/space-latest