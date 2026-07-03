#!/usr/bin/env python3
"""social-hub — a LAZY, NAME-PRESERVING MCP multiplexer over N social backends.

Fronts several social MCP servers (Instagram, TikTok, Facebook-Messenger,
WhatsApp, fb-reels) behind ONE MCP registration while keeping every tool under
its ORIGINAL name.  ``initialize`` and ``tools/list`` are answered from committed
per-backend caches WITHOUT spawning anything (the RAM win + the idle-cheap
promise).  A ``tools/call`` resolves the owning backend, lazily spawns ONLY that
child (once, kept alive for the session), and forwards the request.  A backend
that cannot spawn or enumerate degrades to a clear per-tool error; the hub never
crashes and never renames a tool unless its name genuinely collides across
backends (then a minimal ``<prefix>_`` is applied and advertised).

This extends ``../lazy_proxy.py`` (one child) to the multi-child case.

Modes::

    python hub.py                      # runtime stdio MCP (what ~/.mcp.json runs)
    python hub.py --refresh [ids...]   # (re)generate tool caches by enumerating
    python hub.py --print-plan         # print the merged plan (counts/collisions)

Transport = newline-delimited JSON-RPC (MCP stdio), stdlib only, matching the
lazy_proxy style.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backends import BackendSpec, default_backends  # noqa: E402
from registry import Plan, build_plan  # noqa: E402

HUB_VERSION = "0.1.0"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "caches")
INIT_ID = "_hub_init"
ENUM_TIMEOUT = 45.0   # seconds to wait for a backend's initialize/tools-list
SPAWN_TIMEOUT = 30.0  # seconds to wait for a lazy child to become ready


def _spawn(cmd: tuple[str, ...], env: dict[str, str]) -> subprocess.Popen:
    """Spawn an MCP child with UTF-8 pipes (Windows defaults to cp1252)."""
    return subprocess.Popen(
        list(cmd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, bufsize=1,
        encoding="utf-8", errors="replace", env=env,
    )


def _reader(proc: subprocess.Popen, q: "queue.Queue[str | None]") -> None:
    """Pump one child's stdout into a queue; enqueue None on EOF."""
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            q.put(line)
    finally:
        q.put(None)


def _drain_until(q: "queue.Queue[str | None]", want_id, deadline: float,
                 on_other=None) -> dict:
    """Read queued lines until a JSON-RPC message with id==want_id appears.

    Non-matching JSON messages are handed to ``on_other`` (or dropped). Raises
    TimeoutError past ``deadline`` or EOFError if the child exits first.
    """
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("deadline exceeded")
        try:
            line = q.get(timeout=remaining)
        except queue.Empty as exc:
            raise TimeoutError("deadline exceeded") from exc
        if line is None:
            raise EOFError("child exited")
        s = line.strip()
        if not s.startswith("{"):
            continue
        try:
            msg = json.loads(s)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == want_id:
            return msg
        if on_other is not None:
            on_other(s)


