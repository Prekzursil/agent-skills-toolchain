<!-- verbatim final report of background subagent a8a70bc26f3ed8afb, saved 2026-09-19 -->

## Directions
Sources were checked on 2026-09-19 and are listed in the legend at the end. "est." marks my own unverified estimate.

### 1. Premise refuted: a hosted provider already serves this exact model
- What: The Hub API returns `"inference": "warm"` and `inferenceProviderMapping: {"featherless-ai": {"status": "live", "task": "conversational"}}` for `heretic-org/Qwen3.8-27B-heretic-ara` [H]. Any OpenAI client can call `https://router.huggingface.co/v1` with model `heretic-org/Qwen3.8-27B-heretic-ara:featherless-ai`. The API lane needs no Space.
- Why it matters: There is no boot and no lease, and the weights are FP8 rather than NF4.
  - Featherless lists tools support and "Input $1.6 / Cached $0.15 / Output $12" per 1M tokens [F].
  - Its Developer plan ($50 monthly credit) allows agents and 256K context [F].
  - Its $25 flat "Chat" plan is unlimited but "human typed interactive chat use only", 32K [F].
  - PRO's $2 monthly credit covers HF-routed calls with no markup [IP].
- Feasibility: The listing is verified. Unverified: tok/s, HF-routed price and context, and `reasoning_effort`/`preserve_thinking` pass-through. Lost: sampling knobs. Prompts leave HF ("never stored" per [F]), and the model could be delisted.
- Effort: S.
- Decision: (a) HF-routed per-token, (b) Featherless direct, or (c) self-host only? I recommend (a) as a trial and standing fallback. Trade-off: $12/M output is no cheaper than #4 at volume, and it is a third party.

### 2. Thin CPU front-end, pluggable OpenAI-compatible backend
- What: All generation passes one seam, `_gpu_generate()` (`app.py:527`), shared by the UI and `api_generate` (`app.py:532`). Add a `BACKEND_URL` secret; when it is set, skip model loading and stream from that endpoint. The UI, agent loop, file bench, MCP and `/v1` stay.
- Why it matters: Boot falls from ~5 min to seconds on free CPU Basic. The second agent's pushes stop taking inference down (A1/A2). Every other option becomes configuration.
- Feasibility: Gradio 6.26 ships `gr.load_chat(base_url, model, token)` (`gradio/external.py:839`). The text-markup tool parser survives if the backend returns raw text. ZeroGPU can stay as a second Space, since PRO hosts 10 [Z].
- Effort: M.
- Decision: one codebase with a backend switch, or separate UI and worker Spaces? I recommend the switch. Trade-off: two code paths to test.

### 3. Build the pre-quantized checkpoint on HF Jobs, not inside a lease
- What: Replace A5's in-lease export with a one-off Job on `l40sx1`: $1.80/h billed per minute, read-only model mounts, per-job encrypted secrets, 30-minute default timeout [J]. Est. under $1, inside PRO's $2 credit.
- Why it matters: It removes the quantize-at-boot that races the ~300 s restart (A4). It also takes the write token out of production (A5/A7).
- Feasibility: The mechanics are verified. Pre-quantized bnb loading under ZeroGPU's CUDA emulation is unverified. Community quants of this fine-tune already exist [Q], with quality unaudited:
  - a 22 GB GPTQ "verified on vLLM 0.27.1" for text, vision and MTP;
  - a GGUF Q4_K_M at 16.8 GB plus mmproj.
- Effort: S.
- Decision: self-built or community checkpoint? I recommend self-built for serving and community GGUF for trials.

### 4. A real engine on HF GPUs, only while you work
- What: vLLM lists `Qwen3_5ForConditionalGeneration`. Its Qwen3.8-27B recipe drives the in-checkpoint MTP head (`--speculative-config '{"method":"mtp","num_speculative_tokens":3}'`, acceptance 0.77-0.90) [V]. SGLang runs it too [K]. Transformers discards that head (`modeling_qwen3_5.py:807`: `_keys_to_ignore_on_load_unexpected = [r"^mtp.*"]`). There are three wrappers at one price, L40S-48GB $1.80/h (RTX PRO 6000 96GB $2.75/h):
  - A Jobs session: `--expose 8000` gives a token-gated `https://<job>--8000.hf.jobs`, and `--timeout 2h` caps spend [J].
  - An Inference Endpoint with scale-to-zero: 15 min idle, 502 while waking, no queue, billed while initializing [IE].
  - A Docker Space with sleep time [G].
- Why it matters: est. 35 tok/s plain and 60-70 with MTP on L40S. I scaled this from measured 11.5→22 tok/s on DGX Spark [K] and 12.2→27 on Strix Halo [Q]. That is about $7-10 per 1M output tokens while generating. ZeroGPU overage costs $185 per 1M ($1 per 10 min [Z] at 9 tok/s).
- Feasibility: Cold start est. 5-10 billed minutes. It needs #2 and #3.
- Effort: M.
- Decision: Jobs session, Inference Endpoint, or Docker Space? I recommend Jobs sessions. Trade-off: each session gets a new URL, so the front-end needs a start-session control.

