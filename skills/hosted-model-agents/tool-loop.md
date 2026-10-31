---
title: tool-loop
type: note
permalink: dqverify-repo-20261013/skills/hosted-model-agents/tool-loop
---

# Tool loop (give any agent tools)

Works for any chat model that can emit tool calls (OpenAI `tool_calls`, Qwen XML, Hermes JSON, …). The **runtime only translates**; the **harness only executes**.

```
Client  --messages+tools-->  Runtime (Space / TGI / local / Foundry)
Client  <--tool_calls------  Runtime   (names + JSON args, allowlisted)
Client  --execute locally-->  Host tools (files, HTTP, approved MCP)
Client  --role:tool-------->  Runtime
Client  <--assistant text--  Runtime
```

## What you send the model

- `tools`: OpenAI function schemas (name, description, parameters, required).
- `tool_choice`: `auto` / `none` / named function.
- System prompt from a **profile** ([profiles.md](profiles.md)), not baked into one checkpoint skill.

Keep the list **narrow** (`agent-harness-construction`). A red-team reporter and a literature learner should not share a 200-tool dump.

## What you never send to the GPU box

- Unrestricted shell, credential files, HexStrike `/api/command`, C2, exploit payloads.
- “Execute this tool on the Space.” ZeroGPU Spaces should not grow subprocess tools.

Validate **before** local execution: name ∈ allowlist, required keys present, args parse as JSON. Unknown names → treat as ordinary assistant text, do not run.

## Three ways tools appear (do not collapse them)

| Mechanism | Who lists tools | Who runs them |
|---|---|---|
| **OpenAI `tools` on `/v1`** | Your client, every request | Your harness |
| **Gradio MCP** (`mcp_server=True`) | The Gradio app | The Space process (app-defined; still not Hub) |
| **Native agent MCP** (Cursor/Claude `agents.json`) | Fleet config | That MCP server |

HF **Hub MCP** lists Hub operations, not `read_file` on the owner’s disk. Local `read_file` stays a Cursor/Claude tool.

## Client shape

Any OpenAI-compat HTTP client is enough (`openai` SDK, curl, a 40-line wrapper). Wrappers stay **process-local** (env for that process only). That is the same *shape* as G-32 wrappers, but the **quota** is HF or Modal or local — not Cursor `:8317`.

Streaming: SSE `data:` chunks then `[DONE]`. Tool-call IDs must round-trip on `role: tool`.

Template traps are **per checkpoint** (e.g. Qwen `reasoning_effort: high` vs `xhigh`; Jinja `|items` needing dict arguments). Put those in a **recipe**, not in this doctrine file.