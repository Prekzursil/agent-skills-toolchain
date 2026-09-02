#!/usr/bin/env python3
"""Fake Streamable-HTTP MCP daemon shaped like the Basic Memory :8765 service.

``_fake_mcp_server.py`` is the deterministic stdio fixture; this wraps its
``handle()`` in the HTTP behaviour of the MCP Python SDK's
``StreamableHTTPSessionManager`` (what FastMCP, and therefore Basic Memory 3.x,
runs), so a transport can be tested against the failure windows measured on the
box in ``.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md``:

* ``initialize`` issues a fresh ``Mcp-Session-Id``; every later POST must carry it.
* a stale / unknown id gets **HTTP 404** whose body is the SDK's JSON-RPC error
  ``{"jsonrpc":"2.0","id":null,"error":{"code":-32600,"message":"Session not found"}}``
  (py.sdk.modelcontextprotocol.io/troubleshooting, "MCPError: Session not found").
* ``restart()`` is a watchdog restart: every session is forgotten, open GET
  streams close, ``generation`` increments (visible in ``serverInfo``).
* ``stop()`` / ``start()`` open and close a connection-refused window on the SAME
  port; a start after a stop is a new process, so sessions are gone too.
* responses render as ``application/json`` or as SSE (``event: message`` /
  ``data:``), optionally preceded by notification events, chunked like uvicorn.
* ``GET /mcp`` opens a server->client SSE stream (406 without the SSE Accept
  header - the shape the on-box health probe relies on); ``push()`` delivers a
  message on it; ``DELETE`` terminates a session.

stdlib only. Run standalone to rehearse a client by hand::

    python _fake_streamable_http_daemon.py --port 8799 --mode sse
"""

from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fake_mcp_server import handle as _stdio_handle  # noqa: E402

SESSION_HEADER = "Mcp-Session-Id"
MCP_PATH = "/mcp"


def session_not_found_body() -> bytes:
    """The exact 404 body the MCP Python SDK returns for a stale session id."""
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Session not found"},
        }
    ).encode("utf-8")


def _sse_event(message: dict[str, Any], event_id: str | None = None) -> bytes:
    lines = [b"event: message"]
    if event_id is not None:
        lines.append(f"id: {event_id}".encode("ascii"))
    lines.append(b"data: " + json.dumps(message).encode("utf-8"))
    return b"\n".join(lines) + b"\n\n"


class _Session:
    def __init__(self, session_id: str) -> None:
        self.id = session_id
        self.closed = False
        self.streams: list[queue.Queue[dict[str, Any] | None]] = []
        self.lock = threading.Lock()

    def attach_stream(self) -> queue.Queue[dict[str, Any] | None]:
        sink: queue.Queue[dict[str, Any] | None] = queue.Queue()
        with self.lock:
            self.streams.append(sink)
        return sink

    def detach_stream(self, sink: queue.Queue[dict[str, Any] | None]) -> None:
        with self.lock:
            if sink in self.streams:
                self.streams.remove(sink)

    def push(self, message: dict[str, Any]) -> int:
        with self.lock:
            for sink in self.streams:
                sink.put(message)
            return len(self.streams)

    def close(self) -> None:
        with self.lock:
            self.closed = True
            for sink in self.streams:
                sink.put(None)


