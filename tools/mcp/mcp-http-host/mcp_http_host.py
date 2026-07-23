#!/usr/bin/env python3
"""mcp-http-host - share ONE stdio MCP server across many clients over HTTP.

The cure for per-session MCP process multiplication.  Today every Claude Code
session spawns its OWN stdio copy of every MCP server listed in the config
(``S`` sessions x 1 stdio child = ``S`` processes per server, before that
server's own lazy backends).  This host inverts that: ONE long-lived
``mcp-http-host`` process wraps ONE stdio child and serves ALL sessions over a
fixed ``127.0.0.1`` Streamable-HTTP endpoint.  Sessions register the server as
``{"type": "http", "url": "http://127.0.0.1:<port>/mcp"}`` instead of
``{"type": "stdio", ...}``, so ``S`` sessions collapse to ``1`` shared child
(it removes ``S - 1`` copies of that server, and its backends spawn once, not
once per session).

Transport = MCP "Streamable HTTP": the client POSTs a JSON-RPC message to a
single endpoint; the server answers with ``application/json`` for a
request/response, or ``202 Accepted`` for a notification (no ``id``).  An
``Mcp-Session-Id`` is issued on ``initialize`` and echoed back; because the one
shared child is session-agnostic (the multiplexer hubs answer ``initialize`` /
``tools/list`` from committed caches and hold no per-connection state) the id is
advisory and is not used to route.  See README.md for the honest scope: this
sharing model fits stateless / session-agnostic servers (the hubs); a strongly
stateful server should instead expose its OWN native streamable-HTTP mode.

stdlib only (``http.server`` + ``subprocess`` + ``threading``) - matches the
hub servers' stdlib-only ethos and runs on the bundled ``C:\\Python314\\python.exe``.

Usage::

    python mcp_http_host.py --port 8900 -- C:\\Python314\\python.exe path\\to\\hub.py
    python mcp_http_host.py --port 8900 --eager -- python hub.py
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

HOST_VERSION = "0.1.0"
DEFAULT_PORT = 8900
DEFAULT_MCP_PATH = "/mcp"
DEFAULT_HEALTH_PATH = "/healthz"
REQUEST_TIMEOUT = 60.0  # seconds to await a matching JSON-RPC response line


class StdioChild:
    """Owns ONE stdio MCP subprocess and serialises JSON-RPC round-trips to it.

    A single stdin/stdout pipe cannot service two concurrent readers, so every
    request/response round-trip is guarded by a lock.  ``spawn_count`` is the
    load-bearing proof value: it MUST stay ``1`` no matter how many HTTP clients
    connect - that is the whole point (one shared child, not one-per-client).
    """

    def __init__(self, cmd: list[str], env: dict[str, str] | None = None) -> None:
        if not cmd:
            raise ValueError("StdioChild requires a non-empty command")
        self._cmd = list(cmd)
        self._env = {**os.environ, **(env or {})}
        self._proc: subprocess.Popen[str] | None = None
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self.spawn_count = 0

    def _pump(self, proc: subprocess.Popen[str], sink: queue.Queue[str | None]) -> None:
        """Reader thread: drain the child's stdout into ``sink`` (None on EOF).

        A dedicated reader means a silent/hung child never blocks the request
        thread forever - the request loop reads from the queue WITH a timeout,
        so a wedged backend surfaces as a clean ``TimeoutError`` instead of a
        stuck lock (the exact failure mode ``../social-hub/hub.py`` avoids).
        """
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                sink.put(line)
        finally:
            sink.put(None)

    def _ensure(self) -> subprocess.Popen[str]:
        if self._proc is None or self._proc.poll() is not None:
            # UTF-8 pipes: Windows defaults to cp1252 and would mangle JSON.
            self._proc = subprocess.Popen(
                self._cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=self._env,
            )
            self.spawn_count += 1
            self._queue = queue.Queue()
            threading.Thread(
                target=self._pump, args=(self._proc, self._queue), daemon=True
            ).start()
        return self._proc

    @property
    def pid(self) -> int | None:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc.pid
        return None

    def start(self) -> None:
        """Eagerly spawn the child (so /healthz reports a pid before traffic)."""
        with self._lock:
            self._ensure()

    def request(
        self, msg: dict[str, Any], timeout: float = REQUEST_TIMEOUT
    ) -> dict[str, Any] | None:
        """Forward one JSON-RPC message; return its response, or None if it was a notification.

        A JSON-RPC *notification* has no ``id`` member and receives no reply, so
        we write it and return immediately.  A *request* carries an ``id``; we
        read queued child-stdout lines (bounded by ``timeout``) until one parses
        to a matching ``id`` (unrelated / non-JSON lines are skipped defensively,
        though the hubs emit only JSON-RPC).
        """
        want_id = msg.get("id")
        line = json.dumps(msg) + "\n"
        with self._lock:
            proc = self._ensure()
            sink = self._queue
            assert proc.stdin is not None
            proc.stdin.write(line)
            proc.stdin.flush()
            if want_id is None:
                return None
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"no response for id={want_id!r} within {timeout}s"
                    )
                try:
                    out = sink.get(timeout=remaining)
                except queue.Empty:
                    raise TimeoutError(
                        f"no response for id={want_id!r} within {timeout}s"
                    ) from None
                if out is None:
                    raise RuntimeError("stdio child closed its stdout (EOF)")
                out = out.strip()
                if not out:
                    continue
                try:
                    resp = json.loads(out)
                except json.JSONDecodeError:
                    continue
                if isinstance(resp, dict) and resp.get("id") == want_id:
                    return resp

    def terminate(self) -> None:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._proc.kill()


def _make_handler(
    child: StdioChild,
    mcp_path: str,
    health_path: str,
    stats: dict[str, int],
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send_json(
            self, code: int, obj: Any, extra: dict[str, str] | None = None
        ) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _send_empty(self, code: int) -> None:
            self.send_response(code)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802 (stdlib name)
            if self.path.split("?", 1)[0] == health_path:
                self._send_json(
                    200,
                    {
                        "status": "ok",
                        "host_version": HOST_VERSION,
                        "host_pid": os.getpid(),
                        "child_pid": child.pid,
                        "child_spawn_count": child.spawn_count,
                        "requests_served": stats["served"],
                    },
                )
            else:
                self._send_json(404, {"error": "not found", "path": self.path})

        def do_POST(self) -> None:  # noqa: N802 (stdlib name)
            if self.path.split("?", 1)[0] != mcp_path:
                self._send_json(404, {"error": "not found", "path": self.path})
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b""
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                self._send_json(
                    400,
                    {
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": "parse error"},
                        "id": None,
                    },
                )
                return
            stats["served"] += 1
            try:
                if isinstance(msg, list):
                    self._handle_batch(msg)
                else:
                    self._handle_single(msg)
            except Exception as exc:  # noqa: BLE001 - report as JSON-RPC error, never 500-crash
                rid = msg.get("id") if isinstance(msg, dict) else None
                self._send_json(
                    500,
                    {
                        "jsonrpc": "2.0",
                        "error": {"code": -32000, "message": str(exc)},
                        "id": rid,
                    },
                )

        def _handle_single(self, msg: dict[str, Any]) -> None:
            resp = child.request(msg)
            if resp is None:
                self._send_empty(202)
                return
            extra = (
                {"Mcp-Session-Id": uuid.uuid4().hex}
                if msg.get("method") == "initialize"
                else None
            )
            self._send_json(200, resp, extra)

        def _handle_batch(self, batch: list[dict[str, Any]]) -> None:
            responses = [r for r in (child.request(m) for m in batch) if r is not None]
            if responses:
                self._send_json(200, responses)
            else:
                self._send_empty(202)

        def log_message(self, *args: Any) -> None:  # silence default stderr access log
            pass

    return Handler


def build_server(
    cmd: list[str],
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    mcp_path: str = DEFAULT_MCP_PATH,
    health_path: str = DEFAULT_HEALTH_PATH,
    env: dict[str, str] | None = None,
    eager: bool = False,
) -> tuple[ThreadingHTTPServer, StdioChild]:
    """Construct (but do not serve) a shared host wrapping ``cmd``.

    Returned so tests can drive it in a background thread and shut it down.
    """
    child = StdioChild(cmd, env)
    if eager:
        child.start()
    stats = {"served": 0}
    handler = _make_handler(child, mcp_path, health_path, stats)
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd, child


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Share one stdio MCP server over HTTP."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--path", default=DEFAULT_MCP_PATH, help="Streamable-HTTP POST path"
    )
    parser.add_argument("--health-path", default=DEFAULT_HEALTH_PATH)
    parser.add_argument(
        "--eager", action="store_true", help="spawn the child at startup"
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="the stdio MCP command (put it after --)",
    )
    return parser.parse_args(argv)


def _child_cmd(raw: list[str]) -> list[str]:
    """Drop a leading ``--`` separator argparse's REMAINDER leaves in place."""
    cmd = list(raw)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    return cmd


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    cmd = _child_cmd(args.command)
    if not cmd:
        print("error: no child command given (put it after `--`)", file=sys.stderr)
        return 2
    httpd, child = build_server(
        cmd,
        host=args.host,
        port=args.port,
        mcp_path=args.path,
        health_path=args.health_path,
        eager=args.eager,
    )
    atexit.register(child.terminate)
    url = f"http://{args.host}:{args.port}{args.path}"
    print(
        f"mcp-http-host {HOST_VERSION} serving {cmd} at {url} (health {args.health_path})",
        file=sys.stderr,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        child.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
