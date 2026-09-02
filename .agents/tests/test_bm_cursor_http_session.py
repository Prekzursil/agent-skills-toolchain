"""Session-refresh client for Basic Memory HTTP MCP (Cursor stale-session bug)."""

from __future__ import annotations

import io
import importlib.util
import json
import pathlib
import sys
from typing import Any
from unittest.mock import patch

SCRIPTS_ROOT = pathlib.Path(__file__).resolve().parents[1] / "scripts"


class _BinaryStream:
    def __init__(self, data: bytes = b"") -> None:
        self.buffer = io.BytesIO(data)


class _Session:
    def call_with_retry(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if method == "transport_failure":
            raise OSError("daemon unavailable")
        return {"jsonrpc": "2.0", "result": {"method": method, "params": params}}

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        return None


def load_bm():
    path = SCRIPTS_ROOT / "bm_cursor_http_session.py"
    spec = importlib.util.spec_from_file_location("bm_cursor_http_session", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bm_cursor_http_session"] = module
    spec.loader.exec_module(module)
    return module


def run_loop(bm, data: bytes) -> list[dict[str, Any]]:
    stdin = _BinaryStream(data)
    stdout = _BinaryStream()
    with (
        patch.object(bm.sys, "stdin", stdin),
        patch.object(bm.sys, "stdout", stdout),
    ):
        assert bm.stdio_loop(_Session()) == 0
    return [json.loads(line) for line in stdout.buffer.getvalue().splitlines() if line]


def test_parse_sse_message_event() -> None:
    bm = load_bm()
    raw = b'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n\n'
    parsed = bm.parse_rpc_body(raw, "text/event-stream")
    assert parsed["result"]["ok"] is True


def test_parse_empty_http_body_is_an_error() -> None:
    bm = load_bm()
    try:
        bm.parse_rpc_body(b"", "application/json")
    except ValueError as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("empty HTTP response must not become result: null")


def test_is_session_not_found() -> None:
    bm = load_bm()
    assert bm.is_session_not_found(
        {"error": {"code": -32600, "message": "Session not found"}}
    )
    assert not bm.is_session_not_found({"result": {}})
    assert not bm.is_session_not_found(
        {"error": {"code": -32601, "message": "Method not found"}}
    )


def test_call_retries_after_session_not_found() -> None:
    bm = load_bm()
    session = bm.BmHttpSession(url="http://127.0.0.1:8765/mcp")
    gone = {
        "jsonrpc": "2.0",
        "id": 2,
        "error": {"code": -32600, "message": "Session not found"},
    }
    init_ok = {
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "protocolVersion": "2025-03-26",
            "serverInfo": {"name": "Basic Memory"},
        },
    }
    call_ok = {
        "jsonrpc": "2.0",
        "id": 5,
        "result": {"content": [{"type": "text", "text": "ok"}]},
    }
    posts = [
        (init_ok, "sess-new"),
        ({}, None),
        (gone, None),
        (init_ok, "sess-newer"),
        ({}, None),
        (call_ok, "sess-newer"),
    ]

    def fake_post(payload: dict) -> tuple[dict, str | None]:
        if not posts:
            raise AssertionError(f"unexpected post {payload}")
        return posts.pop(0)

    with patch.object(session, "post_raw", side_effect=fake_post):
        result = session.call_with_retry(
            "tools/call", {"name": "search_notes", "arguments": {}}
        )

    assert result == call_ok
    assert session.session_id == "sess-newer"
    assert posts == []


def test_explicit_initialize_preserves_requested_protocol_without_notifying() -> None:
    bm = load_bm()
    session = bm.BmHttpSession(url="http://127.0.0.1:8765/mcp")
    payloads: list[dict[str, Any]] = []
    init_ok = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2025-06-18",
            "serverInfo": {"name": "Basic Memory"},
        },
    }

    def fake_post(payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        payloads.append(payload)
        return init_ok, "session-id"

    with patch.object(session, "post_raw", side_effect=fake_post):
        result = session.call_with_retry(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "cursor", "version": "1"},
            },
        )

    assert result == init_ok
    assert len(payloads) == 1
    assert payloads[0]["params"]["protocolVersion"] == "2025-06-18"


def test_reads_newline_delimited_json_rpc() -> None:
    bm = load_bm()
    message = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    stdin = _BinaryStream(json.dumps(message).encode("utf-8") + b"\n")

    with patch.object(bm.sys, "stdin", stdin):
        assert bm.read_stdio_message() == message


def test_writes_newline_delimited_utf8_json_rpc() -> None:
    bm = load_bm()
    message = {"jsonrpc": "2.0", "id": 1, "result": {"text": "memorie ✓"}}
    stdout = _BinaryStream()

    with patch.object(bm.sys, "stdout", stdout):
        bm.write_stdio_message(message)

    assert stdout.buffer.getvalue() == (
        json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n"
    )


def test_reads_legacy_content_length_frame() -> None:
    bm = load_bm()
    message = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    body = json.dumps(message).encode("utf-8")
    stdin = _BinaryStream(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)

    with patch.object(bm.sys, "stdin", stdin):
        assert bm.read_stdio_message() == message


def test_malformed_json_returns_parse_error_and_continues() -> None:
    bm = load_bm()
    valid = b'{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n'

    output = run_loop(bm, b"{oops}\n" + valid)

    assert output[0]["id"] is None
    assert output[0]["error"]["code"] == -32700
    assert output[1]["id"] == 2


def test_non_object_json_returns_invalid_request_and_continues() -> None:
    bm = load_bm()
    valid = b'{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n'

    output = run_loop(bm, b"[]\n" + valid)

    assert output[0]["error"]["code"] == -32600
    assert output[1]["id"] == 2


def test_invalid_content_length_does_not_consume_next_message() -> None:
    bm = load_bm()
    valid = b'{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n'

    output = run_loop(bm, b"Content-Length: -1\r\n\r\n" + valid)

    assert output[0]["error"]["code"] == -32600
    assert output[1]["id"] == 2


def test_transport_failure_returns_error_without_killing_proxy() -> None:
    bm = load_bm()
    failing = b'{"jsonrpc":"2.0","id":1,"method":"transport_failure","params":{}}\n'
    valid = b'{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n'

    output = run_loop(bm, failing + valid)

    assert output[0]["id"] == 1
    assert output[0]["error"]["code"] == -32000
    assert output[1]["id"] == 2
