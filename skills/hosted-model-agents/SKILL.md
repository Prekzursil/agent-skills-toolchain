---
name: hosted-model-agents
description: Deploy hosted or local models as agent runtimes (Hugging Face router + Hub MCP + Spaces + Endpoints, Modal/RunPod/Lightning, Azure Foundry, Ollama/LM Studio/llama.cpp, Cursor Max/auth2api), register them once in .agents/models.json, reach them via the inference-hub MCP (models_list / chat / chat_many) or provider blocks, then attach tool loops for agent work. For choosing where to run a model, wiring OpenAI /v1 or Gradio MCP, or Hub MCP vs inference HTTP. Any chat model that emits tool_calls.
metadata:
  status: active
  valid_as_of: 2026-09-02
---

# Hosted model agents (environment + tools, not one model)

**Job:** pick an **environment**, deploy a **runtime**, then give an **agent persona** tools. The model family (Qwen, Llama, GPT, Grok, ...) is a checkpoint choice, not the skill.

Three layers. Mixing them is how the last pass went wrong.

| Layer | What it is | Estate surface |
|---|---|---|
| **Control plane** | Search, push, Spaces CRUD, papers, Hub files | Hugging Face **Hub MCP** `huggingface` (`https://huggingface.co/mcp?login`). Claude-targeted in `agents.json`. Reuse `HUGGINGFACE_TOKEN` / `HF_TOKEN`. |
| **Runtime** | Something that runs weights and speaks chat | HF **router** `/v1`, Space Gradio UI, Space OpenAI `/v1`, Inference Endpoint / TGI / vLLM, Modal GPU fn, Foundry deploy, local Ollama / LM Studio / llama-server, Cursor Max |
| **Harness** | Who **executes** tools and who **prompts** the agent | Local Cursor/Claude/Codex process. Allowlist + schema. Persona = system prompt pack, not a new MCP. |

Read [environments.md](environments.md) for where to deploy, [tool-loop.md](tool-loop.md) for how to give tools, [profiles.md](profiles.md) for red-team / learner / coder packs, [evals.md](evals.md) for the eval gate.

## Hard rules

1. **Hub MCP is first-class for Hugging Face as an environment.** Use it (or the official HF plugin where mounted) for Hub work. Do not invent a second Hub MCP. Cursor may not mount it (`targets: claude`) - then use `huggingface_hub` / Hub HTTP with the same token, not a fake server.
2. **An inference URL is not Hub MCP.** A router model, a Space `/v1/chat/completions` or a TGI endpoint is a **runtime**. Call it with process-local HTTP (OpenAI SDK, a small wrapper) or through `inference-hub`. Do not register every GPU URL in `agents.json` as MCP - that explodes the tool catalogue (`mcp-fleet-curation`) and is the wrong layer. The ONE inference MCP row is `inference-hub`; endpoints and models live in `.agents/models.json`, never as more MCP rows.
3. **The hosted model proposes; the harness executes.** `tool_calls` come back over HTTP/MCP. Shell, files, HexStrike, browsers stay **local** after allowlist + JSON-schema checks. Do not grow a remote shell on a Space to "make tools work." Do not let the router execute remote MCP tools for you (see [tool-loop.md](tool-loop.md)).
4. **Personas are prompt packs**, not skills named after a checkpoint. One runtime can host a red-team reporter, a literature learner, or a coding worker by swapping `messages[0]` and the `tools` list.
5. **G-32 is Cursor-quota wrapping, not "ban HF MCP."** G-32 = `ai-mode` / `*-cursor` stay process-local to auth2api `:8317`; no persistent global Cursor-bridge env. Hugging Face Hub MCP is unrelated. G-36 = at most one `cursor-agent` process (RAM). Neither lock forbids deploying models on HF.

GPU rental / cloud-hub multiplex: skill `cloud-infra-toolchain`. Azure model deploy: `microsoft-foundry`. Action-space design: `agent-harness-construction`. OpenRouter is a spend-capped sidecar only - never Cursor BYOK (`openrouter-routing`, lock L1). All estate locks in one place: `docs/plans/estate-locks.md`.

## Registry + hub (architecture as of 2026-09-02)

