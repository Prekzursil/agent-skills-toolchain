#!/usr/bin/env python3
"""cyberstrike-gateway - the single long-lived process of the MCP estate.

Design: no supervisor, no watchdog, no front-fleet, no per-front ports.
- Backends with Python packages are imported IN-PROCESS (kind=module).
- Backends that are binaries are spawned PER INVOCATION via subprocess.run()
  with a timeout - the OS reaps the child on return, so nothing can orphan.
- Backends that are servers owned elsewhere (msfrpcd, Burp, C2 peers, RE
  bridges) are RPC CLIENTS - the gateway never owns or restarts them.
- Availability is computed lazily from reality (importable / on PATH / RPC
  reachable), so it cannot drift from a static flag.

Run:  python gateway-server.py   (127.0.0.1:31100, path /mcp)
"""
import importlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

HERE = os.path.dirname(os.path.abspath(__file__))
SSOT_PATH = os.path.join(HERE, "mcp-ssot.json")
sys.path.insert(0, HERE)  # backends live in ./fronts/ as importable packages

with open(SSOT_PATH, encoding="utf-8") as f:
    SSOT = json.load(f)

backend_env = {b["name"]: b["env"] for b in SSOT.get("backends", []) if b.get("env")}

mcp = FastMCP("cyberstrike-gateway", host="127.0.0.1", port=SSOT["gateway"]["port"])

_AVAIL_CACHE: dict[str, tuple[str, str]] = {}  # name -> (status, detail)


def _backend_manifest() -> list[dict]:
    """Original SSOT rows - probers need module/binary/rpc/env keys intact."""
    return list(SSOT["backends"])


def _probe_availability(backend: dict) -> tuple[str, str]:
    """Lazily compute availability from reality. Cached per session."""
    name = backend["name"]
    if name in _AVAIL_CACHE:
        return _AVAIL_CACHE[name]
    kind = backend["kind"]
    try:
        if kind == "module":
            mod = backend.get("module", "")
            if not mod:
                status, detail = "misconfigured", "module key missing"
            else:
                importlib.import_module(mod)
                status, detail = "available", f"in-process module {mod}"
        elif kind == "binary":
            path = shutil.which(backend.get("binary", ""))
            if path:
                status, detail = "available", f"binary at {path}"
            else:
                status, detail = "unavailable", f"'{backend.get('binary')}' not on PATH"
        elif kind == "rpc":
            rpc = backend.get("rpc", {})
            try:
                with socket.create_connection((rpc.get("host", "127.0.0.1"), rpc.get("port", 0)), timeout=0.6):
                    status, detail = "available", f"rpc {rpc.get('host')}:{rpc.get('port')} reachable"
            except OSError:
                status, detail = "unavailable", f"rpc {rpc.get('host')}:{rpc.get('port')} not reachable - start the owning server yourself; the gateway is a client only"
        elif kind == "mcp-stdio":
            status, detail = _worker_probe(backend)
        elif kind == "mcp-http":
            status, detail = _mcphttp_probe(backend)
        elif kind == "env":
            status = "available" if os.environ.get(backend.get("env", "")) else "unavailable"
            detail = f"env {backend.get('env')} {'set' if status == 'available' else 'not set'}"
        else:
            status, detail = "misconfigured", f"unknown kind '{kind}'"
    except Exception as exc:  # noqa: BLE001 - import errors are availability data
        status, detail = "unavailable", f"import failed: {exc}"
    _AVAIL_CACHE[name] = (status, detail)
    return status, detail




# --- kind=mcp-stdio: managed worker pool with hard lifecycle guarantees ---
# Anti-orphan design (estate mandate 2026-09-29, after the 2026-09-03 fleet
# incident): exactly ONE child per backend (single-flight lock, duplicates
# structurally impossible), lazy spawn on first use, idle-TTL reap performed
# ON TOUCH (no timer threads, no watchdog - the gateway does zero work while
# idle), and every child lives in a Windows Job Object with
# JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE so a hard-killed gateway takes its
# children with it. Children can never outlive the gateway.