class RuntimeBackend:
    """A fronted backend plus its (lazily spawned) child process."""

    def __init__(self, spec: BackendSpec, out_write) -> None:
        self.spec = spec
        self._out = out_write            # callable(str) -> emits a raw JSON line
        self.proc: subprocess.Popen | None = None
        self.q: "queue.Queue[str | None]" = queue.Queue()
        self.started = False
        self.ok = False
        self.error = ""

    def ensure_started(self) -> bool:
        """Spawn + initialize the child once; return readiness (cached)."""
        if self.started:
            return self.ok and self._alive()
        self.started = True
        try:
            self.proc = _spawn(self.spec.cmd, self.spec.child_env())
        except OSError as exc:
            self.error = f"spawn failed: {exc}"
            return False
        threading.Thread(target=_reader, args=(self.proc, self.q),
                         daemon=True).start()
        self._send({"jsonrpc": "2.0", "id": INIT_ID, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05",
                               "capabilities": {},
                               "clientInfo": {"name": "social-hub",
                                              "version": HUB_VERSION}}})
        try:
            _drain_until(self.q, INIT_ID, time.monotonic() + SPAWN_TIMEOUT,
                         on_other=self._out)
        except (TimeoutError, EOFError) as exc:
            self.error = f"initialize failed: {exc}"
            self._terminate()
            return False
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.ok = True
        threading.Thread(target=self._pump, daemon=True).start()
        return True

    def forward_call(self, request: dict, original_name: str) -> bool:
        """Rewrite the tool name to its original and forward, keeping the id."""
        if not self._alive():
            self.error = "child exited"
            return False
        req = dict(request)
        params = dict(req.get("params") or {})
        params["name"] = original_name
        req["params"] = params
        return self._send(req)

    def _pump(self) -> None:
        """Copy every subsequent child->client JSON line to the hub stdout."""
        while True:
            line = self.q.get()
            if line is None:
                break
            s = line.strip()
            if s.startswith("{"):
                self._out(s)

    def _send(self, obj: dict) -> bool:
        try:
            self.proc.stdin.write(json.dumps(obj) + "\n")  # type: ignore[union-attr]
            self.proc.stdin.flush()  # type: ignore[union-attr]
            return True
        except (OSError, ValueError, AttributeError) as exc:
            self.error = f"write failed: {exc}"
            return False

    def _alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _terminate(self) -> None:
        try:
            if self.proc is not None:
                self.proc.terminate()
        except OSError:
            pass


class HubServer:
    """The multiplexing MCP server: one stdin loop, N lazy backends."""

    def __init__(self, specs: list[BackendSpec], plan: Plan, emit=None) -> None:
        self.specs = specs
        self.plan = plan
        self._out_lock = threading.Lock()
        # ``emit`` is the sink for every outbound JSON line (client-bound). It is
        # injectable so tests can capture traffic without racing stdout; the
        # default writes newline-delimited JSON to stdout under a lock.
        self._emit = emit or self._emit_stdout
        self.backends = {s.id: RuntimeBackend(s, self._emit)
                         for s in specs}

    def _emit_stdout(self, raw_json_line: str) -> None:
        with self._out_lock:
            sys.stdout.write(raw_json_line + "\n")
            sys.stdout.flush()

    def _reply(self, mid, result: dict) -> None:
        self._emit(json.dumps({"jsonrpc": "2.0", "id": mid,
                               "result": result}))

    def _error(self, mid, code: int, message: str) -> None:
        self._emit(json.dumps({"jsonrpc": "2.0", "id": mid,
                               "error": {"code": code, "message": message}}))

    def _tool_error(self, mid, text: str) -> None:
        """A tools/call failure surfaced as an MCP result (isError)."""
        self._reply(mid, {"content": [{"type": "text", "text": text}],
                          "isError": True})

    def _initialize_result(self, params: dict) -> dict:
        pv = (params or {}).get("protocolVersion") or "2024-11-05"
        return {"protocolVersion": pv,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "social-hub", "version": HUB_VERSION}}

    def handle_call(self, msg: dict, mid) -> None:
        name = (msg.get("params") or {}).get("name")
        route = self.plan.routing.get(name) if isinstance(name, str) else None
        if route is None:
            self._error(mid, -32602, f"Unknown tool: {name!r}")
            return
        backend = self.backends[route.backend_id]
        if not backend.ensure_started():
            self._tool_error(
                mid,
                f"[social-hub] backend '{backend.spec.label}' is unavailable: "
                f"{backend.error}. Its other tools stay listed; fix the "
                f"credentials/login for that backend and restart the session.")
            return
        if not backend.forward_call(msg, route.original_name):
            self._tool_error(
                mid,
                f"[social-hub] failed to forward to '{backend.spec.label}': "
                f"{backend.error}.")
        # success path: the response is delivered asynchronously by the pump.

    def dispatch(self, msg: dict) -> None:
        method = msg.get("method")
        mid = msg.get("id")
        if method == "initialize":
            self._reply(mid, self._initialize_result(msg.get("params") or {}))
        elif method == "tools/list":
            self._reply(mid, {"tools": self.plan.tools})
        elif method == "tools/call":
            self.handle_call(msg, mid)
        elif method == "ping":
            self._reply(mid, {})
        elif method == "resources/list":
            self._reply(mid, {"resources": []})
        elif method == "resources/templates/list":
            self._reply(mid, {"resourceTemplates": []})
        elif method == "prompts/list":
            self._reply(mid, {"prompts": []})
        elif method is not None and method.startswith("notifications/"):
            return  # notifications need no reply
        elif mid is not None:
            self._error(mid, -32601, f"Method not found: {method}")

    def run(self) -> int:
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw.startswith("{"):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            self.dispatch(msg)
        return 0


