#!/usr/bin/env python3
"""cloud-hub — a LAZY, NAME-PRESERVING MCP multiplexer over N cloud backends.

Fronts several cloud-infrastructure MCP servers (RunPod, Azure, Google Cloud,
Kaggle, rclone, Modal, Lightning) behind ONE MCP registration while keeping every
tool under its ORIGINAL name.  ``initialize`` and ``tools/list`` are answered from
committed per-backend caches WITHOUT spawning anything (the RAM win + the
idle-cheap promise).  A ``tools/call`` resolves the owning backend, lazily spawns
ONLY that child (once, kept alive for the session), and forwards the request.  A
backend that cannot spawn or enumerate degrades to a clear per-tool error; the hub
never crashes and never renames a tool unless its name genuinely collides across
backends (then a minimal ``<prefix>_`` is applied and advertised).

Mechanics are identical to the sibling social-hub multiplexer (the proven
single-slot lazy proxy generalized to the multi-child case); only the hub
identity and the fronted backend registry differ.

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

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
# accounts.py is shared with social-hub, so it lives one level up in _shared.
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "_shared"))

import accounts  # noqa: E402
from backends import BackendSpec, default_backends  # noqa: E402
from registry import Plan, build_plan  # noqa: E402

HUB_VERSION = "0.1.0"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "caches")
# The gitignored per-user account store (may hold literal secrets -> never
# committed; see accounts.py + .gitignore).
ACCOUNTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "accounts.json")
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

    def __init__(self, spec: BackendSpec, out_write, account_env=None) -> None:
        self.spec = spec
        self._out = out_write            # callable(str) -> emits a raw JSON line
        # callable() -> dict[str,str] of the active account's env, layered on top
        # of the base child env at spawn time (account creds win). None = no
        # account layer for this backend.
        self._account_env = account_env
        self.proc: subprocess.Popen | None = None
        self.q: "queue.Queue[str | None]" = queue.Queue()
        self.started = False
        self.ok = False
        self.error = ""

    def _spawn_env(self) -> dict[str, str]:
        """Base child env with the ACTIVE account's env layered on top."""
        env = self.spec.child_env()
        if self._account_env is not None:
            try:
                env.update(self._account_env() or {})
            except (KeyError, ValueError, TypeError):
                pass  # a malformed account must never block a spawn
        return env

    def restart(self) -> None:
        """Kill the child and reset state so the NEXT call respawns it.

        Used when the active account changes: the hub kills the child now and the
        new credentials take effect on the next lazy ``tools/call`` spawn.
        """
        self._terminate()
        self.proc = None
        self.started = False
        self.ok = False
        self.error = ""
        self.q = queue.Queue()

    def ensure_started(self) -> bool:
        """Spawn + initialize the child once; return readiness (cached)."""
        if self.started:
            return self.ok and self._alive()
        self.started = True
        try:
            self.proc = _spawn(self.spec.cmd, self._spawn_env())
        except OSError as exc:
            self.error = f"spawn failed: {exc}"
            return False
        threading.Thread(target=_reader, args=(self.proc, self.q),
                         daemon=True).start()
        self._send({"jsonrpc": "2.0", "id": INIT_ID, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05",
                               "capabilities": {},
                               "clientInfo": {"name": "cloud-hub",
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

    def __init__(self, specs: list[BackendSpec], plan: Plan, emit=None,
                 account_store: "accounts.AccountStore | None" = None) -> None:
        self.specs = specs
        self.plan = plan
        self._out_lock = threading.Lock()
        # ``emit`` is the sink for every outbound JSON line (client-bound). It is
        # injectable so tests can capture traffic without racing stdout; the
        # default writes newline-delimited JSON to stdout under a lock.
        self._emit = emit or self._emit_stdout
        # The multi-account store (injectable for tests). Backends without an
        # account policy simply get no account layer.
        self.account_store = account_store or accounts.AccountStore(
            ACCOUNTS_PATH, [s.account for s in specs if s.account])
        self.backends = {s.id: RuntimeBackend(s, self._emit,
                                              self._account_env_for(s))
                         for s in specs}
        self._platform_backend = {s.account.platform: s.id
                                  for s in specs if s.account}
        # Synthetic hub-native account tools (never forwarded to a child) merged
        # into the advertised surface alongside the real backend tools.
        self.account_tools, self.account_routes = self._account_surface(specs)
        self.all_tools = list(plan.tools) + self.account_tools

    def _account_env_for(self, spec: BackendSpec):
        """A callable resolving the active env for an env-mode backend (or None)."""
        if not spec.account or spec.account.mode != "env":
            return None
        platform = spec.account.platform
        return lambda: self.account_store.active_env(platform)

    def _account_surface(self, specs: list[BackendSpec]):
        """Build the synthetic account-tool defs + their routing table."""
        tools: list[dict] = []
        routes: dict[str, tuple[str, str]] = {}
        for spec in specs:
            pol = spec.account
            if not pol:
                continue
            for tool in accounts.account_tool_defs(spec.prefix, pol.platform,
                                                   pol.mode, spec.label):
                tools.append(tool)
                op = tool["name"].rsplit("_account_", 1)[1]
                routes[tool["name"]] = (pol.platform, op)
        return tools, routes

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
                "serverInfo": {"name": "cloud-hub", "version": HUB_VERSION}}

    def handle_call(self, msg: dict, mid) -> None:
        name = (msg.get("params") or {}).get("name")
        if isinstance(name, str) and name in self.account_routes:
            self._handle_account(msg, mid, name)
            return
        route = self.plan.routing.get(name) if isinstance(name, str) else None
        if route is None:
            self._error(mid, -32602, f"Unknown tool: {name!r}")
            return
        backend = self.backends[route.backend_id]
        if not backend.ensure_started():
            self._tool_error(
                mid,
                f"[cloud-hub] backend '{backend.spec.label}' is unavailable: "
                f"{backend.error}. Its other tools stay listed; fix the "
                f"credentials/login for that backend and restart the session.")
            return
        if not backend.forward_call(msg, route.original_name):
            self._tool_error(
                mid,
                f"[cloud-hub] failed to forward to '{backend.spec.label}': "
                f"{backend.error}.")
        # success path: the response is delivered asynchronously by the pump.

    def _handle_account(self, msg: dict, mid, name: str) -> None:
        """Handle a hub-native ``<prefix>_account_*`` tool without forwarding.

        Account management is served by the hub itself (via the AccountStore); a
        ``switch``/``cycle`` additionally kills+respawns the owning backend so the
        new credentials take effect on its next lazy spawn.
        """
        platform, op = self.account_routes[name]
        args = (msg.get("params") or {}).get("arguments") or {}
        result = self.account_store.handle(platform, op, args)
        if result.get("ok") and result.get("respawn"):
            bid = self._platform_backend.get(platform)
            if bid is not None:
                self.backends[bid].restart()
            result["note"] = ("backend killed; the next tools/call respawns it "
                              "with the new active account's credentials")
        self._reply(mid, {
            "content": [{"type": "text",
                         "text": json.dumps(result, ensure_ascii=False, indent=2)}],
            "isError": not result.get("ok", False)})

    def dispatch(self, msg: dict) -> None:
        method = msg.get("method")
        mid = msg.get("id")
        if method == "initialize":
            self._reply(mid, self._initialize_result(msg.get("params") or {}))
        elif method == "tools/list":
            self._reply(mid, {"tools": self.all_tools})
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
                        "clientInfo": {"name": "cloud-hub-refresh",
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
    n_account = sum(len(accounts.ACCOUNT_OPS) for s in specs if s.account)
    summary = {
        "backend_tools": len(plan.tools),
        "account_tools": n_account,
        "total_exposed": len(plan.tools) + n_account,
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