### 5. Compute outside HF: home GPU, Modal, RunPod
- What: Run `llama-server` (OpenAI-compatible, `--jinja`, `--api-key`) with an existing GGUF, either on the owner's machine behind Cloudflare Tunnel/Tailscale or on a rented GPU.
  - Modal: L40S at $0.000542/s ($1.95/h), billed per second, scale-to-zero, with $30/month free compute [M]. That is about 15 L40S-hours, est. 3M output tokens. The whole ZeroGPU quota yields ~0.65M/month.
  - RunPod community pods: RTX 4090 $0.34/h, A40-48GB $0.35, L40S $0.79 [R]. These are the cheapest, but they never scale to zero.
- Why it matters: A Strix Halo APU measures Q4_K_M at 12.2 tok/s, or 27-28 with MTP [Q], which is 3x the Space. A 24 GB NVIDIA card should pass 40 tok/s plain (est.). The Windows scheduled tasks (F6) show a machine exists.
- Feasibility: Prices are verified. The home GPU is unknown; under 16 GB VRAM means single-digit tok/s. Modal cold start is unverified. Lost: availability when the PC is off. Data leaves HF, so check each acceptable-use policy.
- Effort: S-M.
- Decision: home GPU, Modal, RunPod, or HF-only? I recommend the home GPU as fallback. Add a vendor only if #4's cold start hurts.

### 6. Re-scope ZeroGPU instead of stretching it
- What: ZeroGPU is "exclusively compatible with the Gradio SDK" with no `torch.compile` [Z], so eager transformers is the only engine. That has three costs:
  - MTP goes unused.
  - 48 of 64 GatedDeltaNet layers run the torch fallback unless `fla`/`causal_conv1d` are installed (`modeling_qwen3_5.py:199-248`). They are absent from `requirements.txt`; the image contents are inferred.
  - Every fresh worker re-uploads the 22.3 GB pack (`spaces/zero/wrappers.py:154`).
- Why it matters: The ~9 tok/s ceiling is largely structural. 40 min/day is ~21.6k tokens.
- Feasibility: In-place gains are unverified.
- Effort: S.
- Decision: ZeroGPU for everything, short chat only, or retire? I recommend short chat only. Never buy overage: it is $6/h for half an RTX Pro 6000 [Z], against $2.75/h for a whole one [J].

## Killed ideas
- vLLM/llama.cpp inside ZeroGPU: it is PyTorch-only with forked per-lease workers (`wrappers.py:59`), so weights reload every lease.
- GGUF on CPU Spaces: CPU Basic's 16 GB RAM is below the 16.8 GB Q4_K_M. CPU Upgrade fits, at est. 2-3 tok/s.
- Dedicated L40S with today's code: it runs unchanged (`spaces/zero/decorator.py:98` no-ops the decorator) but costs est. $35-55/M.
- Always-on A100/H100: $1,800-3,240/month for one user.
- The Windows runtime binary in a community NVFP4 repo: unaudited.

## Biggest unknown
- The fact: how Featherless actually serves this model. That covers decode tok/s, served context, tool-call and thinking-kwarg fidelity, and HF-routed price.
- The cheapest way to learn it: one streamed request through `router.huggingface.co` with the owner's token answers all four for cents. A bad result drops #1 to last and promotes #4.
- Runner-up: the home machine's GPU.

Legend.
- Code: `/tmp/claude-1000/-workspaces-agent-skills-toolchain/ca9aa7a4-16ad-4e9d-bafe-00eed0171063/scratchpad/space-latest/app.py`.
- Library refs: `/tmp/claude-1000/-workspaces-agent-skills-toolchain/ca9aa7a4-16ad-4e9d-bafe-00eed0171063/scratchpad/libsrc/` (`transformers/transformers/models/qwen3_5/`, `spaces/spaces/zero/`, `gradio/gradio/`).
- [Z] huggingface.co/docs/hub/spaces-zerogpu
- [G] huggingface.co/docs/hub/spaces-gpus
- [J] huggingface.co/docs/hub/jobs-pricing and /jobs-configuration
- [IE] huggingface.co/docs/inference-endpoints/autoscaling and /pricing
- [IP] huggingface.co/docs/inference-providers/pricing
- [H] huggingface.co/api/models/heretic-org/Qwen3.8-27B-heretic-ara?expand[]=inferenceProviderMapping
- [F] featherless.ai/models/heretic-org/Qwen3.8-27B-heretic-ara and featherless.ai/pricing
- [V] docs.vllm.ai/en/latest/models/supported_models.html and recipes.vllm.ai/Qwen/Qwen3.8-27B
- [K] blog.kubesimplify.com/qwen3-8-27b-on-dgx-spark
- [Q] Hub cards JC1DA/Qwen3.8-27B-heretic-ara-INT4-INT8-GPTQ, cygnal/Qwen3.8-27B-heretic-ara-Q4_K_M-MTP-GGUF, mradermacher/Qwen3.8-27B-heretic-ara-GGUF
- [M] modal.com/pricing
- [R] runpod.io/pricing

Nothing was modified. The live Space was never contacted, and only read-only Hub tools were used.