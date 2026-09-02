---
name: hosted-model-agents
description: Deploy hosted or local models as agent runtimes in different environments (Hugging Face Hub MCP + Spaces + Endpoints, Modal/RunPod/Lightning, Azure Foundry, llama.cpp, Cursor Max/auth2api), then give them tools in the local harness. Use when choosing where to run a model, wiring OpenAI /v1 or Gradio MCP, attaching tool loops for red-team/learning/coding agents, or deciding Hub MCP vs inference HTTP. Not Qwen-specific — any chat model that emits tool_calls.
metadata:
  status: active
  valid_as_of: 2026-08-29
---

# Hosted model agents (environment + tools, not one model)

**Job:** pick an **environment**, deploy a **runtime**, then give an **agent persona** tools. The model family (Qwen, Llama, GPT, Grok, …) is a checkpoint choice, not the skill.

Three layers. Mixing them is how the last pass went wrong.

| Layer | What it is | Estate surface |
|---|---|---|
| **Control plane** | Search, push, Spaces CRUD, papers, Hub files | Hugging Face **Hub MCP** `huggingface` (`https://huggingface.co/mcp?login`). Claude-targeted in `agents.json`. Reuse `HUGGINGFACE_TOKEN` / `HF_TOKEN`. |
| **Runtime** | Something that runs weights and speaks chat | Space Gradio UI, Space OpenAI `/v1`, Inference Endpoint / TGI / vLLM, Modal GPU fn, Foundry deploy, local llama-server, Cursor Max |
| **Harness** | Who **executes** tools and who **prompts** the agent | Local Cursor/Claude/Codex process. Allowlist + schema. Persona = system prompt pack, not a new MCP. |

Read [environments.md](environments.md) for where to deploy, [tool-loop.md](tool-loop.md) for how to give tools, [profiles.md](profiles.md) for red-team / learner / coder packs.

## Hard rules

1. **Hub MCP is first-class for Hugging Face as an environment.** Use it (or the official HF plugin where mounted) for Hub work. Do not invent a second Hub MCP. Cursor may not mount it (`targets: claude`) — then use `huggingface_hub` / Hub HTTP with the same token, not a fake server.
2. **An inference URL is not Hub MCP.** A Space `/v1/chat/completions` or TGI endpoint is a **runtime**. Call it with process-local HTTP (OpenAI SDK, a small wrapper). Do not register every GPU URL in `agents.json` as MCP — that explodes the tool catalogue (`mcp-fleet-curation`) and is the wrong layer.
3. **The hosted model proposes; the harness executes.** `tool_calls` come back over HTTP/MCP. Shell, files, HexStrike, browsers stay **local** after allowlist + JSON-schema checks. Do not grow a remote shell on a Space to “make tools work.”
4. **Personas are prompt packs**, not skills named after a checkpoint. One runtime can host a red-team reporter, a literature learner, or a coding worker by swapping `messages[0]` and the `tools` list.
5. **G-32 is Cursor-quota wrapping, not “ban HF MCP.”** G-32 = `ai-mode` / `*-cursor` stay process-local to auth2api `:8317`; no persistent global Cursor-bridge env. Hugging Face Hub MCP is unrelated. G-36 = at most one `cursor-agent` process (RAM). Neither lock forbids deploying models on HF.

GPU rental / cloud-hub multiplex: skill `cloud-infra-toolchain`. Azure model deploy: `microsoft-foundry`. Action-space design: `agent-harness-construction`. OpenRouter is a spend-capped sidecar only — never Cursor BYOK (`openrouter-routing`).

## One-line decision

- Need Hub search / Space metadata / papers → **HF Hub MCP** (or Hub CLI).
- Need tokens out of a GPU → **runtime `/v1` or Gradio**.
- Need the agent to *do* something → **local tools** + tool loop.

Worked HF Space OpenAI example (not the SSOT): [recipes/hf-space-openai.md](recipes/hf-space-openai.md).
