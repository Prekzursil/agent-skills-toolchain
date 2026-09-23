"""pytest wiring for tools/endpoint-eval.

The package directory carries a hyphen, so the flat modules are imported by putting the
package root on ``sys.path`` (the same idiom the ``.agents/scripts`` tests use).

``StubOpenAI`` is a tiny in-test ``http.server`` that speaks just enough of the OpenAI
``/v1`` wire for the contract and capability suites. It exists so the suites' own unit
tests never depend on the inference-hub fake server, which lands from another work unit.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

REPO_ROOT = PACKAGE_ROOT.parents[1]


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload).encode("utf-8")


class StubState:
    """Mutable behaviour knobs shared between a stub server and the test driving it."""

    def __init__(self, mode: str = "ok") -> None:
        self.mode = mode
        self.requests: list[dict[str, Any]] = []
        self.models: list[str] = ["stub-model"]


class _Handler(BaseHTTPRequestHandler):
    state: StubState

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    def _send(
        self, status: int, body: bytes, content_type: str = "application/json"
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if status == 429:
            self.send_header("Retry-After", "1")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib name
        if self.path.endswith("/models"):
            if self.state.mode == "models-broken":
                self._send(200, b"not json")
                return
            if self.state.mode == "models-empty":
                self._send(200, _json_bytes({"object": "list", "data": []}))
                return
            data = [{"id": mid, "object": "model"} for mid in self.state.models]
            self._send(200, _json_bytes({"object": "list", "data": data}))
            return
        self._send(404, _json_bytes({"error": {"message": "no such path"}}))

    def do_POST(self) -> None:  # noqa: N802 - stdlib name
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            request = json.loads(raw)
        except ValueError:
            request = {"_raw": raw.decode("utf-8", "replace")}
        request["_authorization"] = self.headers.get("Authorization")
        self.state.requests.append(request)
        mode = self.state.mode
        if mode == "429":
            self._send(
                429, _json_bytes({"error": {"message": "slow down", "type": "rate"}})
            )
            return
        if mode == "503":
            self._send(
                503, _json_bytes({"error": {"message": "down", "type": "server"}})
            )
            return
        if mode == "500":
            self._send(
                500, _json_bytes({"error": {"message": "boom", "type": "server"}})
            )
            return
        if mode == "401":
            self._send(401, _json_bytes({"error": {"message": "missing bearer"}}))
            return
        if mode == "hub-code":
            body = {"error": {"message": "halted", "type": "hub", "code": "HALTED"}}
            self._send(500, _json_bytes(body))
            return
        if mode == "error-no-body":
            self._send(418, b"")
            return
        if mode == "malformed":
            self._send(200, b"{not json")
            return
        if mode == "no-choices":
            self._send(200, _json_bytes({"object": "chat.completion", "choices": []}))
            return
        if mode == "slow":
            time.sleep(2.0)
            self._send(200, _json_bytes(self._completion(request)))
            return
        if mode == "ollama":
            if request.get("model") not in self.state.models:
                self._send(404, _json_bytes({"error": {"message": "model not found"}}))
                return
            if "tool_choice" in request:
                self._send(
                    400, _json_bytes({"error": {"message": "tool_choice unsupported"}})
                )
                return
        if request.get("stream"):
            self._stream(request)
            return
        self._send(200, _json_bytes(self._completion(request)))

    def _last_user_text(self, request: dict[str, Any]) -> str:
        for message in reversed(request.get("messages") or []):
            if message.get("role") == "user":
                content = message.get("content")
                if isinstance(content, list):
                    return " ".join(
                        str(part.get("text", ""))
                        for part in content
                        if isinstance(part, dict)
                    )
                return str(content)
        return ""

    def _completion(self, request: dict[str, Any]) -> dict[str, Any]:
        mode = self.state.mode
        text = self._last_user_text(request)
        content: str | None = f"echo:{text}"
        if mode == "wrong-echo":
            content = "echo:something-else"
        message: dict[str, Any] = {"role": "assistant", "content": content}
        finish = "stop"
        tools = request.get("tools") or []
        if tools and mode not in {"no-tool-calls", "drop-tool-calls"}:
            name = tools[0]["function"]["name"]
            args: dict[str, Any] = {"nonce": _nonce_from(text)}
            if mode == "bad-args":
                arguments = "{not json"
            else:
                arguments = json.dumps(args)
            call = {
                "id": "call_1",
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
            if mode == "no-call-id":
                del call["id"]
            message["tool_calls"] = [call]
            message["content"] = None
            finish = "tool_calls"
        elif tools and mode == "drop-tool-calls":
            message["content"] = (
                f'<tool_call>{{"name": "{tools[0]["function"]["name"]}"}}</tool_call>'
            )
        if request.get("response_format") and mode != "bad-json-content":
            schema = request["response_format"].get("json_schema", {}).get("schema", {})
            message["content"] = json.dumps(_instance_for(schema, text))
        elif request.get("response_format"):
            message["content"] = "not json at all"
        body: dict[str, Any] = {
            "id": "chatcmpl-stub",
            "object": "chat.completion",
            "created": 0,
            "model": request.get("model", "stub-model"),
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        }
        if mode != "no-usage":
            body["usage"] = {
                "prompt_tokens": 3,
                "completion_tokens": 2,
                "total_tokens": 5,
            }
        return body

    def _stream(self, request: dict[str, Any]) -> None:
        mode = self.state.mode
        completion = self._completion(request)
        content = completion["choices"][0]["message"].get("content") or ""
        if mode == "stream-mismatch":
            content = content + "-drift"
        pieces = [content[i : i + 3] for i in range(0, len(content), 3)] or [""]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for index, piece in enumerate(pieces):
            chunk = {
                "id": "chatcmpl-stub",
                "object": "chat.completion.chunk",
                "choices": [
                    {"index": 0, "delta": {"content": piece}, "finish_reason": None}
                ],
            }
            self.wfile.write(b"data: " + _json_bytes(chunk) + b"\n\n")
            self.wfile.flush()
            if mode == "hang" and index == 0:
                time.sleep(2.0)
                return
            if mode == "stream-eof" and index == 0:
                return
        if mode == "stream-eof-empty":
            return
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def _nonce_from(text: str) -> str:
    marker = '"nonce": "'
    if marker in text:
        return text.split(marker, 1)[1].split('"', 1)[0]
    return "0"


def _instance_for(schema: dict[str, Any], text: str) -> Any:
    kind = schema.get("type")
    if kind == "object":
        out: dict[str, Any] = {}
        for key in schema.get("required", []):
            out[key] = _instance_for(schema.get("properties", {}).get(key, {}), text)
        if "nonce" in out:
            out["nonce"] = _nonce_from(text)
        return out
    if kind == "array":
        return [_instance_for(schema.get("items", {}), text)]
    if kind == "integer":
        return 1
    if kind == "number":
        return 1.5
    if kind == "boolean":
        return True
    if "enum" in schema:
        return schema["enum"][0]
    return "text"


class StubOpenAI:
    """In-process OpenAI-wire stub. ``base_url`` ends in ``/v1``."""

    def __init__(self, mode: str = "ok") -> None:
        self.state = StubState(mode)
        handler = type("StubHandler", (_Handler,), {"state": self.state})
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> StubOpenAI:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/v1"

    @property
    def requests(self) -> list[dict[str, Any]]:
        return self.state.requests


@pytest.fixture
def stub() -> Iterator[StubOpenAI]:
    server = StubOpenAI().start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def stub_factory() -> Iterator[Any]:
    started: list[StubOpenAI] = []

    def make(mode: str = "ok") -> StubOpenAI:
        server = StubOpenAI(mode).start()
        started.append(server)
        return server

    try:
        yield make
    finally:
        for server in started:
            server.stop()


def free_port_url() -> str:
    """A loopback ``/v1`` URL nothing listens on (connection refused)."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}/v1"
