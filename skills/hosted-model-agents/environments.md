# Environments (where the weights run)

Pick the environment for **cost, privacy, GPU type, and API shape**. Then attach the harness tool loop ([tool-loop.md](tool-loop.md)). Every runtime below is a row in `.agents/models.json`; Claude / Cursor / Agy / Gemini reach all of them through `inference-hub`, native runtimes through rendered provider blocks ([SKILL.md](SKILL.md), "Registry + hub").

## Hugging Face

| Surface | Use for | How agents talk to it |
|---|---|---|
| **Hub MCP** (`huggingface`) | Models, datasets, Spaces, papers, Hub file ops | Official plugin/MCP. Already in `.agents/agents.json`, Claude target, `HUGGINGFACE_TOKEN`. Control plane only, never the chat runtime. |
| **Router `/v1`** (`https://router.huggingface.co/v1`) - the **default hosted path** | Any model listed by `GET /v1/models` (public, no token; 136 chat models on 2026-09-02); tools / JSON; zero fixed cost | Chat-only: `POST /v1/chat/completions` (plus a `/v1/responses` beta, see [tool-loop.md](tool-loop.md)). Model id suffix picks provider policy: no suffix = `:fastest` (highest measured tok/s), `:cheapest` (lowest output price), `:preferred` (your provider order), `:<provider>` pins one (`zai-org/GLM-5.3:zai-org`). `/v1/models` carries per-provider capability flags (`supports_tools`, `supports_structured_output`, pricing, TTFT) - read them, do not assume; pin a provider when `response_format` is attached. Billing: PRO includes $2.00 of monthly credits (Free $0.10), then pay-as-you-go at provider pass-through prices. Registry endpoint `hf-router`; `glm-5.3` lives here. |
| **Space - Gradio UI** | Humans, quick demos | Browser / Gradio client. Optional `mcp_server=True` (Gradio **4+**, `gradio[mcp]`) exposes *that app's* tools as MCP (app tools, not Hub). Bearer decides whose ZeroGPU quota is spent. |
| **Space - OpenAI `/v1`** on **ZeroGPU** | Private / abliterated checkpoint not on the router; bursty, low volume; PRO account | Mount FastAPI routes on Gradio `App.create_app`; keep generate under `@spaces.GPU`, protocol code GPU-free. ZeroGPU as recorded 2026-09-02: NVIDIA **RTX Pro 6000 Blackwell** slices, `large` = 48 GB / `xlarge` = 96 GB; Gradio SDK only, PyTorch 2.8+; per-caller quota **PRO 40 min/day** (Free 5 min), remaining quota drives queue priority; `@spaces.GPU` default **60 s** per call (`duration=` to change); overage on credits **$1 per 10 GPU-minutes**; hosting cap **10 ZeroGPU Spaces** on PRO. Private Spaces need the Bearer token. Wake latency from sleep: not measured yet ([evals.md](evals.md)). |
| **Inference Endpoints / TGI / vLLM** (dedicated) | Private checkpoint AND sustained load AND a client that can wait | Standard chat completions, same tool loop. Scale-to-zero contract as recorded 2026-09-02: idle timeout default **1 h**; while a replica cold-starts ("a few minutes") the proxy returns **503** unless the client sends `X-Scale-Up-Timeout: <seconds>` and accepts a held request; a **scaled-to-zero endpoint still counts against instance quota** (a paused one does not). Prices L4 $0.80/h, L40S $1.80/h, A100 $2.50/h as recorded; PRO credits may be spent here. |
| **Jobs / dedicated hardware** | Long train/eval | Hub MCP + Jobs docs; not a chat agent unless you add an API. |

Do **not** treat Hub MCP as the chat runtime. Do **not** skip Hub MCP and only document one private Space. Do **not** re-create `glm53-space`: that lane is hard-deleted; use `chat model="glm-5.3"` through the hub.

Auth, two NAMES, never values: Hub MCP keeps `HUGGINGFACE_TOKEN` (also seen as `HF_TOKEN` / `HUGGING_FACE_HUB_TOKEN`). Router inference uses **`HUGGINGFACE_TOKEN_INFERENCE`**, a separate HF **fine-grained** token with only the "Make calls to Inference Providers" permission and no repo rights; it is the only credential name the `inference-hub` row and the `hf-router` endpoint declare. **Never rotate the Hub token** (L6) - the split adds a name, it revokes nothing. Never print either.