import asyncio
import concurrent.futures as _cf

WORKER_IDLE_TTL = float(os.environ.get("GATEWAY_WORKER_IDLE_TTL", "300"))
WORKER_CALL_TIMEOUT = float(os.environ.get("GATEWAY_WORKER_CALL_TIMEOUT", "150"))

_JOB_HANDLES: list = []


def _assign_job_object(pid: int) -> None:
    """Put child in a kill-on-close Job Object so it dies with the gateway."""
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.POINTER(wintypes.ULONG)),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                        ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32 = ctypes.windll.kernel32
        job = k32.CreateJobObjectW(None, None)
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
        k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
        PROCESS_SET_QUOTA = 0x0100
        PROCESS_TERMINATE = 0x0001
        h = k32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
        if h:
            k32.AssignProcessToJobObject(job, h)
            k32.CloseHandle(h)
        # job handle intentionally lives until process exit: closing it kills
        # the child, which is exactly what we want at gateway shutdown.
        _JOB_HANDLES.append(job)
    except Exception:  # noqa: BLE001 - containment best-effort, lifecycle not
        pass


class _McpWorker:
    """One managed stdio MCP child per backend name. Thread-safe."""

    def __init__(self, name: str, command):
        self.name = name
        self.command = command
        self._lock = threading.Lock()      # single-flight: one caller at a time
        self._cm = None
        self._session = None
        self._loop = None
        self._thread = None
        self._last_used = 0.0

    def _ensure_loop(self):
        if self._loop is None or not self._thread.is_alive():
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
            self._thread.start()

    def start(self):
        """Spawn child + initialize session. Returns error string ('' on ok)."""
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        async def _spawn():
            import os as _os
            # audit-fix 2026-09-29: children inherit the gateway's FULL environment
            # (plus any per-backend overrides). The SDK's env=None default passes a
            # minimal whitelist, which silently dropped estate secrets (e.g.
            # DEEPSOURCE_API_KEY) from workers. Single-tenant estate: same-trust
            # children, same-trust env.
            benv = backend_env.get(self.name) or {}
            _env = {**_os.environ, **benv}
            params = StdioServerParameters(command=self.command[0], args=self.command[1:], env=_env)
            cm = stdio_client(params)
            r, w = await cm.__aenter__()
            sess = ClientSession(r, w)
            await sess.__aenter__()
            await sess.initialize()
            return cm, sess

        self._ensure_loop()
        fut = asyncio.run_coroutine_threadsafe(_spawn(), self._loop)
        try:
            self._cm, self._session = fut.result(timeout=45)
        except Exception as exc:  # noqa: BLE001
            return f"{type(exc).__name__}: {str(exc)[:200]}"
        # job-object containment on the child process
        proc = getattr(self._cm, "process", None)
        if proc is not None and getattr(proc, "pid", None):
            _assign_job_object(proc.pid)
        return ""

    def call(self, tool, args, timeout):
        async def _call():
            if tool == "__list__":
                tools = await self._session.list_tools()
                return {"ok": True, "tools": [t.name for t in tools.tools]}
            res = await self._session.call_tool(tool, args or {})
            text = res.content[0].text if res.content else ""
            return {"ok": not res.isError, "result": text[:16000]}

        fut = asyncio.run_coroutine_threadsafe(_call(), self._loop)
        try:
            out = fut.result(timeout=timeout)
            self._last_used = time.time()
            return out
        except _cf.TimeoutError:
            fut.cancel()
            self.stop()  # a timed-out session is untrustworthy - reap now
            return {"ok": False, "error": "tool call timed out after %ss; worker reaped" % timeout}

    def stop(self):
        async def _stop():
            try:
                if self._session:
                    await self._session.__aexit__(None, None, None)
            finally:
                if self._cm:
                    await self._cm.__aexit__(None, None, None)
        if self._loop and self._thread and self._thread.is_alive():
            try:
                asyncio.run_coroutine_threadsafe(_stop(), self._loop).result(timeout=10)
            except Exception:  # noqa: BLE001
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._session = None
        self._cm = None
        self._loop = None
        self._thread = None


