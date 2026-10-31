---
title: reference
type: note
permalink: dqverify-repo-20261013/skills/qwen-space-tool-api/reference
---

# Qwen Space OpenAI wire contract

Measured 29.08.2026. Confirm live `/healthz` before blaming the client.

## Endpoints

Base: `https://prekzursil-qwen38-27b-heretic-chat.hf.space`

| Method | Path | GPU? |
|---|---|---|
| GET | `/v1/models` | no |
| GET | `/healthz` | no |
| POST | `/v1/chat/completions` | yes (`@spaces.GPU`) |
| UI | `/` | Gradio chat |

Auth header: `Authorization: Bearer <HF_TOKEN>`.

Model id advertised: `qwen38-heretic`.
Checkpoint: `heretic-org/Qwen3.8-27B-heretic-ara` (4-bit NF4, ZeroGPU large).

## Request

OpenAI Chat Completions body. Extra fields the Space honors:

| Field | Notes |
|---|---|
| `messages` | required |
| `tools` | OpenAI function tools; passed into `apply_chat_template(..., tools=)` |
| `tool_choice` | `auto` / `none` / named `{type:function,function:{name}}` |
| `stream` | SSE `data: {chunk}` then `data: [DONE]` |
| `reasoning_effort` | `low` / `medium` / `xhigh`. **`high` aliases to `xhigh`** (stock template raises on `high`) |
| `enable_thinking` | bool; also `chat_template_kwargs.enable_thinking` |
| `max_tokens` / `max_completion_tokens` | ZeroGPU may cut ~240s |

Default system prompt is prepended if the client omits `role: system`, and prepended before a client system message so the authorized-scope rules stay first.

## Tool markup

Qwen3.8 native (what the hosted `chat_template.jinja` asks for):

```xml
<tool_call>
<function=read_file>
<parameter=path>
package.json
</parameter>
</function>
</tool_call>
```

Hermes JSON inside `<tool_call>` is also parsed. Both become OpenAI:

```json
{
  "id": "call_0_...",
  "type": "function",
  "function": {"name": "read_file", "arguments": "{\"path\":\"package.json\"}"}
}
```

On the **next** turn, send assistant `tool_calls` with `arguments` as a JSON **object** (dict) in the Space-bound message list — the Jinja template uses `|items` and will character-iterate a string. `openai_protocol.normalize_messages` already coerces strings to dicts. Subsequent tool results: `{"role":"tool","tool_call_id":"...","content":"..."}`.

## Validation before return (not execution)

Dropped, never forwarded to the harness:

- tool name not in the request `tools` allowlist
- missing JSON-schema `required` keys
- `tool_choice` named function mismatch

Unknown-tool attempts come back as `finish_reason: stop` plus a content note, not as `tool_calls`.

## Implementation map

| File | Role |
|---|---|
| `openai_protocol.py` | request/response translation, SSE (GPU-free, unit-tested) |
| `tool_parse.py` | XML/JSON parse + allowlist validate |
| `system_prompt.py` | authorized-scope default SYSTEM |
| `openai_api.py` | mounts `/v1/*` onto Gradio `App.create_app` |
| `app.py` | ZeroGPU generate; Gradio UI; does not execute tools |

Keep `sdk: gradio` + `@spaces.GPU`. Docker Spaces lose ZeroGPU.

## MCP distinction

Three different surfaces that are easy to smash together:

| Surface | What it is | Do we register it in `agents.json`? |
|---|---|---|
| Hub MCP `huggingface` | models/datasets/spaces/papers search | Already registered (Claude target) |
| Gradio `mcp_server=True` on the Space | Space-side MCP over Gradio `chat()` | No. Hub can attach Spaces as community MCP tools; we do not import this private Space into Cursor/Claude MCP (G-32, RAM, wrong action space) |
| `POST /v1/chat/completions` | OpenAI tool-call proposer | **Yes, via process-local `qwen-space`** |

ZeroGPU stays Gradio-SDK-only. Custom `/v1` routes live on the Gradio FastAPI app. The client executes tools. Hugging Face’s own Gradio MCP docs convert *Gradio endpoints* into tools — that would make `chat()` a remote tool, not a local-harness executor. `[B.corrob x2.2026]` hub-docs spaces-mcp-servers + Gradio MCP guide.