#!/usr/bin/env python3
"""M2-core gateway skeleton (G-9 Phase A + Phase B pilot slice, wiring_plan milestone).

ONE lazy asyncio process proving the routing layer of gateway-DESIGN.md §4-§5 on
stdlib only (no aiohttp — RAM discipline, zero new deps):

  lifecycle   spawn manually / by first client; refcount = live client connections;
              self-exits after --idle-exit-s (default 1800 = 30 min, design §5);
              NO scheduled task, NO always-on slot. Port-guarded start: binds
              127.0.0.1:31150, falls back 31151-31159, exits non-zero if none free.
  mount       at startup probes every `front` row (TCP + stateful MCP initialize
              capturing mcp-session-id + tools/list), computes desc_sha8 (poison
              baseline vs generated/gateway-desc-baselines.json when present),
              writes ONE mount-receipt audit line per server
              {server, status: mounted|dead|poisoned, desc_sha8, drift}.
  routing     POST /mcp/<name>  -> resolve row -> unknown 404 + audit FAILED unrouted
              -> poisoned 503 + audit FAILED poison -> remote-auth/stdio-lazy 501 +
              audit FAILED not-in-skeleton -> proxy to front + audit SUCCESS/FAILED.
  sessions    fronts are STATEFUL streamable-http (VERIFIED live 2026-09-22: cve
              initialize returns mcp-session-id; tools/list without it => 400
              "No valid session ID provided"). The proxy therefore forwards the
              session header both ways and POOLS front connections per session id
              (session affinity), with proper Content-Length / chunked framing
              (read-until-EOF would hang on keep-alive fronts — that exact mistake
              produced the first 0/33 probe and is retained here as a lesson).
  meta        GET /health, GET /catalog (route table), GET /dead (dead-list at mount);
              POST /mcp/gateway -> mini JSON-RPC MCP server exposing the two design
              meta-tools: gateway.catalog, gateway.dead_list.
  audit       append-only D:/opt/cyberstrike-mcp/audit/gw-YYYYMMDD.jsonl, S6 vocabulary
              SUCCESS/FAILED/INTERRUPTED, req/resp sha8, resp_bytes, flags,
              resolved_model (null in skeleton — model plane deferred), supersedes
              corrections as NEW lines (never rewrite).

SKELETON LIMITS (honest scope, per wiring_plan "NOT in skeleton"): auth resolver is a
stub (remote-auth rows 501), stdio lazy lane absent (501), long-lived server-push
POST-SSE is bounded not streamed (a 30s read deadline ends the body), resolved_model
attribution is null.

Run:  C:/Python314/python.exe gateway/skeleton.py [--idle-exit-s 1800]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import sys

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gateway"))
from gen_routes import BASELINES_OUT, OUT as ROUTES_OUT  # noqa: E402

AUDIT_DIR = Path(r"D:\opt\cyberstrike-mcp\audit")
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}
MAX_BODY = 16 * 1024 * 1024
GATEWAY_NAME = "gateway"  # reserved meta route name
READ_DEADLINE_S = 30


def utcnow_ms() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def sha8_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:8]


class Audit:
    """Append-only JSONL writer — S6 vocabulary, corrections via `supersedes` lines."""

    def __init__(self, audit_dir: Path = AUDIT_DIR):
        audit_dir.mkdir(parents=True, exist_ok=True)
        self.path = audit_dir / f"gw-{time.strftime('%Y%m%d')}.jsonl"

    def line(self, **row) -> None:
        row.setdefault("v", 1)
        row.setdefault("ts", utcnow_ms())
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def mount(
        self,
        server: str,
        status: str,
        desc_sha8: str | None,
        drift: bool,
        note: str = "",
    ) -> None:
        self.line(
            kind="mount",
            server=server,
            status=status,
            desc_sha8=desc_sha8,
            drift=drift,
            note=note,
        )

    def call(
        self,
        *,
        server: str,
        tool: str | None,
        call_id,
        route: dict,
        status: str,
        ms: int,
        flags: list[str],
        req_sha8: str,
        resp_sha8: str | None = None,
        resp_bytes: int | None = None,
        reason: str | None = None,
        supersedes=None,
    ) -> None:
        assert status in ("SUCCESS", "FAILED", "INTERRUPTED"), status  # S6 immutable
        row = dict(
            kind="call",
            server=server,
            tool=tool,
            call_id=call_id,
            route=route,
            status=status,
            ms=ms,
            flags=flags,
            req_sha8=req_sha8,
            resp_sha8=resp_sha8,
            resp_bytes=resp_bytes,
            resolved_model=None,  # structure only — model plane deferred
            client="skeleton",
        )
        if reason:
            row["reason"] = reason
        if supersedes:
            row["supersedes"] = supersedes
        self.line(**row)


# ---------------------------------------------------------------------------
# minimal framed HTTP client (the part urllib got wrong: sessions + framing)
# ---------------------------------------------------------------------------
async def http_exchange(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    method: str,
    path: str,
    host: str,
    body: bytes,
    headers: dict[str, str],
    deadline_s: float = READ_DEADLINE_S,
):
    """Send one request on an OPEN connection; read ONE framed response.

    Returns (status:int, resp_headers:dict, resp_body:bytes) — the connection stays
    usable when the front is keep-alive (caller decides to pool or close).
    """
    lines = [f"{method} {path} HTTP/1.1", f"Host: {host}"]
    for k, v in headers.items():
        lines.append(f"{k}: {v}")
    lines.append(f"Content-Length: {len(body)}")
    writer.write(("\r\n".join(lines) + "\r\n\r\n").encode("latin1") + body)
    await writer.drain()

    # response head
    head_lines = []
    while True:
        ln = await asyncio.wait_for(reader.readline(), timeout=deadline_s)
        if ln in (b"\r\n", b"\n", b""):
            break
        head_lines.append(ln)
    status = int(head_lines[0].decode("latin1").split(" ", 2)[1]) if head_lines else 502
    rheaders: dict[str, str] = {}
    for ln in head_lines[1:]:
        if b":" in ln:
            k, v = ln.split(b":", 1)
            rheaders[k.decode("latin1").strip().lower()] = v.decode("latin1").strip()

    # framed body
    resp_body = b""
    if rheaders.get("transfer-encoding", "").lower() == "chunked":
        while True:
            sz_ln = await asyncio.wait_for(reader.readline(), timeout=deadline_s)
            size = int(sz_ln.strip().split(b";", 1)[0], 16)
            if size == 0:
                await reader.readline()
                break
            resp_body += await asyncio.wait_for(
                reader.readexactly(size), timeout=deadline_s
            )
            await reader.readline()
            if len(resp_body) > MAX_BODY:
                break
    elif (cl := rheaders.get("content-length")) is not None:
        resp_body = await asyncio.wait_for(
            reader.readexactly(int(cl)), timeout=deadline_s
        )
    else:  # read-until-close (Connection: close fronts)
        while len(resp_body) < MAX_BODY:
            chunk = await asyncio.wait_for(reader.read(65536), timeout=deadline_s)
            if not chunk:
                break
            resp_body += chunk
    return status, rheaders, resp_body


def parse_sse_or_json(body: bytes):
    """Streamable-http bodies may be SSE ('event: message\\ndata: {...}') or plain JSON."""
    text = body.decode("utf-8", "replace").strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
    payload = {}
    for ln in text.splitlines():
        if ln.startswith("data:"):
            try:
                payload = json.loads(ln[5:].strip() or "null")
            except json.JSONDecodeError:
                continue
    return payload or {}


class Gateway:
    def __init__(self, routes: dict, idle_exit_s: int):
        self.routes = routes["tool_plane"]
        self.listen = routes["gateway"]["listen"]
        self.fallbacks = routes["gateway"]["fallback_ports"]
        self.idle_exit_s = idle_exit_s
        self.audit = Audit()
        self.mount: dict[str, dict] = {}
        self.conns: set[asyncio.StreamWriter] = set()
        # session affinity: front mcp-session-id -> (front_reader, front_writer, url)
        self.front_pool: dict[str, tuple] = {}
        self.started = time.monotonic()
        self.last_activity = time.monotonic()
        baselines = {}
        if BASELINES_OUT.exists():
            try:
                baselines = json.loads(BASELINES_OUT.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        self.baselines = baselines

    # -- mount-time checks (design §4.5) ------------------------------------
    async def probe_front(self, url: str, timeout_s: float = 5.0):
        """Stateful probe: initialize (capture session) -> tools/list. Returns
        (alive, desc_sha8|None, tools_count|None, error|None)."""
        u = urlsplit(url)
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(u.hostname, u.port or 80), timeout=timeout_s
            )
        except Exception as e:
            return False, None, None, f"{type(e).__name__}: {e}"[:120]
        try:
            init = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "cs-gw-skeleton", "version": "1"},
                    },
                }
            ).encode()
            st, rh, _b = await http_exchange(
                reader,
                writer,
                "POST",
                u.path or "/mcp",
                u.netloc,
                init,
                {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Connection": "keep-alive",
                },
                timeout_s,
            )
            if st != 200:
                return False, None, None, f"initialize HTTP {st}"
            sid = rh.get("mcp-session-id")
            req2 = json.dumps(
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
            ).encode()
            h2 = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Connection": "close",
            }
            if sid:
                h2["Mcp-Session-Id"] = sid
            st2, _rh2, body2 = await http_exchange(
                reader, writer, "POST", u.path or "/mcp", u.netloc, req2, h2, timeout_s
            )
            if st2 != 200:
                return True, None, None, f"tools/list HTTP {st2} (alive, desc unknown)"
            tools = (parse_sse_or_json(body2).get("result") or {}).get("tools", [])
            canon = json.dumps(
                [
                    {"name": t.get("name"), "description": t.get("description", "")}
                    for t in tools
                ],
                sort_keys=True,
            ).encode()
            return True, sha8_bytes(canon), len(tools), None
        except Exception as e:
            return True, None, None, f"{type(e).__name__}: {e}"[:120]  # TCP ok => alive
        finally:
            try:
                writer.close()
            except Exception:
                pass

    async def do_mount(self) -> None:
        for name, row in self.routes.items():
            if row["kind"] != "front":
                self.mount[name] = {
                    "status": "not-front",
                    "desc_sha8": None,
                    "drift": False,
                }
                continue
            alive, desc, tools, err = await self.probe_front(row["url"])
            base = self.baselines.get(name) or {}
            drift = bool(
                alive and desc and base.get("desc_sha8") and base["desc_sha8"] != desc
            )
            status = "poisoned" if drift else ("mounted" if alive else "dead")
            self.mount[name] = {
                "status": status,
                "desc_sha8": desc,
                "drift": drift,
                "tools": tools or 0,
                "baseline": base.get("desc_sha8"),
            }
            self.audit.mount(name, status, desc, drift, note=err or f"{tools} tools")

    # -- meta plane -----------------------------------------------------------
    def catalog(self) -> list[dict]:
        return [
            {
                "name": n,
                "kind": r["kind"],
                "url": r.get("url"),
                "port": r.get("port"),
                "aliases": r["aliases"],
                "band": r["band"],
                "keys": [k.get("env") for k in r["keys"]],
                "note": r["note"],
                "mount_status": self.mount.get(n, {}).get("status"),
            }
            for n, r in self.routes.items()
        ]

    def dead_list(self) -> list[dict]:
        return [
            {
                "server": n,
                "status": m["status"],
                **({"baseline": m["baseline"]} if m.get("baseline") else {}),
            }
            for n, m in sorted(self.mount.items())
            if m["status"] in ("dead", "poisoned")
        ]

    async def handle_meta(self, body: bytes) -> bytes:
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            return http_response(400, "Bad Request", b'{"error":"invalid json"}')
        method, req_id = req.get("method"), req.get("id")
        if method == "initialize":
            return jsonrpc_result(
                req_id,
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "cs-gateway-skeleton", "version": "1"},
                },
            )
        if method == "tools/list":
            return jsonrpc_result(
                req_id,
                {
                    "tools": [
                        {
                            "name": "gateway.catalog",
                            "description": "Full route table: name, kind, resolved url/port, band, "
                            "aliases, mount status (honest labels, G-9)",
                            "inputSchema": {"type": "object", "properties": {}},
                        },
                        {
                            "name": "gateway.dead_list",
                            "description": "Servers dead or poisoned at mount time — check BEFORE "
                            "calling instead of learning by timeout",
                            "inputSchema": {"type": "object", "properties": {}},
                        },
                    ]
                },
            )
        if method == "tools/call":
            tool = (req.get("params") or {}).get("name")
            if tool == "gateway.catalog":
                return jsonrpc_result(
                    req_id,
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(self.catalog(), indent=1),
                            }
                        ]
                    },
                )
            if tool == "gateway.dead_list":
                return jsonrpc_result(
                    req_id,
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(self.dead_list(), indent=1),
                            }
                        ]
                    },
                )
            return jsonrpc_result(
                req_id,
                {
                    "isError": True,
                    "content": [{"type": "text", "text": f"unknown tool {tool}"}],
                },
            )
        return (
            jsonrpc_result(req_id, {})
            if req_id is not None
            else http_response(202, "Accepted", b"", "application/json")
        )

    # -- proxy ------------------------------------------------------------------
    async def proxy(
        self,
        name: str,
        body: bytes,
        client_headers: dict[str, str],
        cwriter: asyncio.StreamWriter,
    ) -> None:
        t0 = time.monotonic()
        row = self.routes.get(name)
        route = (
            {"kind": row["kind"], "port": row.get("port")}
            if row
            else {"kind": "unrouted"}
        )
        flags: list[str] = []
        try:
            rpc = json.loads(body) if body else {}
        except json.JSONDecodeError:
            rpc = {}
        tool = (
            (rpc.get("params") or {}).get("name")
            if rpc.get("method") == "tools/call"
            else None
        )
        call_id = rpc.get("id")
        req_sha8 = sha8_bytes(body)

        def finish(
            status_code: int,
            reason: str,
            payload: bytes,
            audit_status: str,
            audit_reason: str,
            audit_flags: list[str],
            resp_sha8: str | None = None,
        ) -> None:
            cwriter.write(
                http_response(
                    status_code, "OK" if status_code < 400 else "Error", payload
                )
            )
            self.audit.call(
                server=name,
                tool=tool,
                call_id=call_id,
                route=route,
                status=audit_status,
                ms=int((time.monotonic() - t0) * 1000),
                flags=audit_flags,
                req_sha8=req_sha8,
                resp_sha8=resp_sha8,
                resp_bytes=len(payload),
                reason=audit_reason,
            )

        if row is None:
            finish(
                404,
                "unknown route",
                json.dumps(
                    {"error": f"unknown server {name!r} — not in routing table"}
                ).encode(),
                "FAILED",
                "404 unknown route",
                ["unrouted"],
            )
            return
        if row["kind"] != "front":
            finish(
                501,
                "lane deferred",
                json.dumps(
                    {
                        "error": f"{row['kind']} lane is structure-only in the skeleton "
                        f"(M3/M4 deferred); route exists, proxy not implemented"
                    }
                ).encode(),
                "FAILED",
                f"501 {row['kind']} lane deferred",
                ["not-in-skeleton"],
            )
            return
        m = self.mount.get(name) or {}
        if m.get("status") == "poisoned":
            finish(
                503,
                "desc drift",
                json.dumps(
                    {
                        "error": "tool-description drift (poison flag)",
                        "baseline": m.get("baseline"),
                        "observed": m.get("desc_sha8"),
                        "remedy": "gateway.rebaseline --owner (explicit, audited)",
                    }
                ).encode(),
                "FAILED",
                "503 desc drift",
                ["poison"],
            )
            return
        if m.get("status") == "dead":
            flags.append("dead-at-mount")  # informational; still proxied (listing is
            # single-signal-allowed; killing/repair belongs to the watchdog, §4.5)

        u = urlsplit(row["url"])
        sid = next(
            (v for k, v in client_headers.items() if k.lower() == "mcp-session-id"),
            None,
        )
        pooled = self.front_pool.get(sid) if sid else None
        reader, writer = None, None
        try:
            if pooled and not pooled[0].at_eof():
                reader, writer = pooled[0], pooled[1]
                self.front_pool.pop(sid, None)  # take ownership for this exchange
            else:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(u.hostname, u.port or 80), timeout=10
                )
            fwd: dict[str, str] = {
                "Content-Type": client_headers.get("content-type", "application/json"),
                "Accept": client_headers.get(
                    "accept", "application/json, text/event-stream"
                ),
                "Connection": "keep-alive",
            }
            if sid:
                fwd["Mcp-Session-Id"] = sid
            st, rh, resp_body = await http_exchange(
                reader, writer, "POST", u.path or "/mcp", u.netloc, body, fwd
            )
            # pool the front conn under the front-issued session id (affinity)
            new_sid = rh.get("mcp-session-id") or sid
            if new_sid and rh.get("connection", "keep-alive") != "close":
                self.front_pool[new_sid] = (reader, writer)
            else:
                writer.close()
            keep = {k: v for k, v in rh.items() if k not in HOP_BY_HOP}
            ok = 200 <= st < 400
            cwriter.write(
                http_response(
                    st,
                    "OK" if ok else "Error",
                    resp_body,
                    ctype=keep.get("content-type", "application/json"),
                    extra={
                        k.title(): v for k, v in keep.items() if k != "content-type"
                    },
                )
            )
            self.audit.call(
                server=name,
                tool=tool,
                call_id=call_id,
                route=route,
                status="SUCCESS" if ok else "FAILED",
                ms=int((time.monotonic() - t0) * 1000),
                flags=flags,
                req_sha8=req_sha8,
                resp_sha8=sha8_bytes(resp_body),
                resp_bytes=len(resp_body),
                reason=None if ok else f"front status {st}",
            )
        except asyncio.TimeoutError:
            self._drop(reader, writer, sid)
            try:
                cwriter.write(
                    http_response(504, "Gateway Timeout", b'{"error":"front timeout"}')
                )
            except RuntimeError:
                pass
            self.audit.call(
                server=name,
                tool=tool,
                call_id=call_id,
                route=route,
                status="INTERRUPTED",
                ms=int((time.monotonic() - t0) * 1000),
                flags=flags + ["timeout"],
                req_sha8=req_sha8,
                reason="front did not answer within deadline",
            )
        except (ConnectionResetError, RuntimeError, OSError) as e:
            self._drop(reader, writer, sid)
            try:
                cwriter.write(
                    http_response(
                        502,
                        "Bad Gateway",
                        json.dumps(
                            {"error": f"front exchange failed: {type(e).__name__}"}
                        ).encode(),
                    )
                )
            except RuntimeError:
                pass
            self.audit.call(
                server=name,
                tool=tool,
                call_id=call_id,
                route=route,
                status="FAILED",
                ms=int((time.monotonic() - t0) * 1000),
                flags=flags + ["front-error"],
                req_sha8=req_sha8,
                reason=f"{type(e).__name__}: {e}"[:120],
            )

    def _drop(self, reader, writer, sid) -> None:
        if sid:
            self.front_pool.pop(sid, None)
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass

    # -- connection handling -----------------------------------------------------
    async def on_client(
        self, creader: asyncio.StreamReader, cwriter: asyncio.StreamWriter
    ) -> None:
        self.conns.add(cwriter)
        try:
            while True:
                self.last_activity = time.monotonic()
                req = await read_http_request(creader)
                if req is None:
                    break
                method, path, headers, body = req
                if method == "GET" and path in ("/health", "/catalog", "/dead"):
                    if path == "/health":
                        payload = {
                            "status": "ok",
                            "pid": os.getpid(),
                            "uptime_s": int(time.monotonic() - self.started),
                            "routes": len(self.routes),
                            "live_conns": len(self.conns),
                            "front_sessions": len(self.front_pool),
                            "dead": len(self.dead_list()),
                        }
                    elif path == "/catalog":
                        payload = self.catalog()
                    else:
                        payload = self.dead_list()
                    cwriter.write(
                        http_response(200, "OK", json.dumps(payload, indent=1).encode())
                    )
                    await cwriter.drain()
                    break  # Connection: close semantics
                if method == "POST" and path.startswith("/mcp/"):
                    name = path[len("/mcp/") :].strip("/")
                    if name == GATEWAY_NAME:
                        cwriter.write(await self.handle_meta(body))
                        await cwriter.drain()
                    else:
                        await self.proxy(name, body, headers, cwriter)
                    break
                cwriter.write(
                    http_response(404, "Not Found", b'{"error":"unknown path"}')
                )
                await cwriter.drain()
                break
        finally:
            self.conns.discard(cwriter)
            try:
                cwriter.close()
            except RuntimeError:
                pass

    async def idle_watchdog(self, server: asyncio.AbstractServer) -> None:
        while True:
            await asyncio.sleep(10)
            if (
                not self.conns
                and time.monotonic() - self.last_activity > self.idle_exit_s
            ):
                server.close()
                return

    async def run(self) -> int:
        if not ROUTES_OUT.exists():
            print(
                f"FAILED:gw-skeleton routing table missing {ROUTES_OUT} — "
                f"run gateway/gen_routes.py first"
            )
            return 1
        host, port_s = self.listen.split(":")
        ports = [int(port_s)] + list(self.fallbacks)
        server = None
        bound = None
        for p in ports:
            try:
                server = await asyncio.start_server(self.on_client, host, p)
                bound = p
                break
            except OSError:
                continue
        if server is None:
            print(
                f"FAILED:gw-skeleton no free port in {ports} (another owner or "
                f"foreign listener on the whole band)"
            )
            return 1
        await self.do_mount()
        # idle clock starts AFTER mount (mount itself can take ~a minute on this
        # RAM-pressed box; counting it as idle made the watchdog kill a fresh server)
        self.last_activity = time.monotonic()
        dead = len(self.dead_list())
        alive = sum(1 for m in self.mount.values() if m.get("status") == "mounted")
        print(
            f"SUCCESS:gw-skeleton mount on {host}:{bound} — {len(self.routes)} routes, "
            f"mounted {alive}, dead/poisoned {dead}, audit {self.audit.path}"
        )
        watchdog = asyncio.create_task(self.idle_watchdog(server))
        try:
            async with server:
                await server.serve_forever()
        except asyncio.CancelledError:
            pass  # watchdog closed the listener — expected lazy idle-exit path
        finally:
            watchdog.cancel()
            for _r, w in self.front_pool.values():
                try:
                    w.close()
                except Exception:
                    pass
        print(
            f"SUCCESS:gw-skeleton idle-exit after {self.idle_exit_s}s with no clients"
        )
        return 0


# -- shared helpers (request parse / responses) ------------------------------
async def read_http_request(reader: asyncio.StreamReader):
    """Return (method, path, headers-dict, body) or None on early EOF."""
    try:
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=30)
    except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionResetError):
        return None
    lines = head.split(b"\r\n")
    try:
        method, path, _ = lines[0].decode("latin1").split(" ", 2)
    except ValueError:
        return None
    headers: dict[str, str] = {}
    for ln in lines[1:]:
        if b":" in ln:
            k, v = ln.split(b":", 1)
            headers[k.decode("latin1").strip().lower()] = v.decode("latin1").strip()
    body = b""
    if (cl := headers.get("content-length")) is not None:
        try:
            n = min(int(cl), MAX_BODY)
            body = await asyncio.wait_for(reader.readexactly(n), timeout=60)
        except (asyncio.IncompleteReadError, asyncio.TimeoutError):
            return None
    return method.upper(), path, headers, body


def http_response(
    status: int,
    reason: str,
    payload: bytes,
    ctype: str = "application/json",
    extra: dict[str, str] | None = None,
) -> bytes:
    hdrs = [
        f"HTTP/1.1 {status} {reason}",
        f"Content-Type: {ctype}",
        f"Content-Length: {len(payload)}",
        "Connection: close",
    ]
    for k, v in (extra or {}).items():
        hdrs.append(f"{k}: {v}")
    return ("\r\n".join(hdrs) + "\r\n\r\n").encode("latin1") + payload


def jsonrpc_result(req_id, result) -> bytes:
    return http_response(
        200,
        "OK",
        json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}).encode(),
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="CS MCP gateway skeleton (M2-core)")
    ap.add_argument(
        "--idle-exit-s",
        type=int,
        default=1800,
        help="self-exit when no clients and no activity for N s (default 1800)",
    )
    ap.add_argument(
        "--routes",
        type=Path,
        default=ROUTES_OUT,
        help="routing table (generated/gateway-routes.json)",
    )
    args = ap.parse_args(argv)
    routes = json.loads(args.routes.read_text(encoding="utf-8"))
    return asyncio.run(Gateway(routes, args.idle_exit_s).run())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
