"""Talk to Basic Memory over HTTP MCP with session healing (stdio bridge).

Cursor's built-in Streamable-HTTP client keeps a stale ``mcp-session-id`` after
the :8765 daemon restarts (the watchdog restarts it near-daily under RAM
pressure) and sits on ``-32600 Session not found`` / ``ECONNREFUSED`` while the
port is healthy again (``.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md``; the
TypeScript SDK bug is modelcontextprotocol/typescript-sdk#1708). This process
is the stdio server Cursor talks to instead, and it:

* never binds :8765 and never starts or kills the daemon (the watchdog and
  ``BasicMemory-HTTP-MCP`` own that);
* on ``Session not found`` (HTTP 404 body or JSON-RPC error) re-initializes
  and replays the call once;
* on a dead port answers ``initialize`` / ``tools/list`` / ``ping`` from a
  small on-disk discovery cache so Cursor never loses the server, reports a
  ``tools/call`` as a readable ``isError`` result, and heals on the next call
  (or on its own via a background probe, announcing ``tools/list_changed``);
* relays server->client messages (SSE preludes and the GET stream) to stdio,
  and uses the GET stream's EOF as an early "daemon restarted" signal.

Modes:
  --stdio                 Cursor MCP stdio server (default when no --call/--health)
  --call TOOL ARGS_JSON   one-shot tools/call for agents when Cursor MCP is stale
  --health                one-shot initialize + ping, JSON report, exit 1 when down
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import pathlib
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, cast

DEFAULT_URL = "http://127.0.0.1:8765/mcp"
CLIENT_INFO = {"name": "bm-cursor-http-session", "version": "2"}
# What Basic Memory 3.3.x negotiates (measured 2026-08-27); the fallback when no
# cached negotiation exists and the daemon cannot be asked.
PROTOCOL = "2025-03-26"
CALL_TIMEOUT = 90.0
# The watchdog probes with 30 s because a healthy answer took >15 s under load.
HANDSHAKE_TIMEOUT = 30.0
RECONNECT_DELAY = 1.0
DEFAULT_PROBE_INTERVAL = 30.0
# After a failure, cheap requests answer locally for this long instead of each
# paying another probe window against a daemon that just failed.
DEFAULT_COOLDOWN = 5.0
STREAM_READ_TIMEOUT = 300.0
DEFAULT_CACHE_FILE = (
    pathlib.Path(tempfile.gettempdir()) / "bm-cursor-http-session-cache.json"
)
SESSION_HEADER = "Mcp-Session-Id"

_STDOUT_LOCK = threading.Lock()


class SessionGone(RuntimeError):
    """Server rejected the MCP session id (daemon restarted or session expired)."""


class TransportUnavailable(OSError):
    """The daemon could not be reached or did not answer (refused, reset, hung).

    ``timed_out`` separates a hung daemon (the attempt already cost the probe
    window) from a fast failure such as ECONNREFUSED (worth one quick retry).
    """

    def __init__(self, message: str, *, timed_out: bool = False) -> None:
        super().__init__(message)
        self.timed_out = timed_out


class StdioMessageError(ValueError):
    """Malformed or unsupported message received on MCP stdio."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# --- wire parsing --------------------------------------------------------------


def decode_rpc_message(raw: bytes) -> dict[str, Any]:
    try:
        value: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StdioMessageError(-32700, f"Parse error: {exc}") from exc
    if not isinstance(value, dict):
        raise StdioMessageError(-32600, "Invalid Request: expected a JSON object")
    return cast(dict[str, Any], value)


def parse_sse_messages(text: str) -> list[dict[str, Any]]:
    """Every JSON object carried by ``data:`` lines, one per SSE event, in order."""
    messages: list[dict[str, Any]] = []
    data_lines: list[str] = []

    def flush() -> None:
        if data_lines:
            value: Any = json.loads("\n".join(data_lines))
            if isinstance(value, dict):
                messages.append(cast(dict[str, Any], value))
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
        raise ValueError("Empty Basic Memory JSON-RPC response")
    ctype = (content_type or "").lower()
    if "text/event-stream" in ctype or text.startswith("event:") or "\ndata:" in text:
        messages = parse_sse_messages(text)
        if not messages:
            raise ValueError("Empty Basic Memory SSE response")
        return messages
    value: Any = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Basic Memory returned a non-object JSON-RPC response")
    return [cast(dict[str, Any], value)]


