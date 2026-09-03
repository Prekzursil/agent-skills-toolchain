#!/usr/bin/env python3
"""On-demand localhost OpenAI-compatible wrapper for the GLM 5.3 Space."""

from __future__ import annotations

import argparse
import hmac
import json
import os
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import anyio
import glm53_core as core
import uvicorn
from starlette.applications import Starlette
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

Invoke = Callable[[str, str], str]
MAX_BODY_BYTES = 1_000_000
UNSUPPORTED_PARAMETERS = frozenset(
    {
        "frequency_penalty",
        "logit_bias",
        "logprobs",
        "max_completion_tokens",
        "max_tokens",
        "n",
        "parallel_tool_calls",
        "presence_penalty",
        "response_format",
        "seed",
        "stop",
        "stream_options",
        "temperature",
        "tool_choice",
        "tools",
        "top_logprobs",
        "top_p",
    }
)


def _error(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse(
        {"error": {"message": message, "type": "invalid_request_error"}},
        status_code=status,
    )


def _auth_error(request: Request, expected: str) -> JSONResponse | None:
    if request.headers.get("origin") is not None:
        return _error("browser origins are not allowed", 403)
    if not expected:
        return _error("proxy API key is not configured", 503)
    scheme, separator, presented = request.headers.get(
        "authorization", ""
    ).partition(" ")
    if (
        not separator
        or scheme.casefold() != "bearer"
        or not hmac.compare_digest(
            presented.encode("utf-8"),
            expected.encode("utf-8"),
        )
    ):
        return _error("invalid API key", 401)
    return None


def _completion_payload(response_id: str, created: int, text: str) -> dict[str, Any]:
    return {
        "id": response_id,
        "object": "chat.completion",
        "created": created,
        "model": core.MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }


async def _chat_response(
    request: Request,
    configured_api_key: str,
    invoke_fn: Invoke,
) -> Response:
    if auth_error := _auth_error(request, configured_api_key):
        return auth_error
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_BODY_BYTES:
                return _error("request body is too large", 413)
        except ValueError:
            return _error("invalid Content-Length header")

    request_chunks: list[bytes] = []
    total = 0
    async for request_chunk in request.stream():
        total += len(request_chunk)
        if total > MAX_BODY_BYTES:
            return _error("request body is too large", 413)
        request_chunks.append(request_chunk)
    try:
        body = json.loads(b"".join(request_chunks).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _error("request body must be valid JSON")
    if not isinstance(body, dict):
        return _error("request body must be an object")
    if body.get("model") != core.MODEL_ID:
        return _error(f"model must be {core.MODEL_ID!r}")
    unsupported = sorted(UNSUPPORTED_PARAMETERS & body.keys())
    if unsupported:
        return _error(f"unsupported parameters: {', '.join(unsupported)}")

    try:
        prompt, system_prompt = core.messages_to_prompts(body.get("messages"))
        text = await anyio.to_thread.run_sync(
            lambda: invoke_fn(prompt, system_prompt),
            abandon_on_cancel=True,
        )
    except core.Glm53ValidationError as exc:
        return _error(str(exc))
    except core.Glm53UpstreamError:
        return JSONResponse(
            {
                "error": {
                    "message": "upstream GLM 5.3 request failed",
                    "type": "upstream_error",
                }
            },
            status_code=502,
        )
    except Exception:  # noqa: BLE001 - HTTP boundary must not leak exceptions
        return JSONResponse(
            {
                "error": {
                    "message": "upstream GLM 5.3 request failed",
                    "type": "upstream_error",
                }
            },
            status_code=502,
        )

    response_id = f"chatcmpl-glm53-{uuid.uuid4().hex}"
    created = int(time.time())
    if not body.get("stream", False):
        return JSONResponse(_completion_payload(response_id, created, text))

    response_chunk = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": core.MODEL_ID,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }

    def stream() -> Iterator[str]:
        yield f"data: {json.dumps(response_chunk, separators=(',', ':'))}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


def create_app(
    invoke: Invoke | None = None,
    *,
    api_key: str | None = None,
    allowed_hosts: list[str] | None = None,
) -> Starlette:
    """Create the proxy app with an injectable model call for tests."""
    invoke_fn = invoke or core.invoke
    configured_api_key = (
        os.getenv("GLM53_PROXY_API_KEY") if api_key is None else api_key
    ) or ""

    async def health(_request: Request) -> Response:
        return JSONResponse({"ok": True, "model": core.MODEL_ID})

    async def models(request: Request) -> Response:
        if auth_error := _auth_error(request, configured_api_key):
            return auth_error
        return JSONResponse(
            {
                "object": "list",
                "data": [
                    {
                        "id": core.MODEL_ID,
                        "object": "model",
                        "created": 0,
                        "owned_by": "huggingface:zai-org",
                    }
                ],
            }
        )

    async def chat_completions(request: Request) -> Response:
        return await _chat_response(
            request,
            configured_api_key,
            invoke_fn,
        )

    app = Starlette(
        routes=[
            Route("/healthz", health, methods=["GET"]),
            Route("/v1/models", models, methods=["GET"]),
            Route("/v1/chat/completions", chat_completions, methods=["POST"]),
        ]
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts or ["127.0.0.1", "localhost"],
    )
    return app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the on-demand GLM 5.3 OpenAI-compatible localhost wrapper."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8321)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("the proxy may bind only to loopback")
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