_WORKERS = {}
_WORKERS_LOCK = threading.Lock()


def _reap_idle_workers():
    """Called ON TOUCH from every gateway invoke: stop workers idle > TTL."""
    now = time.time()
    with _WORKERS_LOCK:
        for name, w in list(_WORKERS.items()):
            if w._cm and now - w._last_used > WORKER_IDLE_TTL:
                w.stop()
                _WORKERS.pop(name, None)


def _worker_invoke(backend, tool, args, timeout):
    _reap_idle_workers()
    name = backend["name"]
    with _WORKERS_LOCK:
        w = _WORKERS.get(name)
        if w is None:
            w = _McpWorker(name, backend["command"])
            _WORKERS[name] = w
    with w._lock:  # single-flight: parallel calls queue, never duplicate children
        if w._cm is None:
            err = w.start()
            if err:
                return {"ok": False, "error": "spawn failed: " + err}
        return w.call(tool, args, timeout)


def _worker_probe(backend):
    res = _worker_invoke(backend, "__list__", {}, 30.0)
    if res.get("ok"):
        return "available", "mcp-stdio worker (%d tools)" % len(res["tools"])
    return "unavailable", "mcp-stdio failed: %s" % res.get("error", res)


# --- kind=mcp-http: one-shot MCP client against a streamable-http backend ----
# audit-fix 2026-09-29: the estate's MCP servers owned elsewhere (decepticon
# fronts) speak streamable-http MCP. The gateway is a CLIENT: per invocation it
# opens one MCP session, calls the tool, and closes - no sessions cached, no
# children spawned, nothing to orphan. Availability probe = real initialize
# handshake (not a bare TCP connect, which cannot tell an MCP server from any
# other socket occupant on the port).

_HTTPLOOP: list = []  # [loop, thread] - one shared background loop for mcp-http


def _http_loop():
    if not _HTTPLOOP or not _HTTPLOOP[1].is_alive():
        loop = asyncio.new_event_loop()
        t = threading.Thread(target=loop.run_forever, daemon=True)
        t.start()
        _HTTPLOOP[:] = [loop, t]
    return _HTTPLOOP[0]


def _mcphttp_call(url: str, tool: str, args: dict, timeout: float) -> dict:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def _run():
        async with streamablehttp_client(url, timeout=timeout) as (r, w, _):
            async with ClientSession(r, w) as s:
                await asyncio.wait_for(s.initialize(), timeout)
                if tool == "__list__":
                    tools = await s.list_tools()
                    return {"ok": True, "tools": [t.name for t in tools.tools]}
                res = await asyncio.wait_for(s.call_tool(tool, args or {}), timeout)
                text = res.content[0].text if res.content else ""
                return {"ok": not res.isError, "result": text[:16000]}

    fut = asyncio.run_coroutine_threadsafe(_run(), _http_loop())
    return fut.result(timeout=timeout + 15)


def _mcphttp_probe(backend) -> tuple[str, str]:
    url = backend.get("url", "")
    try:
        res = _mcphttp_call(url, "__list__", {}, 10.0)
    except Exception as exc:  # noqa: BLE001 - connection errors are availability data
        return "unavailable", "mcp-http %s failed: %s" % (url, str(exc)[:160])
    return "available", "mcp-http %s (%d tools)" % (url, len(res["tools"]))


import atexit


def _shutdown_workers():
    with _WORKERS_LOCK:
        for w in _WORKERS.values():
            w.stop()
        _WORKERS.clear()


atexit.register(_shutdown_workers)


