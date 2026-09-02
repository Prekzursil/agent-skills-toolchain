#!/usr/bin/env python3
"""Stdlib fake of the upstreams the inference hub talks to (BUILD-CONTRACT section 5).

One ``ThreadingHTTPServer`` on ``127.0.0.1`` plays one of five profiles:

* ``openai``    - ``/v1/models``, ``/v1/chat/completions`` (JSON and SSE),
  ``/v1/responses``; ``usage`` carries ``prompt_tokens_details``.
* ``ollama``    - the OpenAI facade plus ``/api/tags``, ``/api/show``,
  ``/api/version``; 400 on ``tool_choice``, 404 on an unpulled model, base64
  image data URIs only, stream ``usage`` only with ``stream_options.include_usage``,
  ``response_format`` ignored, errors are ``{"error": "<text>"}``.
* ``hf-router`` - 401 without a Bearer token, ``providers[]`` on every model,
  ``:provider`` suffix echoed in ``model``, ``X-HF-Bill-To`` echoed back.
* ``auth2api``  - 36 ``cursor-*`` ids; ``/v1/responses`` and ``/v1/messages``
  (Anthropic shape) each switchable off, answering 404 when off.
* ``lmstudio``  - ``/api/v0/models`` and a stateful ``/v1/responses`` whose
  ``previous_response_id`` must name an earlier response (forgotten on restart).

The reply is deterministic: ``"echo:" + <last user text>``; ``refuse:<x>`` in the
prompt yields a refusal ``refused:<x>``; a ``tools`` list yields one tool call
(``call_1``) naming the first tool with ``{"nonce": <nonce=... from the prompt or
"0">}``; a ``json_schema`` response format yields the JSON string
``{"echo": <text>}``. Tokens are whitespace-separated words.

Fault flags rehearse upstream misbehaviour on inference routes: ``rate_limit_every``
(429 + ``Retry-After: 1``), ``fail_every`` (503), ``slow_first_token``,
``hang_after_tokens`` (stream N tokens, then hold the connection until the client
leaves, the server stops, or ``HANG_CAP_S`` passes), ``malformed`` (truncated JSON),
``echo_secret`` (the request's Authorization value appears in the content),
``drop_tool_calls`` (``<tool_call>...</tool_call>`` text instead of ``tool_calls``),
``flatten_refusal`` (no ``refusal`` field), ``latency_s`` (fixed delay on every
request) and ``restart_every`` (periodic restart that forgets counters and state).

``requests`` records ``{method, path, headers, json}`` per request with header names
lower-cased and the Authorization / x-api-key values replaced by ``"<present>"``.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import re
import select
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol

PROFILES = ("openai", "ollama", "hf-router", "auth2api", "lmstudio")
HANG_CAP_S = 30.0
OLLAMA_VERSION = "0.13.3"

_HOLD_POLL_S = 0.05
_HOST = "127.0.0.1"
_CREATED = 1756555200
_MODIFIED_AT = "2026-08-30T12:00:00.000000000Z"
_TEXT_PART_TYPES = frozenset({"text", "input_text", "output_text"})
_MASKED_HEADERS = frozenset({"authorization", "x-api-key"})
_NONCE_RE = re.compile(r"nonce=([\w.-]+)")
_REFUSE_PREFIX = "refuse:"
_MALFORMED_BODY = b'{"choices": ['
_OBJECT_REQUIRED = "request body must be a JSON object"

OPENAI_MODELS = ("gpt-5.2", "gpt-5.2-codex", "gpt-5.1", "gpt-4.1", "o4-mini")

OLLAMA_MODELS: dict[str, dict[str, Any]] = {
    "qwen3:8b": {
        "arch": "qwen3",
        "family": "qwen3",
        "parameter_size": "8.2B",
        "quantization": "Q4_K_M",
        "size": 5225388768,
        "block_count": 36,
        "head_count": 32,
        "head_count_kv": 8,
        "embedding_length": 4096,
        "context_length": 40960,
        "capabilities": ["completion", "tools", "thinking"],
    },
    "qwen2.5:7b": {
        "arch": "qwen2",
        "family": "qwen2",
        "parameter_size": "7.6B",
        "quantization": "Q4_K_M",
        "size": 4683087332,
        "block_count": 28,
        "head_count": 28,
        "head_count_kv": 4,
        "embedding_length": 3584,
        "context_length": 32768,
        "capabilities": ["completion", "tools"],
    },
    "qwen2.5-coder:7b": {
        "arch": "qwen2",
        "family": "qwen2",
        "parameter_size": "7.6B",
        "quantization": "Q4_K_M",
        "size": 4683087519,
        "block_count": 28,
        "head_count": 28,
        "head_count_kv": 4,
        "embedding_length": 3584,
        "context_length": 32768,
        "capabilities": ["completion", "tools", "insert"],
    },
    "nomic-embed-text:latest": {
        "arch": "nomic-bert",
        "family": "nomic-bert",
        "parameter_size": "137M",
        "quantization": "F16",
        "size": 274302450,
        "block_count": 12,
        "head_count": 12,
        "head_count_kv": 12,
        "embedding_length": 768,
        "context_length": 2048,
        "capabilities": ["embedding"],
    },
}


def _provider(
    name: str, *, tools: bool, structured: bool, price_in: float, price_out: float
) -> dict[str, Any]:
    return {
        "provider": name,
        "status": "live",
        "supports_tools": tools,
        "supports_structured_output": structured,
        "pricing": {"input": price_in, "output": price_out},
    }


HF_ROUTER_MODELS: dict[str, list[dict[str, Any]]] = {
    "zai-org/GLM-5.3": [
        _provider("novita", tools=True, structured=True, price_in=0.6, price_out=2.2),
        _provider("zai-org", tools=True, structured=False, price_in=0.6, price_out=2.2),
    ],
    "Qwen/Qwen3-Coder-480B-A35B-Instruct": [
        _provider("cerebras", tools=True, structured=True, price_in=2.0, price_out=2.0),
        _provider("together", tools=True, structured=True, price_in=2.0, price_out=2.0),
    ],
    "deepseek-ai/DeepSeek-V3.2": [
        _provider("novita", tools=True, structured=True, price_in=0.27, price_out=0.41),
    ],
    "meta-llama/Llama-3.3-70B-Instruct": [
        _provider("groq", tools=True, structured=True, price_in=0.59, price_out=0.79),
        _provider(
            "nebius", tools=False, structured=False, price_in=0.13, price_out=0.4
        ),
    ],
}

AUTH2API_MODEL_IDS = (
    "cursor-auto",
    "cursor-gpt-5.2",
    "cursor-gpt-5.2-codex",
    "cursor-gpt-5.2-high",
    "cursor-gpt-5.2-mini",
    "cursor-gpt-5.1",
    "cursor-gpt-5.1-codex",
    "cursor-gpt-5.1-codex-max",
    "cursor-gpt-5.1-high",
    "cursor-gpt-5",
    "cursor-gpt-5-codex",
    "cursor-gpt-5-mini",
    "cursor-gpt-5-nano",
    "cursor-gpt-4.1",
    "cursor-gpt-4o",
    "cursor-o3",
    "cursor-o4-mini",
    "cursor-claude-4.5-opus",
    "cursor-claude-4.5-opus-thinking",
    "cursor-claude-4.5-sonnet",
    "cursor-claude-4.5-sonnet-thinking",
    "cursor-claude-4.5-haiku",
    "cursor-claude-4.1-opus",
    "cursor-claude-4-sonnet",
    "cursor-claude-3.7-sonnet",
    "cursor-gemini-3-pro",
    "cursor-gemini-3-flash",
    "cursor-gemini-2.5-pro",
    "cursor-gemini-2.5-flash",
    "cursor-grok-4.6",
    "cursor-grok-4.1-fast",
    "cursor-grok-4",
    "cursor-grok-code-fast-1",
    "cursor-kimi-k2.5",
    "cursor-deepseek-v3.2",
    "cursor-composer-2",
)

LMSTUDIO_MODELS: tuple[dict[str, Any], ...] = (
    {
        "id": "qwen3-8b",
        "object": "model",
        "type": "llm",
        "publisher": "qwen",
        "arch": "qwen3",
        "compatibility_type": "gguf",
        "quantization": "Q4_K_M",
        "state": "loaded",
        "max_context_length": 40960,
    },
    {
        "id": "qwen2.5-7b-instruct",
        "object": "model",
        "type": "llm",
        "publisher": "qwen",
        "arch": "qwen2",
        "compatibility_type": "gguf",
        "quantization": "Q4_K_M",
        "state": "not-loaded",
        "max_context_length": 32768,
    },
    {
        "id": "text-embedding-nomic-embed-text-v1.5",
        "object": "model",
        "type": "embeddings",
        "publisher": "nomic-ai",
        "arch": "nomic-bert",
        "compatibility_type": "gguf",
        "quantization": "Q4_K_M",
        "state": "not-loaded",
        "max_context_length": 2048,
    },
)

_CATALOG: dict[str, tuple[tuple[str, str], ...]] = {
    "openai": tuple((model_id, "openai") for model_id in OPENAI_MODELS),
    "ollama": tuple((model_id, "library") for model_id in OLLAMA_MODELS),
    "hf-router": tuple(
        (model_id, model_id.split("/")[0]) for model_id in HF_ROUTER_MODELS
    ),
    "auth2api": tuple((model_id, "cursor") for model_id in AUTH2API_MODEL_IDS),
    "lmstudio": tuple((row["id"], "organization_owner") for row in LMSTUDIO_MODELS),
}


# --- low-level helpers ---------------------------------------------------------


class _Writable(Protocol):
    def write(self, data: bytes, /) -> object: ...

    def flush(self) -> object: ...


class _Connection(Protocol):
    def fileno(self) -> int: ...

    def recv(self, bufsize: int, /) -> bytes: ...


def _write(stream: _Writable, data: bytes) -> bool:
    """Write and flush; ``False`` when the client has vanished."""
    try:
        stream.write(data)
        stream.flush()
    except OSError:
        return False
    return True


def _frame(payload: bytes) -> bytes:
    return f"{len(payload):x}\r\n".encode("ascii") + payload + b"\r\n"


def _stream_sse(
    write: Callable[[bytes], bool],
    chunks: Iterable[dict[str, Any]],
    hang_after_tokens: int,
) -> str:
    """Emit ``data:`` events as HTTP chunks; ``"done"``, ``"gone"`` or ``"hang"``."""
    for index, chunk in enumerate(chunks):
        if hang_after_tokens and index >= hang_after_tokens:
            return "hang"
        if not write(_frame(b"data: " + json.dumps(chunk).encode("utf-8") + b"\n\n")):
            return "gone"
    if hang_after_tokens:
        return "hang"
    if not write(_frame(b"data: [DONE]\n\n")):
        return "gone"
    write(b"0\r\n\r\n")
    return "done"


def _hold_connection(
    connection: _Connection, stopping: threading.Event, cap_s: float
) -> str:
    """Sit on an open connection; ``"disconnected"``, ``"stopped"`` or ``"cap"``."""
    deadline = time.monotonic() + cap_s
    while True:
        if stopping.is_set():
            return "stopped"
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "cap"
        readable, _, _ = select.select(
            [connection], [], [], min(remaining, _HOLD_POLL_S)
        )
        if not readable:
            continue
        try:
            data = connection.recv(4096)
        except OSError:
            return "disconnected"
        if not data:
            return "disconnected"


def _tokens(text: str) -> int:
    return len(text.split())


def _pieces(text: str) -> list[str]:
    words = text.split(" ")
    return [word + " " for word in words[:-1]] + words[-1:]


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") in _TEXT_PART_TYPES
        )
    return ""


def _parts(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    if isinstance(content, list):
        return [part for part in content if isinstance(part, dict)]
    return []


def _last_user_text(entries: list[dict[str, Any]]) -> str:
    texts = [
        _text_of(entry.get("content"))
        for entry in entries
        if entry.get("role") == "user"
    ]
    return texts[-1] if texts else ""


def _nonce(text: str) -> str:
    match = _NONCE_RE.search(text)
    return match.group(1) if match else "0"


def _first_tool_name(tools: list[Any]) -> str:
    tool = tools[0] if isinstance(tools[0], dict) else {}
    function = tool.get("function")
    if isinstance(function, dict):
        return str(function.get("name", ""))
    return str(tool.get("name", ""))


def _wants_json(response_format: Any) -> bool:
    return isinstance(response_format, dict) and response_format.get("type") in (
        "json_schema",
        "json_object",
    )


def _responses_wants_json(text_options: Any) -> bool:
    fmt = text_options.get("format") if isinstance(text_options, dict) else None
    return isinstance(fmt, dict) and fmt.get("type") == "json_schema"


def _include_usage(stream_options: Any) -> bool:
    return isinstance(stream_options, dict) and bool(
        stream_options.get("include_usage")
    )


def _is_data_uri(image: Any) -> bool:
    url = image.get("url") if isinstance(image, dict) else image
    return isinstance(url, str) and url.startswith("data:")


def _has_bearer(value: str) -> bool:
    scheme, _, token = value.partition(" ")
    return scheme == "Bearer" and token.strip() != ""


def _hf_model_name(model: str) -> str:
    providers = HF_ROUTER_MODELS.get(model)
    if ":" in model or not providers:
        return model
    return f"{model}:{providers[0]['provider']}"


def _bill_to(headers: dict[str, str]) -> tuple[tuple[str, str], ...]:
    value = headers.get("x-hf-bill-to")
    return (("X-HF-Bill-To", value),) if value is not None else ()


def _new_id(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:24]


def _now() -> int:
    return int(time.time())


def _ollama_details(info: dict[str, Any]) -> dict[str, Any]:
    return {
        "parent_model": "",
        "format": "gguf",
        "family": info["family"],
        "families": [info["family"]],
        "parameter_size": info["parameter_size"],
        "quantization_level": info["quantization"],
    }


def _ollama_tag(name: str) -> dict[str, Any]:
    info = OLLAMA_MODELS[name]
    return {
        "name": name,
        "model": name,
        "modified_at": _MODIFIED_AT,
        "size": info["size"],
        "digest": hashlib.sha256(name.encode("utf-8")).hexdigest(),
        "details": _ollama_details(info),
    }


def _ollama_show_body(name: str, info: dict[str, Any]) -> dict[str, Any]:
    arch = info["arch"]
    return {
        "modified_at": _MODIFIED_AT,
        "details": _ollama_details(info),
        "model_info": {
            "general.architecture": arch,
            "general.basename": name.split(":")[0],
            f"{arch}.attention.head_count": info["head_count"],
            f"{arch}.attention.head_count_kv": info["head_count_kv"],
            f"{arch}.attention.key_length": 128,
            f"{arch}.attention.value_length": 128,
            f"{arch}.block_count": info["block_count"],
            f"{arch}.context_length": info["context_length"],
            f"{arch}.embedding_length": info["embedding_length"],
        },
        "capabilities": list(info["capabilities"]),
    }


# --- request/response model ------------------------------------------------------


@dataclass(frozen=True)
class _Request:
    headers: dict[str, str]
    payload: dict[str, Any]


@dataclass(frozen=True)
class _Reply:
    kind: str
    text: str
    tool_name: str = ""

    @property
    def tokens(self) -> int:
        return _tokens(self.text)

    @property
    def finish_reason(self) -> str:
        return "tool_calls" if self.kind == "tool" else "stop"


@dataclass(frozen=True)
class _Outcome:
    status: int
    body: Any
    headers: tuple[tuple[str, str], ...] = ()
    chunks: list[dict[str, Any]] | None = None


@dataclass
class _Running:
    httpd: ThreadingHTTPServer
    serve_thread: threading.Thread
    restart_thread: threading.Thread


_Route = tuple[Callable[[_Request], _Outcome], bool]


class FakeOpenAIServer:
    """Drive from tests or the CLI: ``start()`` / ``stop()`` / ``restart()``."""

    def __init__(
        self,
        profile: str = "openai",
        *,
        port: int = 0,
        rate_limit_every: int = 0,
        fail_every: int = 0,
        slow_first_token: float = 0.0,
        hang_after_tokens: int = 0,
        malformed: bool = False,
        echo_secret: bool = False,
        drop_tool_calls: bool = False,
        flatten_refusal: bool = False,
        latency_s: float = 0.0,
        responses: bool = True,
        messages: bool = True,
        restart_every: float = 0.0,
    ) -> None:
        if profile not in PROFILES:
            raise ValueError(f"unknown profile {profile!r}; expected one of {PROFILES}")
        self.profile = profile
        self.port = port
        self.rate_limit_every = rate_limit_every
        self.fail_every = fail_every
        self.slow_first_token = slow_first_token
        self.hang_after_tokens = hang_after_tokens
        self.malformed = malformed
        self.echo_secret = echo_secret
        self.drop_tool_calls = drop_tool_calls
        self.flatten_refusal = flatten_refusal
        self.latency_s = latency_s
        self.responses = responses
        self.messages = messages
        self.restart_every = restart_every
        self.generation = 0
        self.requests: list[dict[str, Any]] = []
        self.holds: list[str] = []
        self._lock = threading.Lock()
        self._stopping = threading.Event()
        self._running: _Running | None = None
        self._calls = 0
        self._response_tokens: dict[str, int] = {}
        self._plain_errors = profile in ("ollama", "hf-router")
        self._stateful = profile == "lmstudio"
        self._routes = self._build_routes()

    # -- lifecycle ---------------------------------------------------------------

    @property
    def root_url(self) -> str:
        return f"http://{_HOST}:{self.port}"

    @property
    def base_url(self) -> str:
        return self.root_url + "/v1"

    @property
    def running(self) -> bool:
        return self._running is not None

    def start(self) -> FakeOpenAIServer:
        if self._running is not None:
            return self
        self._stopping.clear()
        self.restart()
        httpd = ThreadingHTTPServer((_HOST, self.port), _make_handler(self))
        self.port = httpd.server_address[1]
        serve_thread = threading.Thread(
            target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        restart_thread = threading.Thread(target=self._restart_loop, daemon=True)
        self._running = _Running(httpd, serve_thread, restart_thread)
        serve_thread.start()
        restart_thread.start()
        return self

    def stop(self) -> None:
        """Unbind the port; every new connection is refused until ``start()``."""
        running = self._running
        if running is None:
            return
        self._stopping.set()
        running.httpd.shutdown()
        running.httpd.server_close()
        running.serve_thread.join(timeout=5)
        running.restart_thread.join(timeout=5)
        self._running = None

    def restart(self) -> None:
        """A new process on the same port: counters and stateful responses are gone."""
        with self._lock:
            self.generation += 1
            self._calls = 0
            self._response_tokens.clear()

    def __enter__(self) -> FakeOpenAIServer:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    def _restart_loop(self) -> None:
        while not self._stopping.wait(self.restart_every or None):
            self.restart()

    # -- bookkeeping -------------------------------------------------------------

    def _record(
        self, method: str, path: str, headers: dict[str, str], payload: Any
    ) -> None:
        masked = {
            name: "<present>" if name in _MASKED_HEADERS else value
            for name, value in headers.items()
        }
        self.requests.append(
            {"method": method, "path": path, "headers": masked, "json": payload}
        )

    def _error(
        self,
        status: int,
        message: str,
        *,
        kind: str = "invalid_request_error",
        param: str | None = None,
        code: str | None = None,
        headers: tuple[tuple[str, str], ...] = (),
    ) -> _Outcome:
        if self._plain_errors:
            return _Outcome(status, {"error": message}, headers)
        body = {
            "error": {"message": message, "type": kind, "param": param, "code": code}
        }
        return _Outcome(status, body, headers)

    def _fault(self) -> _Outcome | None:
        with self._lock:
            self._calls += 1
            count = self._calls
        if self.rate_limit_every and count % self.rate_limit_every == 0:
            return self._error(
                429,
                "Rate limit reached for the fake upstream",
                kind="rate_limit_error",
                code="rate_limit_exceeded",
                headers=(("Retry-After", "1"),),
            )
        if self.fail_every and count % self.fail_every == 0:
            return self._error(
                503,
                "The server is temporarily unavailable",
                kind="server_error",
                code="service_unavailable",
            )
        return None

    def _build_routes(self) -> dict[tuple[str, str], _Route]:
        routes: dict[tuple[str, str], _Route] = {
            ("GET", "/v1/models"): (self._models, False),
            ("POST", "/v1/chat/completions"): (self._chat, True),
        }
        if self.profile in ("openai", "auth2api", "lmstudio") and self.responses:
            routes[("POST", "/v1/responses")] = (self._responses, True)
        if self.profile == "auth2api" and self.messages:
            routes[("POST", "/v1/messages")] = (self._messages, True)
        if self.profile == "ollama":
            routes[("GET", "/api/tags")] = (self._ollama_tags, False)
            routes[("POST", "/api/show")] = (self._ollama_show, False)
            routes[("GET", "/api/version")] = (self._ollama_version, False)
        if self.profile == "lmstudio":
            routes[("GET", "/api/v0/models")] = (self._lmstudio_v0_models, False)
        return routes

    # -- reply construction ------------------------------------------------------

    def _reply(
        self, text: str, tools: Any, structured: bool, authorization: str | None
    ) -> _Reply:
        if isinstance(tools, list) and tools:
            name = _first_tool_name(tools)
            arguments = {"nonce": _nonce(text)}
            if self.drop_tool_calls:
                flattened = json.dumps({"name": name, "arguments": arguments})
                return _Reply("text", f"<tool_call>{flattened}</tool_call>")
            return _Reply("tool", json.dumps(arguments), name)
        if text.startswith(_REFUSE_PREFIX):
            return _Reply("refusal", "refused:" + text[len(_REFUSE_PREFIX) :])
        if structured:
            return _Reply("text", json.dumps({"echo": text}))
        content = "echo:" + text
        if self.echo_secret and authorization is not None:
            content += " " + authorization
        return _Reply("text", content)

    def _usage(self, prompt_tokens: int, completion_tokens: int) -> dict[str, Any]:
        usage: dict[str, Any] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        if self.profile == "openai":
            usage["prompt_tokens_details"] = {"cached_tokens": 0}
        return usage

    def _chat_message(self, reply: _Reply) -> dict[str, Any]:
        if reply.kind == "tool":
            call = {
                "id": "call_1",
                "type": "function",
                "function": {"name": reply.tool_name, "arguments": reply.text},
            }
            message: dict[str, Any] = {
                "role": "assistant",
                "content": None,
                "tool_calls": [call],
            }
        elif reply.kind == "refusal" and not self.flatten_refusal:
            message = {"role": "assistant", "content": None, "refusal": reply.text}
        else:
            message = {"role": "assistant", "content": reply.text}
        if not self.flatten_refusal:
            message.setdefault("refusal", None)
        return message

    def _deltas(self, reply: _Reply) -> list[dict[str, Any]]:
        if reply.kind == "tool":
            head = {
                "index": 0,
                "id": "call_1",
                "type": "function",
                "function": {"name": reply.tool_name, "arguments": ""},
            }
            tail = {"index": 0, "function": {"arguments": reply.text}}
            return [{"tool_calls": [head]}, {"tool_calls": [tail]}]
        key = (
            "refusal"
            if reply.kind == "refusal" and not self.flatten_refusal
            else "content"
        )
        return [{key: piece} for piece in _pieces(reply.text)]

    def _chat_chunks(
        self, model: str, reply: _Reply, usage: dict[str, Any], include_usage: bool
    ) -> list[dict[str, Any]]:
        base = {
            "id": _new_id("chatcmpl-"),
            "object": "chat.completion.chunk",
            "created": _now(),
            "model": model,
        }
        deltas = self._deltas(reply)
        deltas[0] = {"role": "assistant", **deltas[0]}
        chunks = [
            {
                **base,
                "choices": [
                    {
                        "index": 0,
                        "delta": delta,
                        "logprobs": None,
                        "finish_reason": None,
                    }
                ],
            }
            for delta in deltas
        ]
        final: dict[str, Any] = {
            **base,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "logprobs": None,
                    "finish_reason": reply.finish_reason,
                }
            ],
        }
        if include_usage:
            final["usage"] = usage
        chunks.append(final)
        return chunks

    # -- routes ------------------------------------------------------------------

    def _models(self, request: _Request) -> _Outcome:
        rows = [
            {"id": model_id, "object": "model", "created": _CREATED, "owned_by": owner}
            for model_id, owner in _CATALOG[self.profile]
        ]
        if self.profile == "hf-router":
            for row in rows:
                row["providers"] = [
                    dict(provider) for provider in HF_ROUTER_MODELS[row["id"]]
                ]
        return _Outcome(200, {"object": "list", "data": rows})

    def _ollama_reject(
        self, payload: dict[str, Any], model: str, messages: list[Any]
    ) -> _Outcome | None:
        if model not in OLLAMA_MODELS:
            return self._error(404, f"model '{model}' not found", code="not_found")
        if "tool_choice" in payload:
            return self._error(400, "tool_choice is not supported")
        for message in messages:
            for part in _parts(message if isinstance(message, dict) else {}):
                if part.get("type") == "image_url" and not _is_data_uri(
                    part.get("image_url")
                ):
                    return self._error(400, "image url must be a base64 data URI")
        return None

    def _chat(self, request: _Request) -> _Outcome:
        payload = request.payload
        messages = payload.get("messages")
        if not isinstance(messages, list):
            return self._error(
                400, "'messages' is required and must be a list", param="messages"
            )
        model = str(payload.get("model", ""))
        if self.profile == "ollama":
            rejected = self._ollama_reject(payload, model, messages)
            if rejected is not None:
                return rejected
        elif self.profile == "hf-router":
            model = _hf_model_name(model)
        entries = [message for message in messages if isinstance(message, dict)]
        prompt_tokens = sum(
            _tokens(_text_of(entry.get("content"))) for entry in entries
        )
        structured = self.profile != "ollama" and _wants_json(
            payload.get("response_format")
        )
        reply = self._reply(
            _last_user_text(entries),
            payload.get("tools"),
            structured,
            request.headers.get("authorization"),
        )
        usage = self._usage(prompt_tokens, reply.tokens)
        headers = _bill_to(request.headers)
        if payload.get("stream"):
            include_usage = self.profile != "ollama" or _include_usage(
                payload.get("stream_options")
            )
            chunks = self._chat_chunks(model, reply, usage, include_usage)
            return _Outcome(200, None, headers, chunks)
        body = {
            "id": _new_id("chatcmpl-"),
            "object": "chat.completion",
            "created": _now(),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": self._chat_message(reply),
                    "logprobs": None,
                    "finish_reason": reply.finish_reason,
                }
            ],
            "usage": usage,
        }
        return _Outcome(200, body, headers)

    def _responses_output(self, reply: _Reply) -> list[dict[str, Any]]:
        if reply.kind == "tool":
            call = {
                "type": "function_call",
                "id": _new_id("fc_"),
                "call_id": "call_1",
                "name": reply.tool_name,
                "arguments": reply.text,
                "status": "completed",
            }
            return [call]
        if reply.kind == "refusal":
            content: dict[str, Any] = {"type": "refusal", "refusal": reply.text}
        else:
            content = {"type": "output_text", "text": reply.text, "annotations": []}
        message = {
            "type": "message",
            "id": _new_id("msg_"),
            "role": "assistant",
            "status": "completed",
            "content": [content],
        }
        return [message]

    def _responses(self, request: _Request) -> _Outcome:
        payload = request.payload
        raw_input = payload.get("input")
        if isinstance(raw_input, str):
            items: list[dict[str, Any]] = [{"role": "user", "content": raw_input}]
        elif isinstance(raw_input, list):
            items = [item for item in raw_input if isinstance(item, dict)]
        else:
            return self._error(400, "'input' must be a string or a list", param="input")
        previous = payload.get("previous_response_id")
        context_tokens = 0
        if self._stateful and previous is not None:
            with self._lock:
                stored = self._response_tokens.get(previous)
            if stored is None:
                return self._error(
                    404,
                    "previous response not found",
                    param="previous_response_id",
                    code="not_found",
                )
            context_tokens = stored
        input_tokens = (
            context_tokens
            + _tokens(_text_of(payload.get("instructions")))
            + sum(_tokens(_text_of(item.get("content"))) for item in items)
        )
        reply = self._reply(
            _last_user_text(items),
            payload.get("tools"),
            _responses_wants_json(payload.get("text")),
            request.headers.get("authorization"),
        )
        response_id = _new_id("resp_")
        total_tokens = input_tokens + reply.tokens
        with self._lock:
            self._response_tokens[response_id] = total_tokens
        body = {
            "id": response_id,
            "object": "response",
            "created_at": _now(),
            "status": "completed",
            "model": payload.get("model"),
            "previous_response_id": previous,
            "output": self._responses_output(reply),
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": reply.tokens,
                "total_tokens": total_tokens,
            },
        }
        return _Outcome(200, body)

    def _messages(self, request: _Request) -> _Outcome:
        payload = request.payload
        messages = payload.get("messages")
        if not isinstance(messages, list):
            return self._error(
                400, "'messages' is required and must be a list", param="messages"
            )
        entries = [message for message in messages if isinstance(message, dict)]
        input_tokens = _tokens(_text_of(payload.get("system"))) + sum(
            _tokens(_text_of(entry.get("content"))) for entry in entries
        )
        reply = self._reply(
            _last_user_text(entries),
            payload.get("tools"),
            False,
            request.headers.get("authorization"),
        )
        if reply.kind == "tool":
            block: dict[str, Any] = {
                "type": "tool_use",
                "id": "toolu_1",
                "name": reply.tool_name,
                "input": json.loads(reply.text),
            }
            stop_reason = "tool_use"
        else:
            block = {"type": "text", "text": reply.text}
            stop_reason = "end_turn"
        body = {
            "id": _new_id("msg_"),
            "type": "message",
            "role": "assistant",
            "model": payload.get("model"),
            "content": [block],
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": input_tokens, "output_tokens": reply.tokens},
        }
        return _Outcome(200, body)

    def _ollama_tags(self, request: _Request) -> _Outcome:
        return _Outcome(200, {"models": [_ollama_tag(name) for name in OLLAMA_MODELS]})

    def _ollama_show(self, request: _Request) -> _Outcome:
        payload = request.payload
        name = str(payload.get("model") or payload.get("name") or "")
        info = OLLAMA_MODELS.get(name)
        if info is None:
            return self._error(404, f"model '{name}' not found", code="not_found")
        return _Outcome(200, _ollama_show_body(name, info))

    def _ollama_version(self, request: _Request) -> _Outcome:
        return _Outcome(200, {"version": OLLAMA_VERSION})

    def _lmstudio_v0_models(self, request: _Request) -> _Outcome:
        return _Outcome(
            200, {"object": "list", "data": [dict(row) for row in LMSTUDIO_MODELS]}
        )


def _make_handler(server: FakeOpenAIServer) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:  # noqa: N802 (stdlib name)
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802 (stdlib name)
            self._dispatch("POST")

        def log_message(self, format: str, *args: Any) -> None:
            pass

        def _read_json(self) -> tuple[Any, bool]:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length)
            if not raw:
                return None, True
            try:
                return json.loads(raw), True
            except ValueError:
                return None, False

        def _dispatch(self, method: str) -> None:
            payload, valid = self._read_json()
            headers = {name.lower(): value for name, value in self.headers.items()}
            server._record(method, self.path, headers, payload)
            if server.latency_s:
                time.sleep(server.latency_s)
            if server.profile == "hf-router" and not _has_bearer(
                headers.get("authorization", "")
            ):
                self._send_json(server._error(401, "unauthorized", code="unauthorized"))
                return
            if not valid:
                self._send_json(server._error(400, "invalid JSON body"))
                return
            route = server._routes.get((method, self.path.split("?", 1)[0]))
            if route is None:
                self._send_json(server._error(404, "Not found", code="not_found"))
                return
            if method == "POST" and not isinstance(payload, dict):
                self._send_json(server._error(400, _OBJECT_REQUIRED))
                return
            handler, inference = route
            request = _Request(headers, payload if isinstance(payload, dict) else {})
            if inference:
                self._answer_inference(handler, request)
            else:
                self._send_json(handler(request))

        def _answer_inference(
            self, handler: Callable[[_Request], _Outcome], request: _Request
        ) -> None:
            fault = server._fault()
            if fault is not None:
                self._send_json(fault)
                return
            if server.slow_first_token:
                time.sleep(server.slow_first_token)
            outcome = handler(request)
            if outcome.status != 200:
                self._send_json(outcome)
                return
            if server.malformed:
                self._send_raw(
                    200, _MALFORMED_BODY, "application/json", outcome.headers
                )
                return
            chunks = outcome.chunks
            if chunks is None:
                if server.hang_after_tokens:
                    self._hold()
                    return
                self._send_json(outcome)
                return
            self._send_sse(chunks, outcome.headers)

        def _send_json(self, outcome: _Outcome) -> None:
            body = json.dumps(outcome.body).encode("utf-8")
            self._send_raw(outcome.status, body, "application/json", outcome.headers)

        def _send_raw(
            self,
            status: int,
            body: bytes,
            content_type: str,
            headers: tuple[tuple[str, str], ...],
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Fake-Generation", str(server.generation))
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            _write(self.wfile, body)

        def _send_sse(
            self, chunks: list[dict[str, Any]], headers: tuple[tuple[str, str], ...]
        ) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("X-Fake-Generation", str(server.generation))
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            write = functools.partial(_write, self.wfile)
            if _stream_sse(write, chunks, server.hang_after_tokens) == "hang":
                self._hold()
            self.close_connection = True

        def _hold(self) -> None:
            server.holds.append(
                _hold_connection(self.connection, server._stopping, HANG_CAP_S)
            )
            self.close_connection = True

    return Handler


# --- CLI ----------------------------------------------------------------------


def _serve_until(stop: threading.Event) -> None:
    stop.wait()


def main(
    argv: list[str] | None = None,
    *,
    stop: threading.Event | None = None,
    ready: Callable[[FakeOpenAIServer], None] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="fake-openai-v1",
        description="Fake OpenAI-compatible upstream (openai / ollama / hf-router / auth2api / lmstudio)",
    )
    parser.add_argument(
        "--port", type=int, default=0, help="TCP port on 127.0.0.1 (0 = ephemeral)"
    )
    parser.add_argument("--profile", choices=PROFILES, default="openai")
    parser.add_argument("--rate-limit-every", type=int, default=0, metavar="N")
    parser.add_argument("--fail-every", type=int, default=0, metavar="N")
    parser.add_argument(
        "--slow-first-token", type=float, default=0.0, metavar="SECONDS"
    )
    parser.add_argument("--hang-after-tokens", type=int, default=0, metavar="N")
    parser.add_argument("--malformed", action="store_true")
    parser.add_argument("--echo-secret", action="store_true")
    parser.add_argument("--drop-tool-calls", action="store_true")
    parser.add_argument("--flatten-refusal", action="store_true")
    parser.add_argument("--latency", type=float, default=0.0, metavar="SECONDS")
    parser.add_argument("--no-responses", dest="responses", action="store_false")
    parser.add_argument("--no-messages", dest="messages", action="store_false")
    parser.add_argument("--restart-every", type=float, default=0.0, metavar="SECONDS")
    args = parser.parse_args(argv)
    server = FakeOpenAIServer(
        args.profile,
        port=args.port,
        rate_limit_every=args.rate_limit_every,
        fail_every=args.fail_every,
        slow_first_token=args.slow_first_token,
        hang_after_tokens=args.hang_after_tokens,
        malformed=args.malformed,
        echo_secret=args.echo_secret,
        drop_tool_calls=args.drop_tool_calls,
        flatten_refusal=args.flatten_refusal,
        latency_s=args.latency,
        responses=args.responses,
        messages=args.messages,
        restart_every=args.restart_every,
    )
    server.start()
    print(
        f"SUCCESS:fake-openai-v1 listening={server.base_url} profile={server.profile}",
        flush=True,
    )
    if ready is not None:
        ready(server)
    try:
        _serve_until(stop if stop is not None else threading.Event())
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


if __name__ == "__main__":  # pragma: no cover - module entrypoint guard
    raise SystemExit(main())
