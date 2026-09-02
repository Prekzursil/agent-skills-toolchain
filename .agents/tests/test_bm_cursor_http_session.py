"""Session-refresh client for Basic Memory HTTP MCP (Cursor stale-session bug).

The first twelve tests are the interim's own suite, imported from
``live-capture/2026-09-02`` (NDJSON framing, legacy Content-Length input,
session refresh retry, JSON-RPC errors for malformed input, survival of
transport errors). Everything after ``# --- hardening ---`` drives the bridge
against ``tools/mcp/mcp-http-host/_fake_streamable_http_daemon.py`` through the
two windows measured on the box in ``.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md``:
a watchdog restart that leaves the port healthy but every session id stale
(HTTP 404 + ``-32600 Session not found``), and the connection-refused window
while the daemon is dead or warming up (2.5-4 min measured).
"""

from __future__ import annotations

import io
import importlib.util
import json
import os
import pathlib
import sys
import threading
import time
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest

SCRIPTS_ROOT = pathlib.Path(__file__).resolve().parents[1] / "scripts"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FAKE_DAEMON_ROOT = REPO_ROOT / "tools" / "mcp" / "mcp-http-host"


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


# --- hardening ---------------------------------------------------------------
# Everything below runs against the fake Streamable-HTTP daemon that lives in the
# mcp-http-host lane, so the bridge is proven against the exact wire the MCP
# Python SDK (FastMCP / Basic Memory 3.x) speaks: sessions, the 404 + -32600
# body on a stale id, restart, the refused window, JSON and SSE, GET streams.


