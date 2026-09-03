# GLM 5.3 Hugging Face adapter

> **DEPRECATED (owner, 2026-09-02).** Registry entry disabled 2026-09-03. To be
> replaced by a registry-driven model integration layer (models SSOT + per-runtime
> materializers + one generic inference MCP tool + eval gate); build wave pending
> owner steering of gem-hunt D1-D13. Do not build on this adapter.

On-demand adapters for the official Hugging Face inference route:

- Cursor/Claude-compatible stdio MCP tool: `glm53_chat`
- Local OpenAI-compatible HTTP wrapper: `glm-5.3-custom`

Backend:

- base URL: `https://router.huggingface.co/v1`
- model: `zai-org/GLM-5.3:zai-org`
- authentication: standard Hugging Face inference token
- protocol: OpenAI-compatible chat completions

The system prompt is deliberately an editable string with a blank default.

The project directory retains its original `glm53-space` name for stable MCP
registration, but runtime calls bypass the third-party
`akhaliq/GLM-5.3` Space.

## Install

```powershell
uv sync
```

Authentication prefers `HF_INFERENCE_TOKEN`, then falls back to
`HUGGINGFACE_TOKEN` or `HF_TOKEN`, and is sent only to Hugging Face's official
router as the OpenAI-compatible API key. Use an inference-only token when one
already exists; the adapter does not create or rotate credentials.

Never put a token in this repository or in command arguments.

## Why the public Space is bypassed

The public Space source was inspected on 30.08.2026. It routes to the genuine
`zai-org/GLM-5.3` model, and its author is a well-known Hugging Face community
builder, so there was no direct evidence of a scam. However, the Space asks for
both `inference-api` and unnecessary `write-repos` OAuth scopes. Gradio then
forwards the visitor OAuth token into third-party Space code. Calling the same
official Hugging Face inference backend directly removes that avoidable trust
boundary without reducing model capability.

## MCP

```powershell
uv run python mcp_server.py
```

Tool schema:

```text
glm53_chat(user_prompt: string, system_prompt: string = "")
```

The model is text-only. Do not send secrets, raw private transcripts, or
confidential source material to the hosted model.

## OpenAI-compatible wrapper

Start manually:

```powershell
uv run python openai_proxy.py --port 8321
```

Endpoints:

- `GET http://127.0.0.1:8321/healthz`
- `GET http://127.0.0.1:8321/v1/models`
- `POST http://127.0.0.1:8321/v1/chat/completions`

Model ID:

```text
glm-5.3-custom
```

The wrapper supports non-streaming responses and a compatibility stream that
emits one text chunk. It does not add tool calling, image input, token usage,
or native incremental generation that the backend does not provide.

Mandatory local bearer protection:

```powershell
$env:GLM53_PROXY_API_KEY = "<local-only value>"
```

The proxy refuses non-loopback binds, rejects browser-origin requests and
untrusted Host headers, limits request bodies, and never autostarts. Stop it
when the client session ends.

## Fabric and Goose

Neither client is changed automatically:

- Fabric currently defaults to its existing OpenRouter model.
- Goose currently defaults to its existing Cursor proxy.

While this wrapper is running, clients that accept an OpenAI-compatible base
URL can use `http://127.0.0.1:8321/v1` with model `glm-5.3-custom`. Keep this
process-local; do not configure it as a persistent Cursor model gateway.

## Verification

```powershell
uv run pytest -q
```