- **`.agents/models.json` is the SSOT of endpoints and models.** Closed schema (`endpoints{}`, `models{}`, `aliases{}`, `slots{}`, `locks[]`, `policy`). Secrets by NAME only: an endpoint's `auth.env` names an environment variable (the HF router row names `HUGGINGFACE_TOKEN_INFERENCE`); no value ever appears in the registry, a rendered config, a log or a doc (L6). Capability lattice per endpoint and model: `native > probed > declared > emulated > absent` for `wire.*` and `features.*`; model rows may only override downward. Every row carries `targets{}` for all ten runtimes, `denyCallers[]`, `resource.ramBytes` and its `locks[]`. Validator: `.agents/scripts/models_control_plane.py` (rule ids V1-V20) with the CLI `.agents/scripts/validate_models_control_plane.py`.
- **`inference-hub` is the ONE door for the MCP-only runtimes** Claude Code, Cursor, Agy and Gemini CLI. It lives in `tools/mcp/inference-hub/`, listens on `127.0.0.1:8901`, and exposes an MCP face (`POST /mcp`, tools `models_list`, `chat`, `chat_many`, `probe`, `budget_status`) plus an OpenAI `/v1` face (`GET /v1/models`, `POST /v1/chat/completions`, `GET /healthz`). Use: `models_list` first, then `chat model="glm-5.3"` (model id, `id@endpoint`, or an alias); `chat_many` for fan-out (`{requests: [...]}` or `{prompt, models: [...], n}`; per-endpoint semaphores, no head-of-line blocking). One `chat` = exactly one model round; the caller executes `tool_calls`. The request never accepts `base_url`, `api_key`, `provider` or `headers`; the hub refuses prompts that contain a credential value (`REFUSED_SECRET_IN_PROMPT`). Lazy start: the stdio shim `.agents/scripts/inference_hub_stdio.py` (the `agents.json` row) starts the hub on first call, idle-exit 600 s, one resident process at most (the bind on 8901 is the mutex, L4).
- **Native runtimes take rendered provider blocks, not the hub.** Codex, Grok, Goose, OpenCode, Aider and Fabric get their provider/model blocks rendered from the registry by `.agents/scripts/merge_generated_<runtime>_models.py` (shared module `.agents/scripts/models_materialize_common.py`). Dry run is the default; `--write` is explicit and per runtime; `--check` reports drift; only managed blocks are touched; secrets are rendered as each runtime's own env-reference syntax. Codex is rendered last: its renderer floors `wire.responses >= probed`, never writes `wire_api = "chat"`, and smoke-tests `codex --version` with a rollback. Cloud agents never run `--write` against a real config.
- **Routing policy + PACE live in `.agents/routing-policy.json`** (validator `.agents/scripts/routing_policy.py`): per task class `primary`, `escalate_to[]`, `floors{}`, `exponents{quality, speed, cost}`, `spend_share`, `pace {P, A, C, E, triggers[]}`, `justification`. Names only; every name must exist in the registry; the PACE rungs must be distinguishable means (at most one `cursor-*` rung, at least one non-network rung, `E` = `basic-memory :8765` + `agent-mail :8812` handoff); OpenRouter rungs only in CLI/Codex task classes (L1).
- **Gone: `glm53-space` and `qwen-space`.** D1 = hard delete (2026-09-02): the `glm53-space` MCP row and `tools/mcp/glm53-space` are removed; `merge_generated_cursor_mcp.py` lists `glm53-space` as retired and `inference-hub` took its Cursor safe-default adapter slot. The capability is kept (L7) as model `glm-5.3` on endpoint `hf-router` (remote id `zai-org/GLM-5.3:zai-org`): `chat model="glm-5.3"` through the hub. The `qwen-space` wrapper and the `qwen-space-tool-api` skill are not on this branch; where a box-side copy still exists it is a tombstone that points here. Do not re-create either as an MCP server.

## One-line decision

- Need Hub search / Space metadata / papers -> **HF Hub MCP** (or Hub CLI).
- Need tokens out of a GPU -> **runtime `/v1` or Gradio**; from Claude / Cursor / Agy / Gemini, always via **`inference-hub`**.
- Need a model in Codex / Grok / Goose / OpenCode / Aider / Fabric -> **rendered provider block** from the registry.
- Need the agent to *do* something -> **local tools** + tool loop.

Worked HF Space OpenAI example (not the SSOT): [recipes/hf-space-openai.md](recipes/hf-space-openai.md). Provider-pinned featherless route for the abliterated/WRN offsec checkpoints (consumed by the consult-offsec MCP): [recipes/hf-router-featherless.md](recipes/hf-router-featherless.md). The four local Ollama offsec models at 64K context (route=local for cred-laden consults): [recipes/ollama-local.md](recipes/ollama-local.md).