def is_response(message: dict[str, Any]) -> bool:
    return "method" not in message and ("result" in message or "error" in message)


def _expects_reply(payload: dict[str, Any]) -> bool:
    """Only a request (method + id) gets a body back; 202 is right for the rest."""
    return "method" in payload and "id" in payload


def parse_rpc_body(raw: bytes, content_type: str | None) -> dict[str, Any]:
    """The response in a body that may also carry notifications (SSE prelude)."""
    messages = parse_rpc_messages(raw, content_type)
    responses = [message for message in messages if is_response(message)]
    return responses[-1] if responses else messages[-1]


def is_session_not_found(payload: dict[str, Any]) -> bool:
    err = payload.get("error")
    if not isinstance(err, dict):
        return False
    msg = str(err.get("message") or "")
    code = err.get("code")
    return code == -32600 and "session not found" in msg.lower()


# --- the HTTP session ----------------------------------------------------------


class BmHttpSession:
    def __init__(
        self,
        url: str = DEFAULT_URL,
        timeout: float = CALL_TIMEOUT,
        *,
        handshake_timeout: float = HANDSHAKE_TIMEOUT,
        reconnect_delay: float = RECONNECT_DELAY,
        on_server_message: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self.handshake_timeout = handshake_timeout
        self.reconnect_delay = reconnect_delay
        self.on_server_message = on_server_message
        self.on_session_changed: Callable[[str | None], None] | None = None
        self._session_id: str | None = None
        self._next_id = 1
        self._initialized = False
        self.last_initialize_result: dict[str, Any] = {}
        self.server_info: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}
        self.protocol_version: str | None = None

    # -- state ---------------------------------------------------------------

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @session_id.setter
    def session_id(self, value: str | None) -> None:
        changed = value != self._session_id
        self._session_id = value
        if changed and self.on_session_changed is not None:
            self.on_session_changed(value)

    @property
    def initialized(self) -> bool:
        return self._initialized

    def mark_gone(self) -> None:
        """Forget the upstream session: the next call re-initializes first."""
        self._initialized = False
        self.session_id = None

    def _alloc_id(self) -> int:
        rid = self._next_id
        self._next_id += 1
        return rid

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers[SESSION_HEADER] = self.session_id
        if self.protocol_version:
            headers["MCP-Protocol-Version"] = self.protocol_version
        return headers

    # -- transport -----------------------------------------------------------

    def _select_response(
        self, messages: list[dict[str, Any]], payload: dict[str, Any]
    ) -> dict[str, Any]:
        want_id = payload.get("id")
        responses = [message for message in messages if is_response(message)]
        chosen = next((m for m in responses if m.get("id") == want_id), None)
        if chosen is None and responses:
            chosen = responses[-1]
        for message in messages:
            if message is chosen:
                continue
            if is_response(message):
                continue  # a stray response to nothing we asked
            if self.on_server_message is not None:
                self.on_server_message(message)
        if chosen is None:
            if not _expects_reply(payload):
                return {}
            raise ValueError("Basic Memory stream ended without a response")
        return chosen

    def post_raw(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        body = json.dumps(payload).encode("utf-8")
        # initialize and ping are cheap: a slow answer is the watchdog's own
        # "bound but unresponsive" signal, so they get the probe timeout, not the
        # long tool-call one.
        timeout = (
            self.handshake_timeout
            if payload.get("method") in ("initialize", "ping")
            else self.timeout
        )
        req = urllib.request.Request(
            self.url, data=body, method="POST", headers=self._headers()
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                sid = resp.headers.get(SESSION_HEADER) or resp.headers.get(
                    SESSION_HEADER.lower()
                )
                content_type = resp.headers.get("Content-Type")
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            content_type = exc.headers.get("Content-Type") if exc.headers else None
            try:
                messages = parse_rpc_messages(raw, content_type)
            except ValueError:
                messages = []
            if not messages:
                raise TransportUnavailable(
                    f"{self.url}: HTTP {exc.code} {exc.reason}"
                ) from exc
            return self._select_response(messages, payload), None
        except (OSError, http.client.HTTPException) as exc:
            # ECONNREFUSED / reset / timeout: the daemon is dead, dying or hung.
            self.mark_gone()
            reason = getattr(exc, "reason", None)
            timed_out = isinstance(exc, TimeoutError) or isinstance(
                reason, TimeoutError
            )
            raise TransportUnavailable(
                f"{self.url}: {reason or exc}", timed_out=timed_out
            ) from exc
        try:
            messages = parse_rpc_messages(raw, content_type)
        except ValueError:
            if not _expects_reply(payload):
                return {}, sid  # 202 Accepted for a notification / response
            raise
        return self._select_response(messages, payload), sid

    def rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._alloc_id(),
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        if method != "initialize" and not self.session_id:
            # The stream listener saw the daemon go while this call was queued.
            raise SessionGone("no upstream session")
        parsed, sid = self.post_raw(payload)
        if sid:
            self.session_id = sid
        if is_session_not_found(parsed):
            self._initialized = False
            raise SessionGone(
                parsed.get("error", {}).get("message", "Session not found")
            )
        return parsed

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        if not self.session_id:
            return  # nothing upstream to notify
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        try:
            parsed, _ = self.post_raw(payload)
        except TransportUnavailable:
            return  # notifications are fire-and-forget on a dying socket
        if is_session_not_found(parsed):
            self.mark_gone()

    def post_response(self, message: dict[str, Any]) -> None:
        """Forward the client's answer to a server->client request."""
        if not self.session_id:
            return
        try:
            self.post_raw(message)
        except TransportUnavailable:
            return

    def handshake(
        self,
        protocol_version: str = PROTOCOL,
        *,
        notify_initialized: bool = True,
    ) -> dict[str, Any]:
        self.mark_gone()
        result = self.rpc(
            "initialize",
            {
                "protocolVersion": protocol_version,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
        )
        if "error" in result:
            return result
        payload = result.get("result")
        self.last_initialize_result = payload if isinstance(payload, dict) else {}
        info = self.last_initialize_result.get("serverInfo")
        self.server_info = info if isinstance(info, dict) else {}
        caps = self.last_initialize_result.get("capabilities")
        self.capabilities = caps if isinstance(caps, dict) else {}
        negotiated = self.last_initialize_result.get("protocolVersion")
        self.protocol_version = negotiated if isinstance(negotiated, str) else None
        if notify_initialized:
            self.notify("notifications/initialized")
        self._initialized = True
        return result

    def _connect(self, attempt: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        """One handshake attempt plus a single quick retry for a fast failure.

        A timeout is not retried: the attempt already blocked for the whole
        probe window, and a hung daemon will not answer a second time sooner.
        """
        try:
            return attempt()
        except TransportUnavailable as exc:
            if (
                exc.timed_out
                or self.reconnect_delay is None
                or self.reconnect_delay < 0
            ):
                raise
            time.sleep(self.reconnect_delay)
            return attempt()

    def call_with_retry(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if method == "initialize":
            version_value = (
                params.get("protocolVersion") if isinstance(params, dict) else None
            )
            requested_version = (
                version_value if isinstance(version_value, str) else PROTOCOL
            )
            return self._connect(
                lambda: self.handshake(requested_version, notify_initialized=False)
            )
        if not self._initialized:
            init = self._connect(self.handshake)
            if "error" in init:
                return init
        try:
            return self.rpc(method, params)
        except SessionGone:
            init = self.handshake()
            if "error" in init:
                return init
            if method == "notifications/initialized":
                return {"jsonrpc": "2.0", "result": None}
            try:
                return self.rpc(method, params)
            except SessionGone as exc:
                # Two restarts inside one call: the daemon is flapping. Surface it
                # as unavailable instead of looping on it.
                self.mark_gone()
                raise TransportUnavailable(
                    f"{self.url}: session lost twice in a row ({exc})"
                ) from exc

    def terminate(self) -> None:
        """Best-effort ``DELETE`` so the daemon frees the session on exit."""
        sid = self.session_id
        self.mark_gone()
        if not sid:
            return
        req = urllib.request.Request(
            self.url,
            method="DELETE",
            headers={
                SESSION_HEADER: sid,
                "Accept": "application/json, text/event-stream",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
        except (OSError, http.client.HTTPException):
            return


# --- discovery cache -------------------------------------------------------------


class DiscoveryCache:
    """Last successful ``initialize`` + ``tools/list`` for one daemon URL.

    Served while the daemon is dead so Cursor never loses discovery; written
    atomically and treated as disposable (a corrupt or foreign file is ignored).
    """

    VERSION = 1

    def __init__(self, path: pathlib.Path | str | None, *, url: str) -> None:
        self.path = pathlib.Path(path) if path is not None else None
        self.url = url

    def load(self) -> dict[str, Any] | None:
        if self.path is None:
            return None
        try:
            value: Any = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if (
            not isinstance(value, dict)
            or value.get("version") != self.VERSION
            or value.get("url") != self.url
            or not isinstance(value.get("initialize"), dict)
            or not isinstance(value.get("tools"), dict)
        ):
            return None
        return cast(dict[str, Any], value)

    def save(self, initialize: dict[str, Any], tools: dict[str, Any]) -> None:
        if self.path is None:
            return
        payload = {
            "version": self.VERSION,
            "url": self.url,
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "initialize": initialize,
            "tools": tools,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False)
                os.replace(tmp_name, self.path)
            except BaseException:
                pathlib.Path(tmp_name).unlink(missing_ok=True)
                raise
        except OSError:
            return  # the cache is best-effort; a full or read-only disk is not fatal


# --- stdio framing ---------------------------------------------------------------


def read_stdio_message() -> dict[str, Any] | None:
    while True:
        first_line = sys.stdin.buffer.readline()
        if not first_line:
            return None
        if first_line not in (b"\r\n", b"\n"):
            break

    # MCP stdio uses one JSON-RPC message per line. Retain Content-Length input
    # support for older callers, but always emit MCP-native NDJSON below.
    if not first_line.lower().startswith(b"content-length:"):
        return decode_rpc_message(first_line)

    header_lines = [first_line]
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        header_lines.append(line)

    length = None
    for raw_line in header_lines:
        line = raw_line.decode("ascii", errors="replace").strip()
        if line.lower().startswith("content-length:"):
            try:
                length = int(line.split(":", 1)[1].strip())
            except ValueError as exc:
                raise StdioMessageError(-32600, "Invalid Content-Length") from exc
            break
    if length is None or length <= 0:
        raise StdioMessageError(-32600, "Invalid Content-Length")
    body = sys.stdin.buffer.read(length)
    if len(body) != length:
        raise StdioMessageError(-32700, "Incomplete Content-Length frame")
    return decode_rpc_message(body)


def write_stdio_message(payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    with _STDOUT_LOCK:
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()


def write_stdio_error(req_id: Any, code: int, message: str) -> None:
    write_stdio_message(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message[:500]},
        }
    )


# --- GET server->client stream -----------------------------------------------------


class ServerStreamListener(threading.Thread):
    """Hold the Streamable-HTTP GET stream open and relay what the server pushes.

    The stream is bound to the session id, so its EOF is the earliest sign that
    the daemon restarted: the session is marked gone before Cursor's next call
    would have wasted a round-trip on ``Session not found``.
    """

    def __init__(
        self,
        session: BmHttpSession,
        deliver: Callable[[dict[str, Any]], None],
        *,
        read_timeout: float = STREAM_READ_TIMEOUT,
    ) -> None:
        super().__init__(name="bm-server-stream", daemon=True)
        self.session = session
        self.deliver = deliver
        self.read_timeout = read_timeout
        self.disabled = False
        self._stop = threading.Event()
        self._wake = threading.Event()

    def wake(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def run(self) -> None:
        failures = 0
        while not self._stop.is_set():
            sid = self.session.session_id
            if self.disabled or not sid or not self.session.initialized:
                self._wake.wait(1.0)
                self._wake.clear()
                continue
            outcome = self._consume(sid)
            if self._stop.is_set():
                return
            if outcome in ("eof", "gone") and self.session.session_id == sid:
                # The server closed the stream bound to this id: the session is
                # over, so the next call re-initializes instead of hitting a 404.
                self.session.mark_gone()
            if outcome in ("eof", "gone", "timeout"):
                failures = 0
                pause = 0.5
            elif outcome == "busy":
                pause = 5.0  # 409: the server still counts the previous stream
            else:
                failures += 1
                pause = min(30.0, 2.0**failures)
            self._wake.wait(pause)
            self._wake.clear()

    def _consume(self, sid: str) -> str:
        req = urllib.request.Request(
            self.session.url,
            method="GET",
            headers={
                "Accept": "text/event-stream",
                SESSION_HEADER: sid,
                "Cache-Control": "no-cache",
            },
        )
        try:
            resp = urllib.request.urlopen(req, timeout=self.read_timeout)
        except urllib.error.HTTPError as exc:
            exc.read()
            if exc.code == 405:
                self.disabled = True  # the server offers no GET stream
                return "disabled"
            if exc.code == 404:
                return "gone"
            if exc.code == 409:
                return "busy"
            return "error"
        except (OSError, http.client.HTTPException):
            return "error"
        data_lines: list[bytes] = []
        try:
            with resp:
                while not self._stop.is_set():
                    line = resp.readline()
                    if not line:
                        return "eof"
                    line = line.rstrip(b"\r\n")
                    if not line:
                        self._dispatch(data_lines)
                        data_lines = []
                    elif line.startswith(b"data:"):
                        data_lines.append(line[5:].lstrip())
        except TimeoutError:
            return "timeout"
        except (OSError, http.client.HTTPException):
            return "eof"
        return "stopped"

    def _dispatch(self, data_lines: list[bytes]) -> None:
        if not data_lines:
            return
        try:
            value: Any = json.loads(b"\n".join(data_lines).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if isinstance(value, dict) and "method" in value:
            self.deliver(cast(dict[str, Any], value))


# --- the stdio bridge -------------------------------------------------------------


class StdioBridge:
    """Serve Cursor over stdio; the daemon may die and come back underneath."""

    LOCAL_LISTS = {
        "resources/list": {"resources": []},
        "resources/templates/list": {"resourceTemplates": []},
        "prompts/list": {"prompts": []},
    }
    # Answered from local state while the daemon is known to be down. tools/call
    # is deliberately absent: it always tries upstream, because it is how the
    # bridge heals on the next call.
    LOCAL_WHILE_DOWN = frozenset({"initialize", "tools/list", "ping", *LOCAL_LISTS})

    def __init__(
        self,
        session: Any,
        *,
        cache: DiscoveryCache | None = None,
        probe_interval: float = 0.0,
        stream: bool = False,
        cooldown: float = DEFAULT_COOLDOWN,
    ) -> None:
        self.session = session
        self.cache = cache
        self.probe_interval = probe_interval
        self.cooldown = cooldown
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._degraded = False
        self._degraded_until = 0.0
        self._last_error: BaseException = TransportUnavailable("not yet attempted")
        self._announced_tools: dict[str, Any] | None = None
        self._prober: threading.Thread | None = None
        self._listener: ServerStreamListener | None = None
        if stream and isinstance(session, BmHttpSession):
            self._listener = ServerStreamListener(session, self._deliver_server_message)
            session.on_session_changed = lambda _sid: self._listener_wake()
        if isinstance(session, BmHttpSession) and session.on_server_message is None:
            session.on_server_message = self._deliver_server_message

    # -- plumbing ------------------------------------------------------------

    def _listener_wake(self) -> None:
        if self._listener is not None:
            self._listener.wake()

    def _deliver_server_message(self, message: dict[str, Any]) -> None:
        if "method" in message:
            write_stdio_message(message)

    def run(self) -> int:
        if self._listener is not None:
            self._listener.start()
        try:
            while True:
                try:
                    msg = read_stdio_message()
                except StdioMessageError as exc:
                    write_stdio_error(None, exc.code, exc.message)
                    continue
                if msg is None:
                    return 0
                self.handle(msg)
        finally:
            self._stop.set()
            if self._listener is not None:
                self._listener.stop()
            terminate = getattr(self.session, "terminate", None)
            if callable(terminate):
                with self._lock:
                    terminate()

    # -- dispatch ------------------------------------------------------------

    def handle(self, msg: dict[str, Any]) -> None:
        method = msg.get("method")
        params = msg.get("params")
        req_id = msg.get("id")
        if not isinstance(method, str):
            if req_id is not None and is_response(msg):
                self._forward_client_response(msg)
                return
            write_stdio_error(
                req_id, -32600, "Invalid Request: method must be a string"
            )
            return
        params = params if isinstance(params, dict) else None
        if req_id is None:
            self._forward_notification(method, params)
            return
        with self._lock:
            if self._in_cooldown() and method in self.LOCAL_WHILE_DOWN:
                # The daemon failed moments ago; a cheap request should not pay
                # another probe window. tools/call and the prober still try.
                write_stdio_message(
                    self._degraded_answer(req_id, method, params, self._last_error)
                )
                return
            try:
                result = self.session.call_with_retry(method, params)
            except OSError as exc:
                self._enter_degraded(exc)
                out = self._degraded_answer(req_id, method, params, exc)
            except ValueError as exc:
                write_stdio_error(req_id, -32603, f"Basic Memory response error: {exc}")
                return
            else:
                self._note_success(method, result)
                out = {"jsonrpc": "2.0", "id": req_id}
                if "error" in result:
                    out["error"] = result["error"]
                else:
                    out["result"] = result.get("result")
        write_stdio_message(out)

    def _forward_notification(self, method: str, params: dict[str, Any] | None) -> None:
        with self._lock:
            try:
                self.session.notify(method, params)
            except SessionGone:
                mark = getattr(self.session, "mark_gone", None)
                if callable(mark):
                    mark()
            except OSError:
                return

    def _forward_client_response(self, message: dict[str, Any]) -> None:
        post = getattr(self.session, "post_response", None)
        if not callable(post):
            return
        with self._lock:
            try:
                post(message)
            except OSError:
                return

    # -- degraded mode -------------------------------------------------------

    def _enter_degraded(self, exc: BaseException | None = None) -> None:
        self._degraded = True
        if exc is not None:
            self._last_error = exc
        self._degraded_until = time.monotonic() + max(self.cooldown, 0.0)
        self._start_prober()

    def _in_cooldown(self) -> bool:
        return self._degraded and time.monotonic() < self._degraded_until

    def _cached(self) -> dict[str, Any] | None:
        return self.cache.load() if self.cache is not None else None

    def _unavailable_text(self, exc: BaseException) -> str:
        url = getattr(self.session, "url", DEFAULT_URL)
        return (
            f"Basic Memory is not reachable at {url} ({exc}). The daemon restarts "
            "itself (BasicMemory-Watchdog: 3-min cycle, then a 2.5-4 min warm-up on "
            "this box); this bridge keeps the MCP connection alive and heals on the "
            "next call. Retry shortly; do not start a second daemon."
        )

    def _local_initialize(self, params: dict[str, Any] | None) -> dict[str, Any]:
        cached = self._cached()
        init = cached["initialize"] if cached else {}
        capabilities = dict(init.get("capabilities") or {})
        tools_caps = dict(capabilities.get("tools") or {})
        tools_caps["listChanged"] = True
        capabilities["tools"] = tools_caps
        result: dict[str, Any] = {
            "protocolVersion": init.get("protocolVersion") or PROTOCOL,
            "capabilities": capabilities,
            "serverInfo": init.get("serverInfo")
            or {"name": "Basic Memory", "version": "unavailable"},
        }
        if isinstance(init.get("instructions"), str):
            result["instructions"] = init["instructions"]
        return result

    def _local_tools(self) -> dict[str, Any]:
        cached = self._cached()
        tools = cached["tools"] if cached else {"tools": []}
        self._announced_tools = tools
        return tools

    def _degraded_answer(
        self,
        req_id: Any,
        method: str,
        params: dict[str, Any] | None,
        exc: BaseException,
    ) -> dict[str, Any]:
        result: dict[str, Any] | None = None
        if method == "initialize":
            result = self._local_initialize(params)
        elif method == "tools/list":
            result = self._local_tools()
        elif method == "ping":
            result = {}
        elif method in self.LOCAL_LISTS:
            result = dict(self.LOCAL_LISTS[method])
        elif method == "tools/call":
            result = {
                "content": [{"type": "text", "text": self._unavailable_text(exc)}],
                "isError": True,
            }
        if result is None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32000,
                    "message": f"Basic Memory transport unavailable: {exc}"[:500],
                },
            }
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    # -- recovery ------------------------------------------------------------

    def _note_success(self, method: str, result: dict[str, Any]) -> None:
        was_degraded = self._degraded
        self._degraded = False
        if "error" in result:
            return
        if method == "tools/list":
            tools = result.get("result")
            if isinstance(tools, dict):
                self._announce(tools)
            return
        if was_degraded:
            self._reconcile_tools()

    def _announce(self, tools: dict[str, Any]) -> None:
        self._announced_tools = tools
        init = getattr(self.session, "last_initialize_result", None)
        if self.cache is not None and isinstance(init, dict) and init:
            self.cache.save(init, tools)

    def _reconcile_tools(self) -> None:
        """After healing, tell Cursor when the live tool list differs from what it saw."""
        try:
            result = self.session.call_with_retry("tools/list")
        except (OSError, ValueError) as exc:
            self._enter_degraded(exc if isinstance(exc, OSError) else None)
            return
        live = result.get("result")
        if not isinstance(live, dict):
            return
        previous = self._announced_tools
        self._announce(live)
        if previous is not None and previous != live:
            write_stdio_message(
                {"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}
            )

    def _start_prober(self) -> None:
        if self.probe_interval <= 0:
            return
        if self._prober is not None and self._prober.is_alive():
            return
        self._prober = threading.Thread(
            target=self._probe_loop, name="bm-recovery-probe", daemon=True
        )
        self._prober.start()

    def _probe_loop(self) -> None:
        while not self._stop.wait(self.probe_interval):
            with self._lock:
                if not self._degraded:
                    return
                try:
                    result = self.session.call_with_retry("ping")
                except (OSError, ValueError):
                    continue
                self._note_success("ping", result)
                if not self._degraded:
                    return


def stdio_loop(
    session: Any,
    *,
    cache: DiscoveryCache | None = None,
    probe_interval: float = 0.0,
    stream: bool = False,
    cooldown: float = DEFAULT_COOLDOWN,
) -> int:
    return StdioBridge(
        session,
        cache=cache,
        probe_interval=probe_interval,
        stream=stream,
        cooldown=cooldown,
    ).run()


# --- one-shot modes ---------------------------------------------------------------


def health(session: BmHttpSession) -> int:
    try:
        result = session.call_with_retry("ping")
    except OSError as exc:
        print(
            json.dumps({"ok": False, "url": session.url, "error": str(exc)}, indent=2)
        )
        return 1
    report: dict[str, Any] = {
        "ok": "error" not in result,
        "url": session.url,
        "serverInfo": session.server_info,
        "protocolVersion": session.protocol_version,
        "sessionId": session.session_id,
    }
    if "error" in result:
        report["error"] = result["error"]
    session.terminate()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


def _is_tool_error(result: dict[str, Any]) -> bool:
    inner = result.get("result")
    return isinstance(inner, dict) and inner.get("isError") is True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--stdio", action="store_true", help="Cursor MCP stdio server")
    parser.add_argument(
        "--call", nargs=2, metavar=("TOOL", "ARGS_JSON"), help="one-shot tools/call"
    )
    parser.add_argument(
        "--health", action="store_true", help="one-shot initialize + ping report"
    )
    parser.add_argument("--timeout", type=float, default=CALL_TIMEOUT)
    parser.add_argument("--handshake-timeout", type=float, default=HANDSHAKE_TIMEOUT)
    parser.add_argument("--reconnect-delay", type=float, default=RECONNECT_DELAY)
    parser.add_argument(
        "--cache-file",
        default=str(DEFAULT_CACHE_FILE),
        help="discovery cache served while the daemon is down",
    )
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument(
        "--probe-interval",
        type=float,
        default=DEFAULT_PROBE_INTERVAL,
        help="seconds between recovery probes while degraded (0 = only heal on traffic)",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=DEFAULT_COOLDOWN,
        help="seconds to serve cacheable calls locally after the daemon drops, before re-probing the port",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="do not hold the GET server->client stream",
    )
    args = parser.parse_args(argv)
    session = BmHttpSession(
        url=args.url,
        timeout=args.timeout,
        handshake_timeout=args.handshake_timeout,
        reconnect_delay=args.reconnect_delay,
    )
    if args.health:
        return health(session)
    if args.call:
        tool, raw_args = args.call
        params = {"name": tool, "arguments": json.loads(raw_args)}
        result = session.call_with_retry("tools/call", params)
        session.terminate()
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0 if "error" not in result and not _is_tool_error(result) else 1
    cache = None if args.no_cache else DiscoveryCache(args.cache_file, url=args.url)
    return stdio_loop(
        session,
        cache=cache,
        probe_interval=args.probe_interval,
        stream=not args.no_stream,
        cooldown=args.cooldown,
    )


if __name__ == "__main__":
    raise SystemExit(main())