class FakeStreamableHttpDaemon:
    """Drive from tests: ``start()`` / ``stop()`` / ``restart()`` / ``push()``."""

    def __init__(
        self,
        port: int = 0,
        host: str = "127.0.0.1",
        response_mode: str = "json",
        sse_prelude: list[dict[str, Any]] | None = None,
        allow_get_stream: bool = True,
        delete_status: int = 200,
        response_delay: float = 0.0,
    ) -> None:
        if response_mode not in ("json", "sse"):
            raise ValueError("response_mode must be 'json' or 'sse'")
        self.host = host
        self.port = port
        self.response_mode = response_mode
        # Notifications emitted on the POST SSE stream BEFORE the response, the
        # way a FastMCP tool that logs through its context does.
        self.sse_prelude: list[dict[str, Any]] = list(sse_prelude or [])
        self.allow_get_stream = allow_get_stream
        self.delete_status = delete_status
        # Seconds to sit on a POST before answering: the "bound but HTTP
        # unresponsive" strike the watchdog measures under RAM pressure.
        self.response_delay = response_delay
        self.extra_tools: list[dict[str, Any]] = []
        self.generation = 0
        self.sessions: dict[str, _Session] = {}
        self.sessions_issued: list[str] = []
        self.requests: list[dict[str, Any]] = []
        self.client_responses: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()

    # -- lifecycle -----------------------------------------------------------

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def url(self) -> str:
        return self.base_url + MCP_PATH

    @property
    def running(self) -> bool:
        return self._httpd is not None

    def start(self) -> "FakeStreamableHttpDaemon":
        if self._httpd is not None:
            return self
        self._stopping.clear()
        # A start after a stop is a NEW process: nothing survives the restart.
        self._forget_all_sessions()
        self.generation += 1
        handler = _make_handler(self)
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, kwargs={"poll_interval": 0.05}
        )
        self._thread.daemon = True
        self._thread.start()
        return self

    def stop(self) -> None:
        """Unbind the port: every new connection is refused until ``start()``."""
        httpd = self._httpd
        if httpd is None:
            return
        self._stopping.set()
        self._forget_all_sessions()
        httpd.shutdown()
        httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._httpd = None
        self._thread = None

    def restart(self) -> None:
        """Watchdog restart without a refused window: sessions gone, port up."""
        with self._lock:
            self.generation += 1
        self._forget_all_sessions()

    def close(self) -> None:
        self.stop()

    def __enter__(self) -> "FakeStreamableHttpDaemon":
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- session bookkeeping -------------------------------------------------

    def _forget_all_sessions(self) -> None:
        with self._lock:
            sessions = list(self.sessions.values())
            self.sessions.clear()
        for session in sessions:
            session.close()

    def new_session(self) -> _Session:
        session = _Session(uuid.uuid4().hex)
        with self._lock:
            self.sessions[session.id] = session
            self.sessions_issued.append(session.id)
        return session

    def get_session(self, session_id: str | None) -> _Session | None:
        if not session_id:
            return None
        with self._lock:
            return self.sessions.get(session_id)

    def terminate_session(self, session_id: str) -> bool:
        with self._lock:
            session = self.sessions.pop(session_id, None)
        if session is None:
            return False
        session.close()
        return True

    def push(self, session_id: str, message: dict[str, Any]) -> int:
        """Deliver a server->client message on that session's GET stream(s)."""
        session = self.get_session(session_id)
        if session is None:
            return 0
        return session.push(message)

    def live_sessions(self) -> list[str]:
        with self._lock:
            return list(self.sessions)

    # -- JSON-RPC semantics --------------------------------------------------

    def answer(self, message: dict[str, Any]) -> dict[str, Any] | None:
        response = _stdio_handle(message)
        if response is None or "result" not in response:
            return response
        method = message.get("method")
        if method == "initialize":
            response["result"]["serverInfo"]["generation"] = self.generation
            response["result"]["capabilities"] = {
                "tools": {"listChanged": True},
                "resources": {},
                "prompts": {},
                "logging": {},
            }
        elif method == "tools/list" and self.extra_tools:
            response["result"]["tools"] = list(response["result"]["tools"]) + [
                dict(tool) for tool in self.extra_tools
            ]
        return response

    def record(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self.requests.append(entry)


def _make_handler(daemon: FakeStreamableHttpDaemon) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # -- helpers ---------------------------------------------------------

        def _path(self) -> str:
            return self.path.split("?", 1)[0]

        def _session_header(self) -> str | None:
            return self.headers.get(SESSION_HEADER) or self.headers.get(
                SESSION_HEADER.lower()
            )

        def _accepts(self, media: str) -> bool:
            accept = self.headers.get("Accept", "")
            return media in accept or "*/*" in accept

        def _send(
            self,
            status: int,
            body: bytes,
            content_type: str = "application/json",
            session_id: str | None = None,
        ) -> None:
            try:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                if session_id:
                    self.send_header(SESSION_HEADER, session_id)
                self.end_headers()
                if body:
                    self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the client timed out and left: a hung-daemon rehearsal

        def _send_rpc_error(
            self, status: int, code: int, message: str, session_id: str | None = None
        ) -> None:
            body = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": code, "message": message},
                }
            ).encode("utf-8")
            self._send(status, body, session_id=session_id)

        def _send_chunked_sse(self, events: list[bytes], session_id: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header(SESSION_HEADER, session_id)
            self.end_headers()
            for event in events:
                self.wfile.write(f"{len(event):x}\r\n".encode("ascii"))
                self.wfile.write(event)
                self.wfile.write(b"\r\n")
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()

        def _read_json(self) -> Any:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b""
            return json.loads(raw)

        # -- verbs -----------------------------------------------------------

        def do_POST(self) -> None:  # noqa: N802 (stdlib name)
            if self._path() != MCP_PATH:
                self._send(404, b"not found", content_type="text/plain")
                return
            if not (
                self._accepts("application/json") and self._accepts("text/event-stream")
            ):
                self._send_rpc_error(
                    406,
                    -32600,
                    "Not Acceptable: Client must accept both application/json and text/event-stream",
                )
                return
            if "application/json" not in self.headers.get("Content-Type", ""):
                self._send_rpc_error(
                    415,
                    -32600,
                    "Unsupported Media Type: Content-Type must be application/json",
                )
                return
            try:
                message = self._read_json()
            except (json.JSONDecodeError, ValueError):
                self._send_rpc_error(400, -32700, "Parse error: Invalid JSON")
                return
            if not isinstance(message, dict):
                self._send_rpc_error(
                    400, -32600, "Invalid Request: batches are not accepted"
                )
                return

            requested = self._session_header()
            daemon.record(
                {
                    "verb": "POST",
                    "session_id": requested,
                    "method": message.get("method"),
                    "id": message.get("id"),
                    "generation": daemon.generation,
                }
            )

            if message.get("method") == "initialize":
                session = daemon.new_session()
            else:
                if not requested:
                    self._send_rpc_error(400, -32600, "Bad Request: Missing session ID")
                    return
                session = daemon.get_session(requested)
                if session is None:
                    self._send(404, session_not_found_body())
                    return

            if daemon.response_delay:
                time.sleep(daemon.response_delay)

            if "method" not in message:
                # A JSON-RPC response to a server->client request: accepted, no body.
                daemon.client_responses.append(message)
                self._send(202, b"", session_id=session.id)
                return

            response = daemon.answer(message)
            if response is None:
                self._send(202, b"", session_id=session.id)
                return
            if daemon.response_mode == "sse":
                events = [_sse_event(note) for note in daemon.sse_prelude]
                events.append(_sse_event(response))
                self._send_chunked_sse(events, session.id)
                return
            self._send(200, json.dumps(response).encode("utf-8"), session_id=session.id)

        def do_GET(self) -> None:  # noqa: N802 (stdlib name)
            if self._path() != MCP_PATH:
                self._send(404, b"not found", content_type="text/plain")
                return
            if not self._accepts("text/event-stream"):
                # Measured on the box: a bare GET /mcp answers 406 while healthy.
                self._send_rpc_error(
                    406, -32600, "Not Acceptable: Client must accept text/event-stream"
                )
                return
            requested = self._session_header()
            daemon.record(
                {
                    "verb": "GET",
                    "session_id": requested,
                    "generation": daemon.generation,
                }
            )
            if not daemon.allow_get_stream:
                self._send(405, b"", content_type="text/plain")
                return
            if not requested:
                self._send_rpc_error(400, -32600, "Bad Request: Missing session ID")
                return
            session = daemon.get_session(requested)
            if session is None:
                self._send(404, session_not_found_body())
                return
            sink = session.attach_stream()
            # Chunked like uvicorn's SSE responses: the client must parse events
            # as they arrive, not wait for a Content-Length it will never get.
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Connection", "close")
            self.send_header(SESSION_HEADER, session.id)
            self.end_headers()
            try:
                self._write_chunk(b": stream open\n\n")
                while not daemon._stopping.is_set() and not session.closed:
                    try:
                        message = sink.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if message is None:
                        break
                    self._write_chunk(_sse_event(message))
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                session.detach_stream(sink)
            self.close_connection = True

        def _write_chunk(self, data: bytes) -> None:
            self.wfile.write(f"{len(data):x}\r\n".encode("ascii"))
            self.wfile.write(data)
            self.wfile.write(b"\r\n")
            self.wfile.flush()

        def do_DELETE(self) -> None:  # noqa: N802 (stdlib name)
            if self._path() != MCP_PATH:
                self._send(404, b"not found", content_type="text/plain")
                return
            requested = self._session_header()
            daemon.record(
                {
                    "verb": "DELETE",
                    "session_id": requested,
                    "generation": daemon.generation,
                }
            )
            if daemon.delete_status == 405:
                self._send(405, b"", content_type="text/plain")
                return
            if not requested or not daemon.terminate_session(requested):
                self._send(404, session_not_found_body())
                return
            self._send(200, b"", content_type="text/plain")

        def log_message(self, *args: Any) -> None:  # silence the access log
            pass

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fake Basic-Memory-shaped Streamable-HTTP daemon"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--mode", choices=("json", "sse"), default="json")
    parser.add_argument(
        "--restart-every",
        type=float,
        default=0.0,
        help="seconds between simulated watchdog restarts (0 = never)",
    )
    args = parser.parse_args(argv)
    daemon = FakeStreamableHttpDaemon(
        port=args.port, host=args.host, response_mode=args.mode
    )
    daemon.start()
    print(
        f"fake streamable-http daemon at {daemon.url} (mode={args.mode})",
        file=sys.stderr,
    )
    try:
        while True:
            time.sleep(args.restart_every or 3600)
            if args.restart_every:
                daemon.restart()
                print(f"restarted: generation={daemon.generation}", file=sys.stderr)
    except KeyboardInterrupt:
        pass
    finally:
        daemon.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