def load_fake_daemon():
    path = FAKE_DAEMON_ROOT / "_fake_streamable_http_daemon.py"
    assert path.is_file(), f"fixture missing: {path}"
    if str(FAKE_DAEMON_ROOT) not in sys.path:
        sys.path.insert(0, str(FAKE_DAEMON_ROOT))
    spec = importlib.util.spec_from_file_location("_fake_streamable_http_daemon", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_fake_streamable_http_daemon"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_daemon():
    fake = load_fake_daemon().FakeStreamableHttpDaemon()
    fake.start()
    try:
        yield fake
    finally:
        fake.close()


@pytest.fixture
def sse_daemon():
    prelude = [
        {
            "jsonrpc": "2.0",
            "method": "notifications/message",
            "params": {"level": "info", "data": "vector sync running"},
        }
    ]
    fake = load_fake_daemon().FakeStreamableHttpDaemon(
        response_mode="sse", sse_prelude=prelude
    )
    fake.start()
    try:
        yield fake
    finally:
        fake.close()


def whoami_pid(result: dict[str, Any]) -> int:
    return json.loads(result["result"]["content"][0]["text"])["pid"]


class _CollectingStdout:
    """A ``sys.stdout`` stand-in whose ``.buffer`` can be written from threads."""

    def __init__(self) -> None:
        self.buffer = self
        self._lines: list[bytes] = []
        self._pending = b""
        self._cond = threading.Condition()

    def write(self, data: bytes) -> int:
        with self._cond:
            self._pending += data
            while b"\n" in self._pending:
                line, self._pending = self._pending.split(b"\n", 1)
                if line:
                    self._lines.append(line)
            self._cond.notify_all()
        return len(data)

    def flush(self) -> None:
        return None

    def messages(self) -> list[dict[str, Any]]:
        with self._cond:
            return [json.loads(line) for line in self._lines]

    def wait_for(
        self, predicate: Callable[[dict[str, Any]], bool], timeout: float = 5.0
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        with self._cond:
            while True:
                for message in (json.loads(line) for line in self._lines):
                    if predicate(message):
                        return message
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError(
                        f"no stdout message matched within {timeout}s: {self._lines!r}"
                    )
                self._cond.wait(remaining)


class _PipeStdin:
    """A ``sys.stdin`` stand-in fed incrementally from the test thread."""

    def __init__(self) -> None:
        read_fd, write_fd = os.pipe()
        self.buffer = open(read_fd, "rb", buffering=0)
        self._writer = open(write_fd, "wb", buffering=0)

    def send(self, message: dict[str, Any]) -> None:
        self._writer.write(json.dumps(message).encode("utf-8") + b"\n")

    def close(self) -> None:
        self._writer.close()


class LiveLoop:
    """Run ``stdio_loop`` in a thread against pipe-backed stdio."""

    def __init__(self, bm, session, **loop_kwargs: Any) -> None:
        self.bm = bm
        self.stdin = _PipeStdin()
        self.stdout = _CollectingStdout()
        self.rc: int | None = None
        self._patches = [
            patch.object(bm.sys, "stdin", self.stdin),
            patch.object(bm.sys, "stdout", self.stdout),
        ]

        def run() -> None:
            self.rc = bm.stdio_loop(session, **loop_kwargs)

        self.thread = threading.Thread(target=run, daemon=True)

    def __enter__(self) -> LiveLoop:
        for p in self._patches:
            p.start()
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stdin.close()
        self.thread.join(timeout=10)
        for p in self._patches:
            p.stop()
        self.stdin.buffer.close()

    def request(
        self, rid: Any, method: str, params: dict[str, Any] | None = None
    ) -> dict:
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            message["params"] = params
        self.stdin.send(message)
        return self.stdout.wait_for(lambda m: m.get("id") == rid and "method" not in m)


INIT_PARAMS = {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "cursor", "version": "1"},
}
WHOAMI = {"name": "whoami", "arguments": {}}


def test_parse_sse_multi_event_body_yields_every_message_in_order() -> None:
    bm = load_bm()
    raw = (
        b'event: message\r\ndata: {"jsonrpc":"2.0","method":"notifications/message",'
        b'"params":{"level":"info","data":"warming"}}\r\n\r\n'
        b"event: message\n"
        b'data: {"jsonrpc":"2.0","id":4,\n'
        b'data: "result":{"ok":true}}\n\n'
        b": keepalive comment\n\n"
    )
    messages = bm.parse_rpc_messages(raw, "text/event-stream")
    assert [m.get("method") for m in messages] == ["notifications/message", None]
    assert messages[1] == {"jsonrpc": "2.0", "id": 4, "result": {"ok": True}}
    # the single-message helper picks the response, never the prelude
    assert bm.parse_rpc_body(raw, "text/event-stream")["id"] == 4


def test_is_session_not_found_accepts_the_sdk_404_body() -> None:
    bm = load_bm()
    fake = load_fake_daemon()
    assert bm.is_session_not_found(json.loads(fake.session_not_found_body()))
    assert bm.is_session_not_found(
        {
            "jsonrpc": "2.0",
            "id": "server-error",
            "error": {"code": -32600, "message": "Session not found"},
        }
    )
    assert not bm.is_session_not_found(
        {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Bad Request: Missing session ID"},
        }
    )


def test_tool_cache_roundtrips_and_ignores_a_corrupt_or_foreign_file(tmp_path) -> None:
    bm = load_bm()
    path = tmp_path / "cache.json"
    cache = bm.DiscoveryCache(path, url="http://127.0.0.1:8765/mcp")
    assert cache.load() is None

    init = {
        "protocolVersion": "2025-03-26",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "Basic Memory"},
    }
    tools = {"tools": [{"name": "search_notes", "inputSchema": {"type": "object"}}]}
    cache.save(init, tools)
    loaded = cache.load()
    assert loaded is not None
    assert loaded["initialize"] == init
    assert loaded["tools"] == tools
    assert not list(tmp_path.glob("*.tmp"))

    foreign = bm.DiscoveryCache(path, url="http://127.0.0.1:9999/mcp")
    assert foreign.load() is None  # a cache for another daemon is never served

    path.write_text("{not json", encoding="utf-8")
    assert cache.load() is None
    cache.save(init, tools)  # and it is recoverable
    assert cache.load() is not None

    disabled = bm.DiscoveryCache(None, url="http://127.0.0.1:8765/mcp")
    disabled.save(init, tools)
    assert disabled.load() is None