def refresh_backend(spec: BackendSpec, timeout: float = ENUM_TIMEOUT) -> tuple[bool, int, str]:
    """Spawn a backend once, capture initialize + tools/list, write its cache.

    Never overwrites a good committed cache with a failure. Returns
    (ok, n_tools, message).
    """
    try:
        proc = _spawn(spec.cmd, spec.child_env())
    except OSError as exc:
        return False, 0, f"spawn failed: {exc}"
    q: "queue.Queue[str | None]" = queue.Queue()
    threading.Thread(target=_reader, args=(proc, q), daemon=True).start()
    try:
        proc.stdin.write(json.dumps(  # type: ignore[union-attr]
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                        "clientInfo": {"name": "social-hub-refresh",
                                       "version": HUB_VERSION}}}) + "\n")
        proc.stdin.flush()  # type: ignore[union-attr]
        deadline = time.monotonic() + timeout
        init = _drain_until(q, 1, deadline)
        proc.stdin.write(json.dumps(  # type: ignore[union-attr]
            {"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.write(json.dumps(  # type: ignore[union-attr]
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list",
             "params": {}}) + "\n")
        proc.stdin.flush()  # type: ignore[union-attr]
        tools = _drain_until(q, 2, deadline)
    except (TimeoutError, EOFError, OSError) as exc:
        _safe_terminate(proc)
        return False, 0, f"enumerate failed: {exc}"
    _safe_terminate(proc)
    tool_list = (tools.get("result") or {}).get("tools", [])
    payload = {"initialize": init.get("result"), "tools": tools.get("result")}
    path = os.path.join(CACHE_DIR, spec.cache)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return True, len(tool_list), f"cached {len(tool_list)} tools -> {spec.cache}"


def _safe_terminate(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
    except OSError:
        pass


def _cmd_refresh(which: list[str]) -> int:
    specs = default_backends()
    if which:
        specs = [s for s in specs if s.id in which]
    rc = 0
    for spec in specs:
        ok, _n, msg = refresh_backend(spec)
        status = "OK  " if ok else "SKIP"
        print(f"[refresh] {status} {spec.id}: {msg}", file=sys.stderr)
        if not ok and spec.can_enumerate_offline:
            rc = 1  # only a hard failure for backends we expect to enumerate
    return rc


def _cmd_print_plan() -> int:
    specs = default_backends()
    plan = build_plan(specs, CACHE_DIR)
    per_backend: dict[str, int] = {s.id: 0 for s in specs}
    for route in plan.routing.values():
        per_backend[route.backend_id] += 1
    summary = {
        "total_tools": len(plan.tools),
        "per_backend": per_backend,
        "collisions": plan.collisions,
        "renamed": {name: [r.backend_id, r.original_name]
                    for name, r in plan.routing.items() if r.renamed},
        "degraded": plan.degraded,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str]) -> int:
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if argv and argv[0] == "--refresh":
        return _cmd_refresh(argv[1:])
    if argv and argv[0] == "--print-plan":
        return _cmd_print_plan()
    specs = default_backends()
    plan = build_plan(specs, CACHE_DIR)
    return HubServer(specs, plan).run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
