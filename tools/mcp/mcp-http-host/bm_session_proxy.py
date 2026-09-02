#!/usr/bin/env python3
"""bm-session-proxy - session-healing reverse proxy in front of the Basic Memory daemon.

The shared Basic Memory daemon dies under RAM pressure near-daily and is restarted
by its watchdog (``.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md``). Two windows
follow every restart, and the TypeScript SDK transport that Cursor and Claude Code
use survives neither (modelcontextprotocol/typescript-sdk#1708):

* **stale-session window** - the port is healthy again but every session id from
  before the restart answers ``HTTP 404`` / JSON-RPC ``-32600 Session not found``;
  the client is stuck until it is destroyed and recreated;
* **dead-port window** - 3-7 minutes of ``ECONNREFUSED`` (watchdog cycle plus a
  2.5-4 min warm-up); the client marks the server red and stays red.

This process owns the client-facing port (``:8765``, the URL every client already
holds) and forwards MCP Streamable HTTP to the daemon on an internal port. Per
client session it keeps ONE upstream session and heals it transparently:

* the client sees a proxy-issued ``Mcp-Session-Id`` that stays valid for as long as
  the client keeps using it; each maps to an upstream session id;
* on ``404`` / ``-32600 Session not found`` the proxy re-initializes the upstream
  session with the client's own ``initialize`` params, sends
  ``notifications/initialized``, and replays the failed request exactly once;
* JSON and SSE bodies are relayed as they arrive (``read1`` chunks), never
  buffered whole; GET server->client streams stay open across upstream restarts
  (the upstream leg is re-opened quietly); ``DELETE`` ends both legs;
* while the daemon's port refuses (or hangs), clients get a clean ``503`` with
  ``Retry-After`` and their session header, never a connection refused;
* a client session id the proxy does not know (the proxy itself restarted) is
  adopted: a fresh upstream session is opened for it, so a proxy restart is
  invisible too (``--no-adopt`` answers the SDK's 404 instead);
* ``/healthz`` reports the upstream state (passive; ``?probe=1`` performs a bare
  upstream GET, which opens no session); every restart-related event is appended
  to a JSONL file.

stdlib only (``http.server`` + ``http.client`` + ``threading``): the box is
RAM-starved and runs the bundled ``C:\\Python314\\python.exe``. Binds loopback only.
The daemon itself is never started, stopped or probed with a session by this
process; the watchdog and ``BasicMemory-HTTP-MCP`` own that.

Usage::

    python bm_session_proxy.py --port 8765 --upstream http://127.0.0.1:8766/mcp \
        --restart-log C:\\Users\\Prekzursil\\.agents\\logs\\bm-session-proxy.jsonl
"""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import os
import re
import sys
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PROXY_VERSION = "0.1.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_UPSTREAM_URL = "http://127.0.0.1:8766/mcp"
DEFAULT_MCP_PATH = "/mcp"
DEFAULT_HEALTH_PATH = "/healthz"
DEFAULT_RETRY_AFTER = 30
# tools/call may legitimately take a long time under load; initialize / ping are
# cheap, so they get the watchdog's probe window (a slow answer there IS the
# "bound but unresponsive" signal the watchdog measures).
DEFAULT_UPSTREAM_TIMEOUT = 120.0
DEFAULT_HANDSHAKE_TIMEOUT = 30.0
# Seconds between SSE keepalive comments on a client GET stream whose upstream
# leg is silent or absent; also the upstream stream's read timeout.
DEFAULT_KEEPALIVE = 15.0
DEFAULT_RECONNECT_DELAY = 0.5
MAX_RECONNECT_DELAY = 5.0
DEFAULT_MAX_SESSIONS = 128
# What Basic Memory 3.3.x negotiates (measured 2026-08-27); used only when an
# unknown client session is adopted without an MCP-Protocol-Version header.
DEFAULT_PROTOCOL_VERSION = "2025-03-26"
DEFAULT_RESTART_LOG_NAME = "bm-session-proxy.jsonl"
PROXY_CLIENT_INFO = {"name": "bm-session-proxy", "version": PROXY_VERSION}
SESSION_HEADER = "Mcp-Session-Id"
PROTOCOL_HEADER = "MCP-Protocol-Version"
# A "Session not found" body is ~90 bytes. JSON bodies up to this size are read
# and inspected for the in-band -32600 form; anything larger streams through.
SMALL_BODY = 512
CHUNK = 65536
MAX_REQUEST_BODY = 32 * 1024 * 1024
CLIENT_IDLE_TIMEOUT = 300.0
HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
        "expect",  # http.client sends bodies eagerly; a forwarded 100-continue misleads
        SESSION_HEADER.lower(),
    }
)
_SESSION_ID_RE = re.compile(r"^[\x21-\x7e]{1,256}$")