def test_session_heals_after_a_watchdog_restart_in_json_mode(fake_daemon) -> None:
    bm = load_bm()
    session = bm.BmHttpSession(url=fake_daemon.url, reconnect_delay=0.01)

    first = session.call_with_retry("tools/call", WHOAMI)
    first_sid = session.session_id
    assert whoami_pid(first) == os.getpid()
    assert first_sid in fake_daemon.live_sessions()

    fake_daemon.restart()  # port healthy, every session id now stale

    healed = session.call_with_retry("tools/call", WHOAMI)
    assert whoami_pid(healed) == os.getpid()
    assert session.session_id != first_sid
    assert session.session_id in fake_daemon.live_sessions()
    methods = [r["method"] for r in fake_daemon.requests if r["verb"] == "POST"]
    assert methods == [
        "initialize",
        "notifications/initialized",
        "tools/call",
        "tools/call",  # rejected with 404 Session not found ...
        "initialize",  # ... so the bridge re-initializes ...
        "notifications/initialized",
        "tools/call",  # ... and replays the call once
    ]
    assert session.server_info["generation"] == 2


def test_session_heals_in_sse_mode_and_relays_prelude_notifications(sse_daemon) -> None:
    bm = load_bm()
    relayed: list[dict[str, Any]] = []
    session = bm.BmHttpSession(
        url=sse_daemon.url, reconnect_delay=0.01, on_server_message=relayed.append
    )

    result = session.call_with_retry("tools/list")
    assert [t["name"] for t in result["result"]["tools"]] == ["whoami"]
    assert relayed and relayed[-1]["method"] == "notifications/message"

    sse_daemon.restart()
    result = session.call_with_retry("tools/call", WHOAMI)
    assert whoami_pid(result) == os.getpid()
    assert session.server_info["generation"] == 2
    assert all(m["method"] == "notifications/message" for m in relayed)


def test_refused_window_raises_transport_unavailable_then_recovers(fake_daemon) -> None:
    bm = load_bm()
    session = bm.BmHttpSession(url=fake_daemon.url, reconnect_delay=0.01)
    assert whoami_pid(session.call_with_retry("tools/call", WHOAMI)) == os.getpid()

    fake_daemon.stop()  # the daemon died; the port refuses connections
    with pytest.raises(bm.TransportUnavailable) as exc:
        session.call_with_retry("tools/call", WHOAMI)
    assert isinstance(exc.value, OSError)  # the stdio loop's existing contract
    assert fake_daemon.url in str(exc.value)
    assert session.session_id is None and not session.initialized

    fake_daemon.start()  # watchdog relaunch: a new process, no sessions
    healed = session.call_with_retry("tools/call", WHOAMI)
    assert whoami_pid(healed) == os.getpid()
    assert session.server_info["generation"] == 2


def test_hung_daemon_times_out_as_transport_unavailable(fake_daemon) -> None:
    bm = load_bm()
    fake_daemon.response_delay = 0.6
    session = bm.BmHttpSession(
        url=fake_daemon.url, timeout=0.15, handshake_timeout=0.15, reconnect_delay=0.0
    )
    with pytest.raises(bm.TransportUnavailable):
        session.call_with_retry("ping")
    assert not session.initialized


