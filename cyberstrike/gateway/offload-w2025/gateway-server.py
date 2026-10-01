#!/usr/bin/env python3
"""cyberstrike-gateway - the single long-lived process of the MCP estate.

Design: no supervisor, no watchdog, no front-fleet, no per-front ports.
- Backends with Python packages are imported IN-PROCESS (kind=module).
- Backends that are binaries are spawned PER INVOCATION via subprocess.run()
  with a timeout - the OS reaps the child on return, so nothing can orphan.
- Backends that are servers owned elsewhere (msfrpcd, Burp, C2 peers, RE
  bridges) are CLIENTS on their native transport: kind=msgrpc (metasploit
  msgpack-rpc), kind=mcp-sse (Burp's MCP extension), kind=mcp-http /
  kind=mcp-stdio (MCP speaking servers and bridges) - the gateway never owns
  or restarts any of them. Backends with no real transport on this box are
  kind=unavailable with an install_note - never a stub that probes "available".
- Availability is computed lazily from reality (importable / on PATH / real
  protocol round-trip), cached with a short TTL so a server dying mid-session
  flips the row on the next status call instead of lying until restart.

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

# wedge-fix 2026-10-01: under the hidden scheduled-task session, a rich console
# write can block forever while holding the logging handler lock, freezing the
# whole event loop (observed twice during a live assessment). Re-point fd 1/2
# at the log files BEFORE any logging/rich initializes; file writes never
# block and rich degrades to plain output on non-tty. Set GATEWAY_NO_REDIRECT=1
# to keep console output when running manually.
if os.environ.get("GATEWAY_NO_REDIRECT") != "1" and sys.stdout is not None:
    try:
        sys.stdout.flush()
        sys.stderr.flush()
        _here = os.path.dirname(os.path.abspath(__file__))
        os.makedirs(os.path.join(_here, "logs"), exist_ok=True)
        _out = open(os.path.join(_here, "logs", "gateway.out.log"), "ab", buffering=0)
        _err = open(os.path.join(_here, "logs", "gateway.err.log"), "ab", buffering=0)
        os.dup2(_out.fileno(), 1)
        os.dup2(_err.fileno(), 2)
    except OSError:
        pass

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

HERE = os.path.dirname(os.path.abspath(__file__))
SSOT_PATH = os.path.join(HERE, "mcp-ssot.json")
sys.path.insert(0, HERE)  # backends live in ./fronts/ as importable packages

with open(SSOT_PATH, encoding="utf-8") as f:
    SSOT = json.load(f)

backend_env = {b["name"]: b["env"] for b in SSOT.get("backends", []) if b.get("env")}

mcp = FastMCP(
    "cyberstrike-gateway",
    host="127.0.0.1",
    port=SSOT["gateway"]["port"],
    # docker0 bridge of the offload-linux sandbox VM (reachable only via the
    # SSH reverse tunnel) must pass DNS-rebinding protection so PentAGI
    # sandbox workers can call the gateway at 172.17.0.1:31100.
    transport_security=TransportSecuritySettings(
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", "172.17.0.1:*"],
        allowed_origins=[
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://[::1]:*",
            "http://172.17.0.1:*",
        ],
    ),
)

_AVAIL_CACHE: dict[str, tuple[str, str, float]] = {}  # name -> (status, detail, computed_at)
# rpc-dispatch 2026-09-30: availability is TTL-cached, not sticky-per-session.
# A cached "available" older than the TTL is re-probed on touch (same on-touch
# philosophy as worker reaping - no timers). This is what lets a stopped server
# flip its row to unavailable with the real transport error on the next status
# call, which a sticky cache could never show.
_AVAIL_TTL = float(os.environ.get("GATEWAY_AVAIL_TTL", "20"))


def _backend_manifest() -> list[dict]:
    """Original SSOT rows - probers need module/binary/rpc config keys intact
    (the env key survives only as per-backend env-var injection, not a kind)."""
    return list(SSOT["backends"])


def _probe_availability(backend: dict) -> tuple[str, str]:
    """Lazily compute availability from reality. TTL-cached (see _AVAIL_TTL)."""
    name = backend["name"]
    hit = _AVAIL_CACHE.get(name)
    if hit and time.time() - hit[2] < _AVAIL_TTL:
        return hit[0], hit[1]
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
        elif kind == "msgrpc":
            status, detail = _msgrpc_probe(backend)
        elif kind == "mcp-sse":
            status, detail = _mcpsse_probe(backend)
        elif kind == "unavailable":
            status = "unavailable"
            detail = backend.get("install_note") or "reclassified unavailable: no real transport on this box"
        elif kind == "mcp-stdio":
            status, detail = _worker_probe(backend)
        elif kind == "mcp-http":
            status, detail = _mcphttp_probe(backend)
        else:
            status, detail = "misconfigured", f"unknown kind '{kind}'"
    except Exception as exc:  # noqa: BLE001 - import errors are availability data
        status, detail = "unavailable", f"import failed: {exc}"
    _AVAIL_CACHE[name] = (status, detail, time.time())
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
# RSS ceiling per mcp-stdio worker (MB). A worker exceeding it is reaped on the
# next touch and its row reports unavailable with the cap reason - one runaway
# backend (measured: sliver-client ballooning 50GB commit, 2026-09-30 crash)
# must never take the host down. On-touch only; no timers.
WORKER_RSS_CAP_MB = float(os.environ.get("GATEWAY_WORKER_RSS_CAP_MB", "6144"))
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
_RSS_CAPPED: dict[str, str] = {}
_WORKERS_LOCK = threading.Lock()


def _worker_rss_mb(w) -> float:
    """Worker child RSS in MB via psutil (fallback: ctypes GetProcessMemoryInfo)."""
    proc = getattr(w._cm, "process", None) if w._cm is not None else None
    if proc is None or getattr(proc, "pid", None) is None:
        return 0.0
    try:
        import psutil
        return psutil.Process(int(proc.pid)).memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001
        try:
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

            pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
            h = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, int(proc.pid))  # QUERY|READ
            if h:
                ok = ctypes.windll.kernel32.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb)
                ctypes.windll.kernel32.CloseHandle(h)
                if ok:
                    return pmc.WorkingSetSize / (1024 * 1024)
        except Exception:  # noqa: BLE001
            pass
        return 0.0


def _reap_idle_workers():
    """Called ON TOUCH from every gateway invoke: stop workers idle > TTL."""
    now = time.time()
    with _WORKERS_LOCK:
        for name, w in list(_WORKERS.items()):
            if not w._cm:
                continue
            if now - w._last_used > WORKER_IDLE_TTL:
                w.stop()
                _WORKERS.pop(name, None)
                continue
            rss = _worker_rss_mb(w)
            if rss > WORKER_RSS_CAP_MB:
                w.stop()
                _WORKERS.pop(name, None)
                _RSS_CAPPED[name] = f"worker reaped: RSS {rss:.0f}MB exceeded cap {WORKER_RSS_CAP_MB:.0f}MB"


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
    _reap_idle_workers()
    res = _worker_invoke(backend, "__list__", {}, 30.0)
    if res.get("ok"):
        return "available", "mcp-stdio worker (%d tools)" % len(res["tools"])
    capped = _RSS_CAPPED.get(backend["name"])
    if capped:
        return "unavailable", capped
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


def _flatten_error(exc) -> str:
    """Flatten anyio/httpx ExceptionGroup wrapping into its leaf causes.

    The one-shot MCP clients raise nested ExceptionGroups ('unhandled errors
    in a TaskGroup (1 sub-exception)') whose leaf is the actual connect/auth
    error. Probe details and harness_invoke errors must carry the leaf, not
    the wrapper, or the real reason is hidden."""
    subs = getattr(exc, "exceptions", None)
    if subs:
        inner = "; ".join(filter(None, (_flatten_error(s) for s in subs)))
        head = str(exc).split(" (")[0]
        return (head + ": " + inner) if inner else head
    return "%s: %s" % (type(exc).__name__, exc)


def _mcphttp_headers(backend) -> dict:
    """Optional bearer auth for kind=mcp-http backends.

    Backend may declare {"auth": {"mode": "bearer_env", "env": "VARNAME"}} -
    the value is read from the gateway process environment (user env of the
    scheduled task) and sent as 'Authorization: Bearer <value>' on every
    one-shot request. No declaration or unset env -> no header (the backend's
    own 401 then surfaces through the probe/invoke error text).
    linux-vm addition 2026-10-01; decepticon fronts carry no auth and are
    unaffected."""
    a = (backend or {}).get("auth") or {}
    if a.get("mode") == "bearer_env" and a.get("env"):
        v = os.environ.get(a["env"])
        if v:
            return {"Authorization": "Bearer " + v}
    return {}


def _mcphttp_call(url: str, tool: str, args: dict, timeout: float, headers: dict | None = None) -> dict:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def _run():
        async with streamablehttp_client(url, timeout=timeout, headers=dict(headers or {})) as (r, w, _):
            async with ClientSession(r, w) as s:
                await asyncio.wait_for(s.initialize(), timeout)
                if tool == "__list__":
                    tools = await s.list_tools()
                    return {"ok": True, "tools": [t.name for t in tools.tools]}
                res = await asyncio.wait_for(s.call_tool(tool, args or {}), timeout)
                text = res.content[0].text if res.content else ""
                return {"ok": not res.isError, "result": text[:16000]}

    fut = asyncio.run_coroutine_threadsafe(_run(), _http_loop())
    try:
        return fut.result(timeout=timeout + 15)
    except Exception as exc:  # noqa: BLE001 - re-raised with the leaf cause visible
        raise RuntimeError(_flatten_error(exc)) from exc


def _mcphttp_probe(backend) -> tuple[str, str]:
    url = backend.get("url", "")
    try:
        res = _mcphttp_call(url, "__list__", {}, 10.0, _mcphttp_headers(backend))
    except Exception as exc:  # noqa: BLE001 - connection errors are availability data
        return "unavailable", "mcp-http %s failed: %s" % (url, str(exc)[:160])
    return "available", "mcp-http %s (%d tools)" % (url, len(res["tools"]))


# --- kind=mcp-sse: one-shot MCP client against an SSE MCP backend -----------
# Burp Suite's MCP extension (PortSwigger BApp) serves the SSE MCP transport
# at the root path of its configured port (GET / streams `endpoint` events;
# JSON-RPC frames POST to ?sessionId=...). The gateway is a CLIENT: one SSE
# session per invocation, then closed - same one-shot shape as kind=mcp-http,
# different wire transport, so it stays its own function (no generic adapter).
# Probe = real initialize handshake; a TCP-open socket proves nothing.


def _mcpsse_call(url: str, tool: str, args: dict, timeout: float) -> dict:
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async def _run():
        # sse_read_timeout must cover the whole tool call or the stream tears
        # down while we are still waiting for the response event.
        async with sse_client(url, timeout=timeout,
                              sse_read_timeout=max(timeout, 120.0)) as (r, w):
            async with ClientSession(r, w) as s:
                await asyncio.wait_for(s.initialize(), timeout)
                if tool == "__list__":
                    tools = await s.list_tools()
                    return {"ok": True, "tools": [t.name for t in tools.tools]}
                res = await asyncio.wait_for(s.call_tool(tool, args or {}), timeout)
                text = res.content[0].text if res.content else ""
                return {"ok": not res.isError, "result": text[:16000]}

    fut = asyncio.run_coroutine_threadsafe(_run(), _http_loop())
    try:
        return fut.result(timeout=timeout + 20)
    except Exception as exc:  # noqa: BLE001 - re-raised with the leaf cause visible
        raise RuntimeError(_flatten_error(exc)) from exc


def _mcpsse_probe(backend) -> tuple[str, str]:
    url = backend.get("url", "")
    try:
        res = _mcpsse_call(url, "__list__", {}, 10.0)
    except Exception as exc:  # noqa: BLE001 - connection errors are availability data
        return "unavailable", "mcp-sse %s failed: %s" % (url, str(exc)[:160])
    return "available", "mcp-sse %s (%d tools)" % (url, len(res["tools"]))


# --- kind=msgrpc: metasploit msfrpcd msgpack-rpc client ----------------------
# metasploit's native RPC is msgpack-RPC over a raw TCP socket (msfrpcd,
# optionally TLS). The gateway is a pure CLIENT; the operator owns msfrpcd.
# Probe = connect + auth.login + core.version round-trip. Dispatch = route the
# harness_invoke tool name 1:1 onto the msgrpc method map (module.exploit,
# core.version, ...) with the caller's params behind the auth token. One
# connection per round-trip: no persistent socket to manage or orphan.

_MSF_TOKENS: dict[str, str] = {}


class _MsgrpcError(Exception):
    """Real transport/protocol error from the msgrpc wire, surfaced verbatim."""


def _msf_roundtrip(backend: dict, method: str, params: list, timeout: float):
    """One msgpack-rpc request/response over a fresh TCP connection."""
    import msgpack
    rpc = backend.get("rpc", {})
    sock = None
    try:
        sock = socket.create_connection(
            (rpc.get("host", "127.0.0.1"), rpc.get("port", 55553)), timeout=timeout)
        sock.settimeout(timeout)
        if rpc.get("ssl"):
            import ssl
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sock = ctx.wrap_socket(sock)
        msgid = int(time.time() * 1000) & 0x7FFFFFFF
        sock.sendall(msgpack.packb([0, msgid, method, list(params)], use_bin_type=True))
        unpacker = msgpack.Unpacker(raw=False)
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                raise _MsgrpcError("connection closed by msfrpcd before a response frame")
            unpacker.feed(chunk)
            for msg in unpacker:
                if not (isinstance(msg, (list, tuple)) and len(msg) == 4):
                    raise _MsgrpcError("malformed msgpack-rpc frame: %s" % str(msg)[:120])
                typ, mid, result, error = msg
                if typ == 1 and mid == msgid:
                    if error:
                        if isinstance(error, dict):
                            ecls = str(error.get("error_class", ""))
                            emsg = str(error.get("error_message", error))
                            raise _MsgrpcError("%s: %s" % (ecls, emsg) if ecls else emsg)
                        raise _MsgrpcError(str(error))
                    return result
    except OSError as exc:
        raise _MsgrpcError("not listening: %s: %s" % (type(exc).__name__, exc)) from exc
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def _msf_token(backend: dict, timeout: float) -> str:
    name = backend["name"]
    tok = _MSF_TOKENS.get(name)
    if tok:
        return tok
    rpc = backend.get("rpc", {})
    uenv, penv = rpc.get("username_env", ""), rpc.get("password_env", "")
    user, password = os.environ.get(uenv, ""), os.environ.get(penv, "")
    if not user or not password:
        raise _MsgrpcError(
            "credentials not configured (set %s / %s to the msfrpcd -U/-P values)"
            % (uenv, penv))
    res = _msf_roundtrip(backend, "auth.login", [user, password], timeout)
    if not isinstance(res, str) or not res:
        raise _MsgrpcError("auth.login returned no token: %s" % str(res)[:120])
    _MSF_TOKENS[name] = res
    return res


def _msf_invoke(backend: dict, tool: str, params: list, timeout: float) -> dict:
    try:
        token = _msf_token(backend, min(timeout, 15.0))
    except _MsgrpcError as exc:
        return {"ok": False, "error": "msgrpc auth failed: %s" % exc}
    try:
        res = _msf_roundtrip(backend, tool, [token] + list(params), timeout)
    except _MsgrpcError as exc:
        msg = str(exc).lower()
        if "token" in msg or "auth" in msg:
            # msfrpcd restarted under us: drop the stale token, re-login, retry once
            _MSF_TOKENS.pop(backend["name"], None)
            try:
                token = _msf_token(backend, min(timeout, 15.0))
                res = _msf_roundtrip(backend, tool, [token] + list(params), timeout)
            except _MsgrpcError as exc2:
                return {"ok": False, "error": "msgrpc call failed: %s" % exc2}
        else:
            return {"ok": False, "error": "msgrpc call failed: %s" % exc}
    return {"ok": True, "result": res}


def _msgrpc_probe(backend) -> tuple[str, str]:
    rpc = backend.get("rpc", {})
    host, port = rpc.get("host", "127.0.0.1"), rpc.get("port", 55553)
    res = _msf_invoke(backend, "core.version", [], 10.0)
    if res.get("ok"):
        ver = json.dumps(res.get("result"), default=_msf_jsonable)
        return "available", "msgrpc %s:%s auth+core.version round-trip: %s" % (host, port, ver[:160])
    return "unavailable", "msgrpc %s:%s %s" % (host, port, res.get("error", "probe failed")[:200])


def _msf_jsonable(o):  # msgpack may hand back bytes for binary-ish values
    if isinstance(o, (bytes, bytearray)):
        return o.decode("utf-8", "replace")
    return str(o)


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
            "design": "one process; module backends in-process; binary backends per-call and reaped; mcp-stdio backends in a managed worker pool; mcp-http/mcp-sse/msgrpc backends are one-shot clients to operator-owned servers; no kind=rpc exists anymore",
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
    subprocess reaped on return; mcp-stdio -> managed worker; mcp-http /
    mcp-sse -> one-shot MCP client session; msgrpc -> one msgpack-rpc
    round-trip to the operator-owned msfrpcd. Unavailable backends return
    their real transport error and install note - no raw fallback, no silent
    degradation, never a stub.
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
            "install_note": match.get("install_note", ""),
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
            res = _mcphttp_call(match["url"], tool, args, float(args.get("timeout", WORKER_CALL_TIMEOUT)), _mcphttp_headers(match))
            return json.dumps({"backend": backend, "tool": tool, "mode": "mcp-http-one-shot", **res})
        if match["kind"] == "mcp-sse":
            res = _mcpsse_call(match["url"], tool, args, float(args.get("timeout", WORKER_CALL_TIMEOUT)))
            return json.dumps({"backend": backend, "tool": tool, "mode": "mcp-sse-one-shot", **res})
        if match["kind"] == "msgrpc":
            # tool name routes 1:1 onto the msgrpc method map; caller params
            # ride in arguments.params (e.g. {"params": ["windows/x64/meterpreter/reverse_tcp"]})
            params = args.get("params", [])
            if not isinstance(params, list):
                params = [params]
            res = _msf_invoke(match, tool, params, float(args.get("timeout", 60.0)))
            return json.dumps({"backend": backend, "tool": tool, "mode": "msgrpc-client",
                               **res}, default=_msf_jsonable)
        if match["kind"] == "unavailable":
            return json.dumps({"backend": backend, "tool": tool,
                               "error": "reclassified unavailable: no real transport on this box",
                               "install_note": match.get("install_note", "")})
        return json.dumps({"error": f"unhandled kind '{match['kind']}'"})
    except subprocess.TimeoutExpired:
        return json.dumps({"backend": backend, "tool": tool, "error": "timeout - child reaped"})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"backend": backend, "tool": tool, "error": str(exc)})


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