def session_not_found_body() -> bytes:
    """The MCP Python SDK's exact body for a stale session id."""
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Session not found"},
        }
    ).encode("utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- errors ------------------------------------------------------------------------


class UpstreamUnavailable(OSError):
    """The daemon could not be reached or did not answer (refused, reset, hung)."""

    def __init__(self, message: str, *, timed_out: bool = False) -> None:
        super().__init__(message)
        self.timed_out = timed_out


class UpstreamRejected(RuntimeError):
    """The daemon answered the proxy's own re-initialize with something unusable."""

    def __init__(self, status: int, body: bytes) -> None:
        text = body.decode("utf-8", errors="replace")[:300]
        super().__init__(f"HTTP {status} {text}".strip())
        self.status = status


class ClientGone(Exception):
    """The client closed its connection while a response was being written."""


# --- wire parsing ------------------------------------------------------------------


def parse_sse_messages(text: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    data_lines: list[str] = []

    def flush() -> None:
        if data_lines:
            try:
                value: Any = json.loads("\n".join(data_lines))
            except ValueError:
                value = None
            if isinstance(value, dict):
                messages.append(value)
        data_lines.clear()

    for line in text.splitlines():
        if not line.strip():
            flush()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    flush()
    return messages


def parse_rpc_messages(raw: bytes, content_type: str | None) -> list[dict[str, Any]]:
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return []
    ctype = (content_type or "").lower()
    if "text/event-stream" in ctype or text.startswith("event:") or "\ndata:" in text:
        return parse_sse_messages(text)
    try:
        value: Any = json.loads(text)
    except ValueError:
        return []
    return [value] if isinstance(value, dict) else []


def is_response(message: dict[str, Any]) -> bool:
    return "method" not in message and ("result" in message or "error" in message)


def is_session_not_found(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    err = payload.get("error")
    if not isinstance(err, dict):
        return False
    return (
        err.get("code") == -32600
        and "session not found" in str(err.get("message") or "").lower()
    )


def _last_response(messages: list[dict[str, Any]]) -> dict[str, Any]:
    responses = [m for m in messages if is_response(m)]
    return responses[-1] if responses else {}


# --- restart log -------------------------------------------------------------------


class RestartLog:
    """Append-only JSONL: one object per restart-related event, best-effort."""

    def __init__(self, path: Path | str | None) -> None:
        self.path = Path(path) if path else None
        self._lock = threading.Lock()

    def append(self, event: str, **fields: Any) -> None:
        if self.path is None:
            return
        entry: dict[str, Any] = {"ts": _now(), "pid": os.getpid(), "event": event}
        entry.update(fields)
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(line)
            except OSError:
                return  # a full or read-only disk must never take the proxy down


# --- upstream state ----------------------------------------------------------------


class UpstreamState:
    """What the proxy currently believes about the daemon, for /healthz and the log."""

    def __init__(self, url: str, log: RestartLog) -> None:
        self.url = url
        self.log = log
        self.state = "unknown"
        self.last_ok_at: str | None = None
        self.last_failure_at: str | None = None
        self.last_error: str | None = None
        self.consecutive_failures = 0
        self.downtime_windows = 0
        self.sessions_lost = 0
        self.reinitialized = 0
        self.heal_rejected = 0
        self._lock = threading.Lock()

    def record_ok(self) -> None:
        with self._lock:
            was = self.state
            self.state = "up"
            self.last_ok_at = _now()
            self.consecutive_failures = 0
        if was == "down":
            self.log.append("upstream_recovered", upstream=self.url)

    def record_failure(self, exc: BaseException) -> None:
        with self._lock:
            was = self.state
            self.state = "down"
            self.last_failure_at = _now()
            self.last_error = str(exc)
            self.consecutive_failures += 1
            if was != "down":
                self.downtime_windows += 1
        if was != "down":
            self.log.append("upstream_down", upstream=self.url, detail=str(exc))

    def note_session_lost(
        self, client_session: str, upstream_session: str | None, detail: str
    ) -> None:
        with self._lock:
            self.sessions_lost += 1
        self.log.append(
            "session_lost",
            client_session=client_session,
            upstream_session=upstream_session,
            detail=detail,
        )

    def note_reinitialized(
        self,
        client_session: str,
        old: str | None,
        new: str,
        server_generation: Any,
        adopted: bool,
    ) -> None:
        with self._lock:
            self.reinitialized += 1
        self.log.append(
            "session_reinitialized",
            client_session=client_session,
            upstream_session_old=old,
            upstream_session_new=new,
            server_generation=server_generation,
            adopted=adopted,
        )

    def note_heal_rejected(self, client_session: str, detail: str) -> None:
        with self._lock:
            self.heal_rejected += 1
        self.log.append("heal_rejected", client_session=client_session, detail=detail)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "url": self.url,
                "state": self.state,
                "last_ok_at": self.last_ok_at,
                "last_failure_at": self.last_failure_at,
                "last_error": self.last_error,
                "consecutive_failures": self.consecutive_failures,
                "downtime_windows": self.downtime_windows,
                "sessions_lost": self.sessions_lost,
                "reinitialized": self.reinitialized,
                "heal_rejected": self.heal_rejected,
            }


# --- client sessions ---------------------------------------------------------------


class ClientSession:
    """One client-visible session and the upstream session currently behind it."""

    __slots__ = (
        "client_id",
        "upstream_id",
        "previous_upstream_id",
        "init_params",
        "generation",
        "adopted",
        "lock",
    )

    def __init__(
        self,
        client_id: str,
        init_params: dict[str, Any],
        upstream_id: str | None,
        *,
        adopted: bool,
    ) -> None:
        self.client_id = client_id
        self.upstream_id = upstream_id
        self.previous_upstream_id: str | None = None
        self.init_params = init_params
        self.generation = 0
        self.adopted = adopted
        # Held for the whole re-initialize round-trip so concurrent requests on the
        # same client session heal it once, not once each.
        self.lock = threading.Lock()

    def snapshot(self) -> tuple[int, str | None]:
        with self.lock:
            return self.generation, self.upstream_id

    def mark_lost(self, generation: int, *, known_stale: bool) -> bool:
        """Forget the upstream session unless another thread already healed it."""
        with self.lock:
            if self.generation != generation or self.upstream_id is None:
                return False
            self.previous_upstream_id = self.upstream_id if known_stale else None
            self.upstream_id = None
            return True


class SessionTable:
    """Client id -> ClientSession, least-recently-used eviction at ``max_sessions``."""

    def __init__(self, max_sessions: int) -> None:
        self.max_sessions = max(1, max_sessions)
        self._sessions: OrderedDict[str, ClientSession] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, client_id: str) -> ClientSession | None:
        with self._lock:
            session = self._sessions.get(client_id)
            if session is not None:
                self._sessions.move_to_end(client_id)
            return session

    def create(
        self,
        client_id: str,
        init_params: dict[str, Any],
        upstream_id: str | None,
        *,
        adopted: bool,
    ) -> tuple[ClientSession, list[ClientSession]]:
        """Return the (existing or new) session plus the sessions evicted for it."""
        with self._lock:
            existing = self._sessions.get(client_id)
            if existing is not None:
                self._sessions.move_to_end(client_id)
                return existing, []
            session = ClientSession(
                client_id, init_params, upstream_id, adopted=adopted
            )
            self._sessions[client_id] = session
            evicted: list[ClientSession] = []
            while len(self._sessions) > self.max_sessions:
                _, old = self._sessions.popitem(last=False)
                evicted.append(old)
            return session, evicted

    def remove(self, client_id: str) -> ClientSession | None:
        with self._lock:
            return self._sessions.pop(client_id, None)

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def stats(self) -> dict[str, int]:
        with self._lock:
            sessions = list(self._sessions.values())
        return {
            "client": len(sessions),
            "with_upstream": sum(1 for s in sessions if s.upstream_id is not None),
            "adopted": sum(1 for s in sessions if s.adopted),
            "max": self.max_sessions,
        }


# --- the upstream leg --------------------------------------------------------------


class Upstream:
    """Plain ``http.client`` calls to the daemon; one connection per exchange."""

    def __init__(self, url: str, timeout: float, handshake_timeout: float) -> None:
        parts = urlsplit(url)
        if parts.scheme != "http" or not parts.hostname:
            raise ValueError(f"upstream must be a plain http:// URL, got {url!r}")
        self.url = url
        self.host = parts.hostname
        self.port = parts.port or 80
        self.path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        self.timeout = timeout
        self.handshake_timeout = handshake_timeout
        self._next_id = 0
        self._lock = threading.Lock()

    def _alloc_id(self) -> str:
        with self._lock:
            self._next_id += 1
            return f"bm-session-proxy-{self._next_id}"

    def open(
        self,
        method: str,
        headers: dict[str, str],
        body: bytes | None = None,
        timeout: float | None = None,
    ) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
        """Send one request and return the connection plus its unread response."""
        wait = self.timeout if timeout is None else timeout
        conn = http.client.HTTPConnection(self.host, self.port, timeout=wait)
        try:
            conn.request(method, self.path, body=body, headers=headers)
            resp = conn.getresponse()
        except TimeoutError as exc:
            conn.close()
            raise UpstreamUnavailable(
                f"timed out after {wait:g}s waiting for {self.url}", timed_out=True
            ) from exc
        except (OSError, http.client.HTTPException) as exc:
            conn.close()
            raise UpstreamUnavailable(f"{exc}") from exc
        return conn, resp

    @staticmethod
    def _rpc_headers(
        session_id: str | None, protocol_version: str | None
    ) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if session_id:
            headers[SESSION_HEADER] = session_id
        if protocol_version:
            headers[PROTOCOL_HEADER] = protocol_version
        return headers

    def initialize(self, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Open a fresh upstream session: (session id, initialize result message)."""
        message = {
            "jsonrpc": "2.0",
            "id": self._alloc_id(),
            "method": "initialize",
            "params": params,
        }
        conn, resp = self.open(
            "POST",
            self._rpc_headers(None, None),
            json.dumps(message).encode("utf-8"),
            timeout=self.handshake_timeout,
        )
        with closing(conn):
            body = resp.read()  # an initialize result is small: drain it whole
            sid = resp.getheader(SESSION_HEADER)
            if resp.status != 200 or not sid:
                raise UpstreamRejected(resp.status, body)
            result = _last_response(
                parse_rpc_messages(body, resp.getheader("Content-Type"))
            )
            if "error" in result or "result" not in result:
                raise UpstreamRejected(resp.status, body)
        return sid, result

    def notify_initialized(self, session_id: str, protocol_version: str | None) -> None:
        message = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        conn, resp = self.open(
            "POST",
            self._rpc_headers(session_id, protocol_version),
            json.dumps(message).encode("utf-8"),
            timeout=self.handshake_timeout,
        )
        with closing(conn):
            resp.read()

    def delete(self, session_id: str) -> None:
        """Best-effort release of an upstream session the proxy no longer needs."""
        try:
            conn, resp = self.open(
                "DELETE",
                {SESSION_HEADER: session_id},
                timeout=self.handshake_timeout,
            )
        except UpstreamUnavailable:
            return
        with closing(conn):
            resp.read()

    def probe(self) -> int:
        """A bare GET (no Accept): any HTTP status means the daemon is serving.

        This is the on-box watchdog's own probe shape (406 while healthy) and it
        opens no session.
        """
        conn, resp = self.open("GET", {}, timeout=self.handshake_timeout)
        with closing(conn):
            resp.read()
            return resp.status


# --- the proxy core ----------------------------------------------------------------


class Request:
    __slots__ = ("verb", "headers", "body", "message", "client_sid", "query")

    def __init__(
        self,
        verb: str,
        headers: dict[str, str],
        body: bytes,
        client_sid: str | None,
        query: str,
    ) -> None:
        self.verb = verb
        self.headers = headers
        self.body = body
        self.client_sid = client_sid
        self.query = query
        parsed: Any = None
        if body:
            try:
                parsed = json.loads(body)
            except ValueError:
                parsed = None
        self.message: dict[str, Any] | None = (
            parsed if isinstance(parsed, dict) else None
        )

    @property
    def rpc_method(self) -> str | None:
        method = self.message.get("method") if self.message else None
        return method if isinstance(method, str) else None

    @property
    def rpc_id(self) -> Any:
        return self.message.get("id") if self.message else None

    def header(self, name: str) -> str | None:
        wanted = name.lower()
        for key, value in self.headers.items():
            if key.lower() == wanted:
                return value
        return None


class Writer:
    """Response writer protocol the core drives; the HTTP handler implements it."""

    def start(
        self, status: int, headers: list[tuple[str, str]], *, chunked: bool
    ) -> None:
        raise NotImplementedError

    def write(self, data: bytes) -> None:
        raise NotImplementedError

    def finish(self) -> None:
        raise NotImplementedError


class SessionProxy:
    def __init__(
        self,
        upstream_url: str = DEFAULT_UPSTREAM_URL,
        *,
        restart_log: Path | str | None = None,
        retry_after: int = DEFAULT_RETRY_AFTER,
        upstream_timeout: float = DEFAULT_UPSTREAM_TIMEOUT,
        handshake_timeout: float = DEFAULT_HANDSHAKE_TIMEOUT,
        keepalive: float = DEFAULT_KEEPALIVE,
        reconnect_delay: float = DEFAULT_RECONNECT_DELAY,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        adopt_unknown_sessions: bool = True,
    ) -> None:
        self.upstream = Upstream(upstream_url, upstream_timeout, handshake_timeout)
        self.log = RestartLog(restart_log)
        self.state = UpstreamState(upstream_url, self.log)
        self.sessions = SessionTable(max_sessions)
        self.retry_after = max(0, int(retry_after))
        self.keepalive = max(0.05, keepalive)
        self.reconnect_delay = max(0.01, reconnect_delay)
        self.adopt_unknown_sessions = adopt_unknown_sessions
        self.stopping = threading.Event()
        self.started_at = _now()
        self.host = DEFAULT_HOST
        self.port: int | None = None
        self.mcp_path = DEFAULT_MCP_PATH
        self.health_path = DEFAULT_HEALTH_PATH
        self._metrics = {"proxied": 0, "unavailable_503": 0, "streams_open": 0}
        self._metrics_lock = threading.Lock()

    def stop(self) -> None:
        self.stopping.set()

    def _count(self, key: str, delta: int = 1) -> None:
        with self._metrics_lock:
            self._metrics[key] += delta

    # -- header plumbing -----------------------------------------------------

    @staticmethod
    def _forward_headers(
        client_headers: dict[str, str], upstream_sid: str | None
    ) -> dict[str, str]:
        out = {
            key: value
            for key, value in client_headers.items()
            if key.lower() not in HOP_BY_HOP
        }
        if upstream_sid:
            out[SESSION_HEADER] = upstream_sid
        return out

    @staticmethod
    def _relay_headers(
        resp: http.client.HTTPResponse, client_sid: str | None
    ) -> list[tuple[str, str]]:
        headers = [
            (key, value)
            for key, value in resp.getheaders()
            if key.lower() not in HOP_BY_HOP
        ]
        if client_sid:
            headers.append((SESSION_HEADER, client_sid))
        return headers

    # -- local answers -------------------------------------------------------

    @staticmethod
    def _send_bytes(
        writer: Writer,
        status: int,
        body: bytes,
        headers: list[tuple[str, str]],
    ) -> None:
        writer.start(
            status, [*headers, ("Content-Length", str(len(body)))], chunked=False
        )
        if body:
            writer.write(body)
        writer.finish()

    def _send_json_error(
        self,
        writer: Writer,
        status: int,
        rid: Any,
        code: int,
        message: str,
        client_sid: str | None,
        extra: list[tuple[str, str]] | None = None,
    ) -> None:
        body = json.dumps(
            {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}
        ).encode("utf-8")
        headers = [("Content-Type", "application/json"), *(extra or [])]
        if client_sid:
            headers.append((SESSION_HEADER, client_sid))
        self._send_bytes(writer, status, body, headers)

    def _send_503(
        self, writer: Writer, rid: Any, exc: BaseException, client_sid: str | None
    ) -> None:
        self._count("unavailable_503")
        text = (
            f"Basic Memory upstream unavailable at {self.upstream.url} ({exc}). The "
            "daemon restarts itself (BasicMemory-Watchdog: 3-min cycle, then a "
            "2.5-4 min warm-up on this box); this proxy keeps your session and "
            "heals it on the next request. Retry shortly; do not start a second daemon."
        )
        self._send_json_error(
            writer,
            503,
            rid,
            -32000,
            text,
            client_sid,
            extra=[("Retry-After", str(self.retry_after))],
        )

    def _send_502(
        self, writer: Writer, rid: Any, exc: UpstreamRejected, client_sid: str | None
    ) -> None:
        self._send_json_error(
            writer,
            502,
            rid,
            -32000,
            f"Basic Memory rejected the proxy's re-initialize: {exc}",
            client_sid,
        )

    def _send_session_not_found(self, writer: Writer) -> None:
        self._send_bytes(
            writer,
            404,
            session_not_found_body(),
            [("Content-Type", "application/json")],
        )

    def _send_empty(self, writer: Writer, status: int, client_sid: str | None) -> None:
        headers = [(SESSION_HEADER, client_sid)] if client_sid else []
        self._send_bytes(writer, status, b"", headers)

    # -- relaying ------------------------------------------------------------

    def _relay(
        self,
        resp: http.client.HTTPResponse,
        writer: Writer,
        client_sid: str | None,
        prebody: bytes | None = None,
    ) -> None:
        """Stream an upstream response to the client as its bytes arrive."""
        headers = self._relay_headers(resp, client_sid)
        if prebody is not None:
            self._send_bytes(writer, resp.status, prebody, headers)
            return
        length = resp.getheader("Content-Length")
        bodiless = resp.status in (204, 304)
        chunked = length is None and not bodiless
        if not chunked and not bodiless:
            headers.append(("Content-Length", str(length)))
        writer.start(resp.status, headers, chunked=chunked)
        if not bodiless:
            while not self.stopping.is_set():
                try:
                    data = resp.read1(CHUNK)
                except (OSError, http.client.HTTPException):
                    break  # upstream cut the body short: end what we can
                if not data:
                    break
                writer.write(data)
        writer.finish()

    def _detect_session_loss(
        self, resp: http.client.HTTPResponse
    ) -> tuple[bool, bytes | None, str]:
        """(lost, body already read, detail) - reading only small JSON bodies."""
        if resp.status == 404:
            body = resp.read()
            messages = parse_rpc_messages(body, resp.getheader("Content-Type"))
            detail = "HTTP 404"
            for message in messages:
                err = message.get("error")
                if isinstance(err, dict) and err.get("message"):
                    detail = str(err["message"])
            return True, body, detail
        length = resp.getheader("Content-Length")
        ctype = (resp.getheader("Content-Type") or "").lower()
        if (
            length is not None
            and length.isdigit()
            and int(length) <= SMALL_BODY
            and "application/json" in ctype
            and resp.getheader("Content-Encoding") is None
        ):
            body = resp.read()
            try:
                payload: Any = json.loads(body) if body else None
            except ValueError:
                payload = None
            if is_session_not_found(payload):
                return True, body, str(payload["error"]["message"])
            return False, body, ""
        return False, None, ""

    # -- session resolution --------------------------------------------------

    def _release(self, evicted: list[ClientSession]) -> None:
        for session in evicted:
            _, usid = session.snapshot()
            if usid:
                self.upstream.delete(usid)

    def _resolve(self, req: Request) -> ClientSession | None:
        client_sid = req.client_sid
        assert client_sid is not None
        session = self.sessions.get(client_sid)
        if session is not None:
            return session
        if not self.adopt_unknown_sessions:
            return None
        # The proxy restarted (or the id predates it): adopt the id the client
        # already holds and open an upstream session for it lazily, negotiating the
        # version the client announces on its requests.
        params = {
            "protocolVersion": req.header(PROTOCOL_HEADER) or DEFAULT_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": dict(PROXY_CLIENT_INFO),
        }
        session, evicted = self.sessions.create(client_sid, params, None, adopted=True)
        self._release(evicted)
        return session

    def _heal(self, session: ClientSession, expected_generation: int) -> None:
        """Re-initialize the upstream leg with the client's own initialize params.

        Raises ``UpstreamUnavailable`` / ``UpstreamRejected``; a no-op when another
        thread healed this session since ``expected_generation`` was read.
        """
        with session.lock:
            if session.generation != expected_generation or session.upstream_id:
                return
            old = session.previous_upstream_id
            sid, result = self.upstream.initialize(session.init_params)
            self.state.record_ok()
            payload = result.get("result")
            negotiated = (
                payload.get("protocolVersion") if isinstance(payload, dict) else None
            )
            info = payload.get("serverInfo") if isinstance(payload, dict) else None
            generation = info.get("generation") if isinstance(info, dict) else None
            try:
                self.upstream.notify_initialized(
                    sid, negotiated if isinstance(negotiated, str) else None
                )
            except UpstreamUnavailable:
                pass  # the session exists; the daemon dying again shows on the replay
            session.upstream_id = sid
            session.previous_upstream_id = None
            session.generation += 1
            self.state.note_reinitialized(
                session.client_id, old, sid, generation, session.adopted
            )

    # -- verbs ---------------------------------------------------------------

    def handle_post(self, req: Request, writer: Writer) -> None:
        self._count("proxied")
        if req.rpc_method == "initialize":
            self._proxy_initialize(req, writer)
            return
        if not req.client_sid:
            self._passthrough(req, writer)  # the daemon answers 400 Missing session ID
            return
        session = self._resolve(req)
        if session is None:
            self._send_session_not_found(writer)
            return
        self._proxy_session_post(req, writer, session)

    def _proxy_initialize(self, req: Request, writer: Writer) -> None:
        headers = self._forward_headers(req.headers, None)  # a fresh upstream session
        try:
            conn, resp = self.upstream.open(
                "POST", headers, req.body, timeout=self.upstream.handshake_timeout
            )
        except UpstreamUnavailable as exc:
            self.state.record_failure(exc)
            self._send_503(writer, req.rpc_id, exc, None)
            return
        with closing(conn):
            self.state.record_ok()
            usid = resp.getheader(SESSION_HEADER)
            client_sid = None
            if resp.status == 200 and usid:
                client_sid = uuid.uuid4().hex
                params = req.message.get("params") if req.message else None
                _, evicted = self.sessions.create(
                    client_sid,
                    params if isinstance(params, dict) else {},
                    usid,
                    adopted=False,
                )
                self._release(evicted)
            self._relay(resp, writer, client_sid)

    def _proxy_session_post(
        self, req: Request, writer: Writer, session: ClientSession
    ) -> None:
        rid = req.rpc_id
        method = req.rpc_method
        timeout = (
            self.upstream.handshake_timeout
            if method == "ping"
            else self.upstream.timeout
        )
        losses = 0
        heals = 0
        while losses < 2 and heals < 3 and not self.stopping.is_set():
            generation, usid = session.snapshot()
            if usid is None:
                heals += 1
                try:
                    self._heal(session, generation)
                except UpstreamUnavailable as exc:
                    self.state.record_failure(exc)
                    self._send_503(writer, rid, exc, session.client_id)
                    return
                except UpstreamRejected as exc:
                    self.state.note_heal_rejected(session.client_id, str(exc))
                    self._send_502(writer, rid, exc, session.client_id)
                    return
                if method == "notifications/initialized":
                    # The heal already announced initialized on the new session.
                    self._send_empty(writer, 202, session.client_id)
                    return
                continue
            headers = self._forward_headers(req.headers, usid)
            try:
                conn, resp = self.upstream.open("POST", headers, req.body, timeout)
            except UpstreamUnavailable as exc:
                self.state.record_failure(exc)
                session.mark_lost(generation, known_stale=False)
                self._send_503(writer, rid, exc, session.client_id)
                return
            with closing(conn):
                self.state.record_ok()
                lost, prebody, detail = self._detect_session_loss(resp)
                if not lost:
                    self._relay(resp, writer, session.client_id, prebody)
                    return
                if session.mark_lost(generation, known_stale=True):
                    self.state.note_session_lost(session.client_id, usid, detail)
            losses += 1
        self._send_503(
            writer,
            rid,
            UpstreamUnavailable("session lost twice in a row: the daemon is flapping"),
            session.client_id,
        )

    def _passthrough(self, req: Request, writer: Writer) -> None:
        """Forward a request that carries no proxy session (probes, bad requests)."""
        headers = self._forward_headers(req.headers, None)
        body = req.body if req.verb == "POST" else None
        try:
            conn, resp = self.upstream.open(
                req.verb, headers, body, timeout=self.upstream.handshake_timeout
            )
        except UpstreamUnavailable as exc:
            self.state.record_failure(exc)
            self._send_503(writer, req.rpc_id, exc, None)
            return
        with closing(conn):
            self.state.record_ok()
            self._relay(resp, writer, None)

    def handle_get(self, req: Request, writer: Writer) -> None:
        self._count("proxied")
        accept = (req.header("Accept") or "").lower()
        if not req.client_sid or "text/event-stream" not in accept:
            self._passthrough(req, writer)  # the on-box health probe shape (406)
            return
        session = self._resolve(req)
        if session is None:
            self._send_session_not_found(writer)
            return
        self._count("streams_open")
        try:
            self._stream(req, writer, session)
        finally:
            self._count("streams_open", -1)

    def _start_client_stream(self, writer: Writer, client_sid: str) -> None:
        writer.start(
            200,
            [
                ("Content-Type", "text/event-stream"),
                ("Cache-Control", "no-cache"),
                (SESSION_HEADER, client_sid),
            ],
            chunked=True,
        )
        writer.write(b": bm-session-proxy stream open\n\n")

    def _pause(self, writer: Writer, failures: int, started: bool) -> None:
        """Back off before the next upstream attempt, keeping the client warm."""
        pause = min(
            self.reconnect_delay * (2 ** max(failures - 1, 0)), MAX_RECONNECT_DELAY
        )
        deadline = time.monotonic() + pause
        last_write = time.monotonic()
        while not self.stopping.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(remaining, self.keepalive, 0.25))
            if started and time.monotonic() - last_write >= self.keepalive:
                writer.write(
                    b": keepalive\n\n"
                )  # raises ClientGone when the client left
                last_write = time.monotonic()

    def _stream(self, req: Request, writer: Writer, session: ClientSession) -> None:
        """The decoupled GET stream: the client's leg stays open across restarts."""
        started = False
        failures = 0
        while not self.stopping.is_set():
            generation, usid = session.snapshot()
            if usid is None:
                try:
                    self._heal(session, generation)
                except UpstreamUnavailable as exc:
                    self.state.record_failure(exc)
                except UpstreamRejected as exc:
                    if failures == 0:  # once per streak, not once per retry
                        self.state.note_heal_rejected(session.client_id, str(exc))
                else:
                    continue
                if not started:
                    self._start_client_stream(writer, session.client_id)
                    started = True
                failures += 1
                self._pause(writer, failures, started)
                continue
            headers = self._forward_headers(req.headers, usid)
            try:
                conn, resp = self.upstream.open("GET", headers, timeout=self.keepalive)
            except UpstreamUnavailable as exc:
                self.state.record_failure(exc)
                session.mark_lost(generation, known_stale=False)
                if not started:
                    self._start_client_stream(writer, session.client_id)
                    started = True
                failures += 1
                self._pause(writer, failures, started)
                continue
            with closing(conn):
                self.state.record_ok()
                if resp.status == 404:
                    lost, _, detail = self._detect_session_loss(resp)
                    if lost and session.mark_lost(generation, known_stale=True):
                        self.state.note_session_lost(session.client_id, usid, detail)
                    if not started:
                        self._start_client_stream(writer, session.client_id)
                        started = True
                    continue  # heal on the next turn
                if resp.status != 200:
                    if not started:
                        self._relay(
                            resp, writer, session.client_id
                        )  # e.g. 405: no stream
                        return
                    resp.read()
                    failures += 1
                    self._pause(writer, failures, started)
                    continue
                if not started:
                    self._start_client_stream(writer, session.client_id)
                    started = True
                failures = 0
                while not self.stopping.is_set():
                    try:
                        data = resp.read1(CHUNK)
                    except TimeoutError:
                        writer.write(b": keepalive\n\n")
                        continue
                    except (OSError, http.client.HTTPException):
                        break
                    if not data:
                        break  # upstream closed the stream (restart): re-attach
                    writer.write(data)
            failures += 1
            self._pause(writer, failures, started)
        writer.finish()

    def handle_delete(self, req: Request, writer: Writer) -> None:
        self._count("proxied")
        if not req.client_sid:
            self._passthrough(req, writer)
            return
        session = self.sessions.remove(req.client_sid)
        if session is None:
            if self.adopt_unknown_sessions:
                self._send_empty(writer, 200, None)  # nothing to end: already gone
            else:
                self._send_session_not_found(writer)
            return
        _, usid = session.snapshot()
        if usid is None:
            self._send_empty(writer, 200, None)
            return
        headers = self._forward_headers(req.headers, usid)
        try:
            conn, resp = self.upstream.open(
                "DELETE", headers, timeout=self.upstream.handshake_timeout
            )
        except UpstreamUnavailable as exc:
            # The upstream session died with the daemon; the client's is gone too.
            self.state.record_failure(exc)
            self._send_empty(writer, 200, None)
            return
        with closing(conn):
            self.state.record_ok()
            self._relay(resp, writer, None)

    # -- health --------------------------------------------------------------

    def health(self, query: str) -> dict[str, Any]:
        if "probe=1" in query.split("&"):
            try:
                self.upstream.probe()
            except UpstreamUnavailable as exc:
                self.state.record_failure(exc)
            else:
                self.state.record_ok()
        upstream = self.state.snapshot()
        status = {"up": "ok", "down": "degraded"}.get(upstream["state"], "starting")
        with self._metrics_lock:
            requests = dict(self._metrics)
        return {
            "status": status,
            "proxy": {
                "version": PROXY_VERSION,
                "pid": os.getpid(),
                "host": self.host,
                "port": self.port,
                "mcp_path": self.mcp_path,
                "started_at": self.started_at,
                "restart_log": str(self.log.path) if self.log.path else None,
            },
            "upstream": upstream,
            "sessions": self.sessions.stats(),
            "requests": requests,
        }


# --- HTTP glue -----------------------------------------------------------------------


class _HandlerWriter(Writer):
    def __init__(self, handler: BaseHTTPRequestHandler) -> None:
        self.handler = handler
        self.chunked = False
        self.started = False
        self.raw = handler.request_version == "HTTP/1.0"

    def start(
        self, status: int, headers: list[tuple[str, str]], *, chunked: bool
    ) -> None:
        h = self.handler
        self.started = True
        try:
            h.send_response(status)
            for key, value in headers:
                h.send_header(key, value)
            self.chunked = chunked
            if chunked:
                if self.raw:
                    h.close_connection = True  # HTTP/1.0: body until close
                else:
                    h.send_header("Transfer-Encoding", "chunked")
            h.end_headers()
        except OSError as exc:
            raise ClientGone(str(exc)) from exc

    def write(self, data: bytes) -> None:
        if not data:
            return
        try:
            if self.chunked and not self.raw:
                self.handler.wfile.write(f"{len(data):x}\r\n".encode("ascii"))
                self.handler.wfile.write(data)
                self.handler.wfile.write(b"\r\n")
            else:
                self.handler.wfile.write(data)
            self.handler.wfile.flush()
        except OSError as exc:
            raise ClientGone(str(exc)) from exc

    def finish(self) -> None:
        try:
            if self.chunked and not self.raw:
                self.handler.wfile.write(b"0\r\n\r\n")
            self.handler.wfile.flush()
        except OSError as exc:
            raise ClientGone(str(exc)) from exc


def _make_handler(
    proxy: SessionProxy, mcp_path: str, health_path: str
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = f"bm-session-proxy/{PROXY_VERSION}"
        sys_version = ""
        timeout = CLIENT_IDLE_TIMEOUT

        def _split_path(self) -> tuple[str, str]:
            path, _, query = self.path.partition("?")
            return path, query

        def _json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _not_found(self) -> None:
            self._json(404, {"error": "not found", "path": self.path})

        def _read_request(self, verb: str, query: str) -> Request | None:
            if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
                self._json(411, {"error": "Content-Length required"})
                return None
            raw_length = self.headers.get("Content-Length") or "0"
            if not raw_length.isdigit():
                self._json(400, {"error": "bad Content-Length"})
                return None
            length = int(raw_length)
            if length > MAX_REQUEST_BODY:
                self._json(413, {"error": "request body too large"})
                return None
            body = self.rfile.read(length) if length else b""
            client_sid = self.headers.get(SESSION_HEADER)
            if client_sid is not None and not _SESSION_ID_RE.match(client_sid):
                self._json(
                    400,
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32600, "message": "Invalid Mcp-Session-Id"},
                    },
                )
                return None
            headers = {key: value for key, value in self.headers.items()}
            return Request(verb, headers, body, client_sid or None, query)

        def _dispatch(self, verb: str) -> None:
            path, query = self._split_path()
            if path != mcp_path:
                self._not_found()
                return
            req = self._read_request(verb, query)
            if req is None:
                return
            writer = _HandlerWriter(self)
            try:
                if verb == "POST":
                    proxy.handle_post(req, writer)
                elif verb == "GET":
                    proxy.handle_get(req, writer)
                else:
                    proxy.handle_delete(req, writer)
            except ClientGone:
                self.close_connection = True
            except Exception as exc:  # noqa: BLE001 - one bad exchange must not kill the thread loudly
                print(f"bm-session-proxy: {verb} failed: {exc!r}", file=sys.stderr)
                self.close_connection = True
                if not writer.started:
                    self._json(
                        500,
                        {
                            "jsonrpc": "2.0",
                            "id": req.rpc_id,
                            "error": {"code": -32000, "message": f"proxy error: {exc}"},
                        },
                    )

        def do_POST(self) -> None:  # noqa: N802 (stdlib name)
            self._dispatch("POST")

        def do_GET(self) -> None:  # noqa: N802 (stdlib name)
            path, query = self._split_path()
            if path == health_path:
                self._json(200, proxy.health(query))
                return
            self._dispatch("GET")

        def do_DELETE(self) -> None:  # noqa: N802 (stdlib name)
            self._dispatch("DELETE")

        def log_message(self, *args: Any) -> None:  # silence the access log
            pass

    return Handler


def build_server(
    upstream_url: str = DEFAULT_UPSTREAM_URL,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    mcp_path: str = DEFAULT_MCP_PATH,
    health_path: str = DEFAULT_HEALTH_PATH,
    **proxy_kwargs: Any,
) -> ThreadingHTTPServer:
    """Construct (but do not serve) the proxy; ``server.proxy`` is the core."""
    proxy = SessionProxy(upstream_url, **proxy_kwargs)
    handler = _make_handler(proxy, mcp_path, health_path)
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True
    proxy.host = host
    proxy.port = httpd.server_address[1]
    proxy.mcp_path = mcp_path
    proxy.health_path = health_path
    httpd.proxy = proxy  # type: ignore[attr-defined]
    proxy.log.append(
        "proxy_started",
        version=PROXY_VERSION,
        listen=f"http://{host}:{proxy.port}{mcp_path}",
        upstream=upstream_url,
    )
    return httpd


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Session-healing reverse proxy for the Basic Memory MCP daemon.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "The proxy owns the client-facing port; the daemon moves to the internal\n"
            "upstream port. Loopback only. See deploy/README.md in this lane."
        ),
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--upstream", default=DEFAULT_UPSTREAM_URL)
    parser.add_argument(
        "--path", default=DEFAULT_MCP_PATH, help="client-facing MCP path"
    )
    parser.add_argument("--health-path", default=DEFAULT_HEALTH_PATH)
    parser.add_argument(
        "--restart-log",
        default=str(Path(tempfile.gettempdir()) / DEFAULT_RESTART_LOG_NAME),
        help="JSONL file for restart events ('' disables)",
    )
    parser.add_argument("--retry-after", type=int, default=DEFAULT_RETRY_AFTER)
    parser.add_argument(
        "--upstream-timeout", type=float, default=DEFAULT_UPSTREAM_TIMEOUT
    )
    parser.add_argument(
        "--handshake-timeout", type=float, default=DEFAULT_HANDSHAKE_TIMEOUT
    )
    parser.add_argument("--keepalive", type=float, default=DEFAULT_KEEPALIVE)
    parser.add_argument(
        "--reconnect-delay", type=float, default=DEFAULT_RECONNECT_DELAY
    )
    parser.add_argument("--max-sessions", type=int, default=DEFAULT_MAX_SESSIONS)
    parser.add_argument(
        "--no-adopt",
        action="store_true",
        help="answer unknown client session ids with the SDK 404 instead of adopting them",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if not _is_loopback(args.host):
        print(
            f"error: --host {args.host!r} is not a loopback address; this proxy is "
            "loopback-only by design",
            file=sys.stderr,
        )
        return 2
    try:
        httpd = build_server(
            args.upstream,
            host=args.host,
            port=args.port,
            mcp_path=args.path,
            health_path=args.health_path,
            restart_log=args.restart_log or None,
            retry_after=args.retry_after,
            upstream_timeout=args.upstream_timeout,
            handshake_timeout=args.handshake_timeout,
            keepalive=args.keepalive,
            reconnect_delay=args.reconnect_delay,
            max_sessions=args.max_sessions,
            adopt_unknown_sessions=not args.no_adopt,
        )
    except (OSError, ValueError) as exc:
        print(f"error: cannot start bm-session-proxy: {exc}", file=sys.stderr)
        return 1
    proxy: SessionProxy = httpd.proxy  # type: ignore[attr-defined]
    print(
        f"bm-session-proxy {PROXY_VERSION} on http://{args.host}:{proxy.port}{args.path}"
        f" -> {args.upstream} (health {args.health_path}, restart log "
        f"{args.restart_log or 'off'})",
        file=sys.stderr,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        proxy.stop()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