@mcp.tool()
def harness_bridge_status() -> str:
    """Gateway self-status plus lazily-probed availability of every backend."""
    backends = []
    for b in _backend_manifest():
        status, detail = _probe_availability(b)
        backends.append({"name": b["name"], "category": b["category"], "kind": b["kind"],
                         "status": status, "detail": detail, "note": b.get("note", "")})
    return json.dumps({
        "gateway": {
            "name": SSOT["gateway"]["name"],
            "port": SSOT["gateway"]["port"],
            "status": "running",
            "pid": os.getpid(),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "design": "one process; module backends in-process; binary backends per-call and reaped; rpc backends are clients",
        },
        "backends": backends,
    }, indent=2)


@mcp.tool()
def harness_capabilities() -> str:
    """Full revisioned capability manifest (all backends, honest availability)."""
    out = []
    for b in _backend_manifest():
        status, detail = _probe_availability(b)
        out.append({**b, "status": status, "detail": detail})
    return json.dumps({
        "gateway": SSOT["gateway"]["name"],
        "revision": SSOT.get("version"),
        "design": SSOT.get("design"),
        "specialized_total": SSOT["catalogs"]["specialized_total"],
        "legacy_total": SSOT["catalogs"]["legacy_total"],
        "backends": out,
    }, indent=2)


@mcp.tool()
def harness_invoke(backend: str, tool: str, arguments: str = "{}") -> str:
    """Invoke a tool on a backend THROUGH the gateway.

    Dispatch by kind: module -> in-process call; binary -> short-lived
    subprocess reaped on return; rpc -> one client request to the server the
    operator owns. Unavailable backends return their install note - no raw
    fallback, no silent degradation.
    """
    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"bad arguments JSON: {exc}"})

    match = next((b for b in SSOT["backends"] if b["name"] == backend), None)
    if match is None:
        return json.dumps({
            "error": f"unknown backend '{backend}'",
            "known": [b["name"] for b in SSOT["backends"]],
        })

    status, detail = _probe_availability(match)
    if status != "available":
        return json.dumps({
            "error": f"backend '{backend}' unavailable", "status": status,
            "detail": detail, "note": match.get("note", ""),
        })

    try:
        if match["kind"] == "module":
            mod = importlib.import_module(match["module"])
            if not hasattr(mod, "run"):
                return json.dumps({"error": f"module {match['module']} exposes no run(tool, args)"})
            result = mod.run(tool, args)
            return json.dumps({"backend": backend, "tool": tool, "mode": "in-process",
                               "result": result})
        if match["kind"] == "binary":
            proc = subprocess.run(
                [match["binary"], tool] + [str(a) for a in args.get("argv", [])],
                capture_output=True, text=True, timeout=args.get("timeout", 120),
                shell=False, cwd=args.get("cwd") or None,
            )
            return json.dumps({"backend": backend, "tool": tool, "mode": "subprocess-reaped",
                               "returncode": proc.returncode,
                               "stdout": proc.stdout[-8000:], "stderr": proc.stderr[-2000:]})
        if match["kind"] == "mcp-stdio":
            res = _worker_invoke(match, tool, args, args.get("timeout", WORKER_CALL_TIMEOUT))
            return json.dumps({"backend": backend, "tool": tool, "mode": "mcp-stdio-managed-worker", **res})
        if match["kind"] == "mcp-http":
            res = _mcphttp_call(match["url"], tool, args, float(args.get("timeout", WORKER_CALL_TIMEOUT)))
            return json.dumps({"backend": backend, "tool": tool, "mode": "mcp-http-one-shot", **res})
        if match["kind"] == "rpc":
            rpc = match.get("rpc", {})
            return json.dumps({"backend": backend, "tool": tool,
                               "error": "backend reachable over TCP but no protocol adapter wired: "
                                        f"kind=rpc speaks the owning server's native protocol (see note); "
                                        f"the gateway is a client only",
                               "rpc": rpc})
        return json.dumps({"error": f"unhandled kind '{match['kind']}'"})
    except subprocess.TimeoutExpired:
        return json.dumps({"backend": backend, "tool": tool, "error": "timeout - child reaped"})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"backend": backend, "tool": tool, "error": str(exc)})


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