def test_stdio_loop_serves_cached_discovery_while_the_daemon_is_down(
    fake_daemon, tmp_path
) -> None:
    bm = load_bm()
    cache_path = tmp_path / "bm-cache.json"

    # Day 1: daemon up. Cursor discovers, the bridge remembers.
    cache = bm.DiscoveryCache(cache_path, url=fake_daemon.url)
    session = bm.BmHttpSession(url=fake_daemon.url, reconnect_delay=0.01)
    with LiveLoop(bm, session, cache=cache) as loop:
        init = loop.request(1, "initialize", INIT_PARAMS)
        assert init["result"]["serverInfo"]["name"] == "fake-mcp"
        loop.stdin.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools = loop.request(2, "tools/list")
        assert [t["name"] for t in tools["result"]["tools"]] == ["whoami"]
    assert loop.rc == 0
    assert cache_path.is_file()

    # Day 2: Cursor starts while the daemon is dead (refused). No red, no lost tools.
    fake_daemon.stop()
    session = bm.BmHttpSession(url=fake_daemon.url, reconnect_delay=0.01)
    cache = bm.DiscoveryCache(cache_path, url=fake_daemon.url)
    with LiveLoop(bm, session, cache=cache) as loop:
        init = loop.request(1, "initialize", INIT_PARAMS)
        assert "error" not in init
        assert init["result"]["protocolVersion"] == "2025-06-18"  # cached negotiation
        assert init["result"]["serverInfo"]["name"] == "fake-mcp"
        assert init["result"]["capabilities"]["tools"]["listChanged"] is True
        loop.stdin.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        tools = loop.request(2, "tools/list")
        assert [t["name"] for t in tools["result"]["tools"]] == ["whoami"]
        assert loop.request(3, "ping")["result"] == {}
        assert loop.request(4, "resources/list")["result"] == {"resources": []}
        assert loop.request(5, "prompts/list")["result"] == {"prompts": []}

        call = loop.request(6, "tools/call", WHOAMI)
        assert "error" not in call  # a tool error the model can read, not a dead server
        assert call["result"]["isError"] is True
        text = call["result"]["content"][0]["text"]
        assert fake_daemon.url in text and "refused" in text.lower()

        # The watchdog brings the daemon back: the very next call heals.
        fake_daemon.start()
        healed = loop.request(7, "tools/call", WHOAMI)
        assert whoami_pid(healed) == os.getpid()
        assert session.server_info["generation"] == 2
    assert loop.rc == 0
    relaunch_posts = [
        r["method"]
        for r in fake_daemon.requests
        if r["verb"] == "POST" and r["generation"] == 2
    ]
    # heal, replay the call, then re-check the tool list against what was served
    assert relaunch_posts == [
        "initialize",
        "notifications/initialized",
        "tools/call",
        "tools/list",
    ]
    # the cached list matched the live one, so Cursor was not told to refresh
    assert not any(
        m.get("method") == "notifications/tools/list_changed"
        for m in loop.stdout.messages()
    )


def test_stdio_loop_cold_start_without_cache_recovers_and_announces_tools(
    fake_daemon, tmp_path
) -> None:
    bm = load_bm()
    fake_daemon.stop()
    cache = bm.DiscoveryCache(tmp_path / "empty-cache.json", url=fake_daemon.url)
    session = bm.BmHttpSession(url=fake_daemon.url, reconnect_delay=0.0)
    with LiveLoop(bm, session, cache=cache, probe_interval=0.05) as loop:
        init = loop.request(1, "initialize", INIT_PARAMS)
        assert "error" not in init
        assert init["result"]["protocolVersion"] == bm.PROTOCOL
        assert init["result"]["capabilities"]["tools"]["listChanged"] is True
        loop.stdin.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert loop.request(2, "tools/list")["result"] == {"tools": []}

        fake_daemon.start()
        loop.stdout.wait_for(
            lambda m: m.get("method") == "notifications/tools/list_changed"
        )
        tools = loop.request(3, "tools/list")
        assert [t["name"] for t in tools["result"]["tools"]] == ["whoami"]
        assert whoami_pid(loop.request(4, "tools/call", WHOAMI)) == os.getpid()
    assert loop.rc == 0
    assert cache.load() is not None  # the recovery primed the cache for next time


