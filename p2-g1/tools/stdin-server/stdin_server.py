"""Desktop Commander interactive-stdin MCP server (stdlib-only, zero-dependency).

Closes a concrete gap: Claude Code's Bash tool runs `-NonInteractive` with stdin
wired to the null device, so it cannot steer a live REPL or any process that
reads from stdin after start-up. This server owns persistent child processes and
lets a caller write to their stdin and read incremental stdout, over
newline-delimited JSON-RPC 2.0 on the server's own stdin/stdout.

Three verbs, and only three:

* ``start_process(command, cwd?)``        -> ``{session_id, pid}``
* ``interact_with_process(session_id, input, wait_ms=200)``
                                          -> ``{output, alive, exit_code}``
* ``read_process_output(session_id, max_chars=8192, timeout_ms=1000)``
                                          -> ``{output, more, truncated, alive, exit_code}``

Design notes
------------
* **Opt-in mount, NOT always-on.** This box has a measured commit-exhaustion
  freeze caused by per-session stdio-MCP duplication, so this server is written
  with zero third-party dependencies and is meant to be mounted only for the
  session that needs an interactive channel.
* **Bounded memory.** Each child's stdout is drained by a daemon thread into a
  fixed-size ring (``BUFFER_CAP`` characters, drop-oldest), so a chatty child
  cannot grow memory without bound. Dropped output is surfaced as ``truncated``.
* **Windows caveat.** ``pty`` is Unix-only, so children are driven over ordinary
  pipes. A program that gates its prompt on ``isatty()`` may suppress that prompt
  when its stdout is a pipe; for the CPython REPL, launch it with ``-i -u`` (as
  the tests do). A ConPTY / pywinpty front-end is a documented follow-on that is
  deliberately outside this stdlib-only scope.
"""

from __future__ import annotations

import atexit
import itertools
import json
import subprocess
import sys
import threading
import time
from collections import deque

BUFFER_CAP = 256 * 1024
MAX_SESSIONS = 16
_DEFAULT_WAIT_MS = 200
_DEFAULT_READ_MAX = 8192
_DEFAULT_READ_TIMEOUT_MS = 1000
_POLL_INTERVAL_S = 0.01

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "stdin-server"
SERVER_VERSION = "0.1.0"


class ManagedProcess:
    """A live child process whose stdout is drained into a bounded ring buffer.

    A single daemon reader thread reads the child's merged stdout+stderr one
    character at a time (so interactive prompts arrive without waiting for a full
    buffer to fill) and appends into a deque capped at ``buffer_cap`` characters.
    Once the cap is exceeded the oldest characters are discarded and the drop is
    remembered so a later read can report ``truncated``.
    """

    def __init__(
        self,
        command: list[str],
        cwd: str | None = None,
        *,
        buffer_cap: int = BUFFER_CAP,
        _popen=subprocess.Popen,
    ) -> None:
        self._proc = _popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            text=True,
            cwd=cwd,
        )
        self._buffer_cap = buffer_cap
        self._buf: deque[str] = deque()
        self._dropped = False
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._drain, daemon=True)
        self._reader.start()

    @property
    def pid(self) -> int:
        return self._proc.pid

    def _drain(self) -> None:
        stream = self._proc.stdout
        while True:
            chunk = stream.read(1)
            if chunk == "":
                break  # EOF: the child closed stdout / exited
            with self._lock:
                self._buf.append(chunk)
                while len(self._buf) > self._buffer_cap:
                    self._buf.popleft()
                    self._dropped = True

    def _snapshot(self, max_chars: int) -> tuple[str, bool]:
        with self._lock:
            out: list[str] = []
            while self._buf and len(out) < max_chars:
                out.append(self._buf.popleft())
            return "".join(out), bool(self._buf)

    def take_dropped(self) -> bool:
        with self._lock:
            dropped = self._dropped
            self._dropped = False
            return dropped

    def send(self, data: str) -> bool:
        try:
            self._proc.stdin.write(data)
            self._proc.stdin.flush()
        except (BrokenPipeError, ValueError, OSError):
            return False
        return True

    def read(
        self,
        max_chars: int,
        timeout_ms: int,
        *,
        _clock=time.monotonic,
        _sleep=time.sleep,
    ) -> tuple[str, bool]:
        deadline = _clock() + timeout_ms / 1000.0
        out, more = self._snapshot(max_chars)
        while not out and _clock() < deadline:
            _sleep(_POLL_INTERVAL_S)
            out, more = self._snapshot(max_chars)
        return out, more

    def poll(self) -> int | None:
        return self._proc.poll()

    def terminate(self) -> None:
        if self._proc.poll() is not None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:  # pragma: no cover - child ignores SIGTERM
            self._proc.kill()