## Other GPU clouds

Skill `cloud-infra-toolchain` (cloud-hub multiplexer): **Modal**, **RunPod**, **Lightning**, Kaggle, Azure/GCP ops. Those platforms **rent GPUs**; this skill **turns a GPU into an agent runtime** (OpenAI `/v1` or native SDK) and attaches tools locally.

## Azure AI Foundry

Skill `microsoft-foundry` / `deploy-model`. Hosted catalog models with Azure auth. Tool loop still local unless Foundry's own tool runtime is explicitly in scope.

## Local (the real box, corrected 2026-09-02)

The Windows 11 box has an **NVIDIA GeForce RTX 4050 Laptop GPU, 6 GB VRAM** (`nvidia-smi`: 6141 MiB total) and ~32 GB of chronically pressured RAM; the earlier "no GPU" premise was wrong. Rule of thumb from the audit: <= 8B at Q4 fits in VRAM, 14B+ does not.

| Server | Contract | Notes |
|---|---|---|
| **Ollama** (`http://127.0.0.1:11434/v1`) - primary | Weights on `D:\ai-models\ollama` (`OLLAMA_MODELS`); `qwen2.5:7b` is the proven 6 GB fit. User env: `OLLAMA_KEEP_ALIVE=2m`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`. Bind loopback only. | Tier S = `Qwen3-4B-Instruct-2507` (Q4, thinking off); Tier M = `Qwen3-8B` thinking off. Granite / Qwen3.5 / MoE only through the eval gate. `/v1` has `tools` but no `tool_choice`; `usage` only with `stream_options.include_usage`; native `/api/chat` is the safer tool path; `/api/show` exposes `capabilities`. |
| **LM Studio** (`http://127.0.0.1:1234/v1`) | Run the `llmster` daemon (headless, `lms daemon up`), not the GUI, so two processes never fight over 1234. JIT model load + auto-evict ON, idle TTL 600 s (the default is 60 min). Weights on `D:\ai-models\lmstudio`. | `tools` on `/v1/chat/completions` (parsed from text for models without a native tool format); `response_format` json_schema (weak below 7B); discovery `GET /api/v0/models` (legacy) or `/api/v1/*`. |
| **llama-server** (`http://127.0.0.1:8080/v1`) | Registry row `llamacpp`, `enabled: false`; not resident. | Enable only through the eval gate (D10 kept Ollama primary + LM Studio; vLLM/WSL2 is a skip). |

Every local row in the registry carries `resource.ramBytes`; the validator warns when the enabled local servers plus the largest enabled local model exceed `policy.localRamBudgetBytes`. Same tool loop as hosted. No Hub MCP involved. RAM tiers as CPU worst-case budgets: `docs/gem-hunt/2026-09-02-hosted-models/04-local-inference-ram-budget.md`.

## Cursor Max / Claude Max (not a deploy)

Native Cursor models and Claude Max are **subscription runtimes**, not HF. Cursor quota from a TUI uses **auth2api `:8317`** via process-local wrappers (`ai-mode`, `grok-cursor`, ...) - that is **G-32**; the registry row is `cursor-auth2api` (`kind: bridge`, `singletonKey: cursor-bridge`, `denyCallers` includes `cursor`, L3). Do not conflate with HF. Never point Claude's `ANTHROPIC_BASE_URL` at any of these (L1).

## App hosts (not model runtimes)

`vercel-deploy`, `netlify-deploy`, `cloudflare-deploy`, `render-deploy` ship **apps**. They are not "put Qwen on Vercel." **fly-deploy** is an audit *checkbox* for a Fly.io skill that was never written; do not invent it to green the harness audit unless the owner wants Fly.io.

## Checklist before you "just MCP it"

1. Is this Hub search? -> existing `huggingface` MCP / plugin.
2. Is this one app's Gradio tools? -> that Space's Gradio MCP, optional, scoped.
3. Is this chat completions? -> a registry row; `inference-hub` from MCP-only runtimes, a rendered provider block from native ones, or a process-local `/v1` client.
4. Would adding it to `agents.json` duplicate Hub MCP, duplicate `inference-hub`, or dump 50 tools into every turn? -> don't. `mcp-fleet-curation`.