def test_get_stream_relays_server_notifications_and_requests(fake_daemon) -> None:
    bm = load_bm()
    session = bm.BmHttpSession(url=fake_daemon.url, reconnect_delay=0.01)
    with LiveLoop(bm, session, stream=True) as loop:
        loop.request(1, "initialize", INIT_PARAMS)
        loop.stdin.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        sid = session.session_id
        assert sid is not None
        deadline = time.monotonic() + 5
        while (
            fake_daemon.push(sid, {"jsonrpc": "2.0", "method": "notifications/ping"})
            == 0
        ):
            assert time.monotonic() < deadline, "bridge never opened the GET stream"
            time.sleep(0.02)
        loop.stdout.wait_for(lambda m: m.get("method") == "notifications/ping")

        fake_daemon.push(sid, {"jsonrpc": "2.0", "id": "srv-1", "method": "roots/list"})
        loop.stdout.wait_for(
            lambda m: m.get("method") == "roots/list" and m.get("id") == "srv-1"
        )
        loop.stdin.send({"jsonrpc": "2.0", "id": "srv-1", "result": {"roots": []}})
        deadline = time.monotonic() + 5
        while not fake_daemon.client_responses:
            assert time.monotonic() < deadline, (
                "client response never reached the daemon"
            )
            time.sleep(0.02)
        assert fake_daemon.client_responses == [
            {"jsonrpc": "2.0", "id": "srv-1", "result": {"roots": []}}
        ]
    assert loop.rc == 0


def test_get_stream_eof_marks_the_session_gone_so_the_next_call_skips_the_404(
    fake_daemon,
) -> None:
    bm = load_bm()
    session = bm.BmHttpSession(url=fake_daemon.url, reconnect_delay=0.01)
    with LiveLoop(bm, session, stream=True) as loop:
        loop.request(1, "initialize", INIT_PARAMS)
        loop.stdin.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        sid = session.session_id
        deadline = time.monotonic() + 5
        # Wait until the bridge has both forwarded Cursor's initialized notification
        # and opened its GET stream, so the restart below is the only thing that
        # can produce a stale-session POST.
        while not (
            any(
                r["verb"] == "GET" and r["session_id"] == sid
                for r in fake_daemon.requests
            )
            and any(
                r["verb"] == "POST" and r["method"] == "notifications/initialized"
                for r in fake_daemon.requests
            )
        ):
            assert time.monotonic() < deadline
            time.sleep(0.02)

        fake_daemon.restart()  # closes the GET stream: the bridge learns before Cursor asks
        deadline = time.monotonic() + 5
        while session.initialized:
            assert time.monotonic() < deadline, (
                "stream EOF did not mark the session gone"
            )
            time.sleep(0.02)

        result = loop.request(2, "tools/call", WHOAMI)
        assert whoami_pid(result) == os.getpid()
    stale_posts = [
        r
        for r in fake_daemon.requests
        if r["verb"] == "POST" and r["session_id"] == sid and r["generation"] == 2
    ]
    assert stale_posts == []  # no round-trip was wasted on the dead session


def test_stdin_eof_terminates_the_upstream_session(fake_daemon) -> None:
    bm = load_bm()
    session = bm.BmHttpSession(url=fake_daemon.url, reconnect_delay=0.01)
    with LiveLoop(bm, session) as loop:
        loop.request(1, "initialize", INIT_PARAMS)
        sid = session.session_id
    assert loop.rc == 0
    assert any(
        r["verb"] == "DELETE" and r["session_id"] == sid for r in fake_daemon.requests
    )
    assert sid not in fake_daemon.live_sessions()


def test_main_health_and_call_modes(fake_daemon, capsys) -> None:
    bm = load_bm()
    assert bm.main(["--health", "--url", fake_daemon.url]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["serverInfo"]["name"] == "fake-mcp"
    assert report["url"] == fake_daemon.url

    assert bm.main(["--call", "whoami", "{}", "--url", fake_daemon.url]) == 0
    called = json.loads(capsys.readouterr().out)
    assert whoami_pid(called) == os.getpid()

    fake_daemon.stop()
    assert (
        bm.main(["--health", "--url", fake_daemon.url, "--reconnect-delay", "0"]) == 1
    )
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False and "refused" in report["error"].lower()