class Server:
    """A capped registry of :class:`ManagedProcess` sessions plus the 3 verbs."""

    def __init__(
        self,
        *,
        max_sessions: int = MAX_SESSIONS,
        proc_factory=ManagedProcess,
    ) -> None:
        self._sessions: dict[str, ManagedProcess] = {}
        self._counter = itertools.count(1)
        self._max_sessions = max_sessions
        self._proc_factory = proc_factory

    def start_process(self, command: list[str], cwd: str | None = None) -> dict:
        if not command:
            raise ValueError("command is required")
        if len(self._sessions) >= self._max_sessions:
            raise RuntimeError(f"session limit reached ({self._max_sessions})")
        proc = self._proc_factory(command, cwd)
        session_id = f"proc-{next(self._counter)}"
        self._sessions[session_id] = proc
        return {"session_id": session_id, "pid": proc.pid}

    def _get(self, session_id: str) -> ManagedProcess:
        proc = self._sessions.get(session_id)
        if proc is None:
            raise KeyError(f"unknown session_id: {session_id}")
        return proc

    def interact_with_process(
        self,
        session_id: str,
        input: str,
        wait_ms: int = _DEFAULT_WAIT_MS,
    ) -> dict:
        proc = self._get(session_id)
        proc.send(input)
        time.sleep(max(wait_ms, 0) / 1000.0)
        output, _more = proc.read(BUFFER_CAP, 0)
        code = proc.poll()
        return {"output": output, "alive": code is None, "exit_code": code}

    def read_process_output(
        self,
        session_id: str,
        max_chars: int = _DEFAULT_READ_MAX,
        timeout_ms: int = _DEFAULT_READ_TIMEOUT_MS,
    ) -> dict:
        proc = self._get(session_id)
        output, more = proc.read(max_chars, timeout_ms)
        truncated = proc.take_dropped()
        code = proc.poll()
        return {
            "output": output,
            "more": more,
            "truncated": truncated,
            "alive": code is None,
            "exit_code": code,
        }

    def cleanup(self) -> None:
        for proc in list(self._sessions.values()):
            proc.terminate()
        self._sessions.clear()


TOOL_SCHEMAS = [
    {
        "name": "start_process",
        "description": (
            "Start a persistent child process whose stdin stays open for later "
            "input. Returns a session_id to address it and the OS pid."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "argv list, e.g. ['python', '-i', '-u']",
                },
                "cwd": {"type": "string", "description": "working directory"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "interact_with_process",
        "description": (
            "Write input to a session's stdin, wait wait_ms, then return the "
            "output produced so far plus liveness."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "input": {"type": "string"},
                "wait_ms": {"type": "integer", "default": _DEFAULT_WAIT_MS},
            },
            "required": ["session_id", "input"],
        },
    },
    {
        "name": "read_process_output",
        "description": (
            "Read up to max_chars of buffered output for a session, blocking up "
            "to timeout_ms for the first byte. 'more' means output remains; "
            "'truncated' means the ring buffer dropped older output."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "max_chars": {"type": "integer", "default": _DEFAULT_READ_MAX},
                "timeout_ms": {"type": "integer", "default": _DEFAULT_READ_TIMEOUT_MS},
            },
            "required": ["session_id"],
        },
    },
]

_TOOL_DISPATCH = {
    "start_process": lambda srv, a: srv.start_process(a["command"], a.get("cwd")),
    "interact_with_process": lambda srv, a: srv.interact_with_process(
        a["session_id"], a["input"], a.get("wait_ms", _DEFAULT_WAIT_MS)
    ),
    "read_process_output": lambda srv, a: srv.read_process_output(
        a["session_id"],
        a.get("max_chars", _DEFAULT_READ_MAX),
        a.get("timeout_ms", _DEFAULT_READ_TIMEOUT_MS),
    ),
}


def _tool_result(request_id, payload: dict, *, is_error: bool = False) -> dict:
    result = {"content": [{"type": "text", "text": json.dumps(payload)}]}
    if is_error:
        result["isError"] = True
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def handle_request(server: Server, obj: dict) -> dict | None:
    """Dispatch one decoded JSON-RPC request; return a response dict or None.

    ``None`` is returned for notifications (a request without an ``id``), which
    per JSON-RPC must not produce a response.
    """
    method = obj.get("method")
    request_id = obj.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOL_SCHEMAS}}
    if method == "tools/call":
        params = obj.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        handler = _TOOL_DISPATCH.get(name)
        if handler is None:
            return _tool_result(
                request_id, {"error": f"unknown tool: {name}"}, is_error=True
            )
        try:
            payload = handler(server, args)
        except (ValueError, KeyError, RuntimeError) as exc:
            return _tool_result(request_id, {"error": str(exc)}, is_error=True)
        return _tool_result(request_id, payload)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


def _write(writer, obj: dict) -> None:
    writer.write(json.dumps(obj) + "\n")
    writer.flush()


def serve(server: Server, reader, writer) -> None:
    """Run the newline-delimited JSON-RPC loop until ``reader`` reaches EOF."""
    for raw in reader:
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            _write(
                writer,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "parse error"},
                },
            )
            continue
        response = handle_request(server, obj)
        if response is not None:
            _write(writer, response)


_SERVER = Server()
atexit.register(_SERVER.cleanup)


def main() -> int:
    serve(_SERVER, sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
