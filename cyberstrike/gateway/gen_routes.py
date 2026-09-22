#!/usr/bin/env python3
"""M1 gateway routing-table generator (G-9 skeleton, wiring_plan gateway_skeleton_milestone).

Reads D:/opt/cyberstrike-mcp/mcp-ssot.json (v2) and emits the v3 routing table
D:/opt/cyberstrike-mcp/generated/gateway-routes.json — design gateway-DESIGN.md §3.

HERMETIC SPLIT (deliberate): the routes artifact is DETERMINISTIC from the SSOT (no
network), so `--check` is a hermetic drift gate. Live liveness / tool-description
baselines are a separate, network-touching enrichment (`--probe`) written to
generated/gateway-desc-baselines.json — the gateway consumes baselines at mount time
if present; rows carry desc_sha8_baseline: null until probed.

Discipline:
  - duplicate-alias lint: ANY alias (or name) resolving to >1 row is a generation
    ERROR (exit non-zero) — design §3 rule 1, "duplicate aliases are a generation
    error, not a warning".
  - --check regenerates in memory and diffs the on-disk artifact (exit 1 on drift),
    wired into scripts/gen_context.py --check (the estate drift gate).
  - no key VALUES ever: remote-auth rows record env-var NAMES + scheme only (A1).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SSOT = Path(r"D:\opt\cyberstrike-mcp\mcp-ssot.json")
GEN_DIR = Path(r"D:\opt\cyberstrike-mcp\generated")
OUT = GEN_DIR / "gateway-routes.json"
BASELINES_OUT = GEN_DIR / "gateway-desc-baselines.json"

GATEWAY = {"listen": "127.0.0.1:31150", "fallback_ports": [31151, 31152, 31153, 31154,
           31155, 31156, 31157, 31158, 31159]}


def sha8_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:8]


def load_ssot(path: Path = SSOT) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_routes(ssot: dict) -> dict:
    """Deterministic v3 routing table from the SSOT. No network, no env reads."""
    ssot_sha8 = sha8_bytes(SSOT.read_bytes())
    band_of: dict[str, str] = {}
    for band, names in ssot.get("profiles", {}).items():
        for n in names:
            band_of.setdefault(n, band)

    tool_plane: dict[str, dict] = {}

    for name, row in ssot.get("fronts", {}).items():
        tool_plane[name] = {
            "kind": "front",
            "url": row.get("url") or f"http://127.0.0.1:{row.get('port')}/mcp",
            "port": row.get("port"),
            "aliases": list(row.get("aliases") or [name]),
            "band": band_of.get(name, "unassigned"),
            "keys": [],
            "desc_sha8_baseline": None,
            "note": f"supervisor front (profile {band_of.get(name, 'unassigned')})",
        }

    for name, row in ssot.get("general_http_servers", {}).items():
        keys = []
        if row.get("auth") and row.get("env"):
            keys.append({"scheme": row["auth"], "env": row["env"],
                         "ssot": ".agents/local.json:env_keys (name only, never a value)"})
        tool_plane[name] = {
            "kind": "remote-auth",
            "url": row["url"],
            "aliases": [name],
            "band": "general",
            "keys": keys,
            "desc_sha8_baseline": None,
            "note": (row.get("note") or
                     ("keyless remote (auth stub structure-only in skeleton — M3 deferred)"
                      if not keys else "auth via env_keys SSOT (M3 resolver deferred)")),
        }

    for name in ssot.get("catalogs", {}).get("general_stdio_lazy", []):
        if name in tool_plane:
            # collision_resolution: front row wins over same-name stdio-lazy entry
            continue
        tool_plane[name] = {
            "kind": "stdio-lazy",
            "cmd": None,
            "aliases": [name],
            "band": "general",
            "keys": [],
            "desc_sha8_baseline": None,
            "note": "structure only — M4 stdio lazy lane deferred; cmd from client registry at Phase D",
        }

    # NOTE: name collisions between fronts and general catalogs (e.g. angr, frida,
    # mitmproxy exist BOTH as fronts and in stdio-lazy catalog) are resolved
    # front-first: the front row wins and the lazy row is skipped (a live front is
    # strictly better than a spawn). Recorded in collision note, not silently dropped.
    return {
        "version": 3,
        "generated_from": f"mcp-ssot.json@{ssot_sha8}",
        "generated_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gateway": dict(GATEWAY),
        "tool_plane": tool_plane,
        "model_plane_pointer": {
            "spec": "phase2-5/cai/normalized-model-routing.md",
            "note": "structure only — model plane out of skeleton scope",
            "resolved_model_attribution": "deferred (M2 skeleton writes resolved_model: null)",
        },
        "collision_resolution": "front row wins over same-name stdio-lazy catalog entry "
                                "(angr, frida, mitmproxy, ghidra-mcp, ida-pro-mcp class)",
    }


def lint_duplicate_aliases(routes: dict) -> list[str]:
    """Design §3 rule 1: every routable name resolves through EXACTLY one row."""
    owner: dict[str, list[str]] = {}
    for name, row in routes["tool_plane"].items():
        # a row's own name and its alias list may overlap (SSOT aliases include the
        # primary name) — that is NOT a collision; distinct ROWS owning one alias is.
        for alias in {name, *row.get("aliases", [])}:
            owner.setdefault(alias, []).append(name)
    return [f"alias {a!r} -> rows {sorted(rows)}"
            for a, rows in owner.items() if len(rows) > 1]


def check(routes: dict) -> int:
    """Hermetic drift gate: regenerate in memory, diff on-disk artifact."""
    if not OUT.exists():
        print(f"FAILED:gateway-routes missing {OUT} — run gateway/gen_routes.py first")
        return 1
    disk = json.loads(OUT.read_text(encoding="utf-8"))
    drift_fields = [k for k in ("version", "generated_from", "gateway", "tool_plane",
                                "model_plane_pointer", "collision_resolution")
                    if disk.get(k) != routes.get(k)]
    if drift_fields:
        print(f"FAILED:gateway-routes-drift fields differ: {drift_fields}")
        return 1
    print(f"SUCCESS:gateway-routes-check {OUT.name} == ssot regeneration "
          f"({len(routes['tool_plane'])} rows)")
    return 0


def _sock_exchange(sock, method: str, path: str, host: str, body: bytes,
                   headers: dict, timeout_s: float):
    """One framed HTTP/1.1 exchange on an open socket. Returns (status, headers, body)."""
    lines = [f"{method} {path} HTTP/1.1", f"Host: {host}"]
    for k, v in headers.items():
        lines.append(f"{k}: {v}")
    lines.append(f"Content-Length: {len(body)}")
    sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin1") + body)
    sock.settimeout(timeout_s)
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf += chunk
    head, _, rest = buf.partition(b"\r\n\r\n")
    hl = head.decode("latin1", "replace").split("\r\n")
    status = int(hl[0].split(" ", 2)[1]) if hl else 502
    rheaders = {}
    for ln in hl[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            rheaders[k.strip().lower()] = v.strip()
    body_out = rest
    if (cl := rheaders.get("content-length")) is not None:
        while len(body_out) < int(cl):
            chunk = sock.recv(65536)
            if not chunk:
                break
            body_out += chunk
        body_out = body_out[:int(cl)]
    elif rheaders.get("transfer-encoding", "").lower() == "chunked":
        # append until 0-size chunk (bounded)
        while b"0\r\n\r\n" not in body_out[-16:] and len(body_out) < (8 << 20):
            chunk = sock.recv(65536)
            if not chunk:
                break
            body_out += chunk
    else:  # read until close
        while len(body_out) < (8 << 20):
            chunk = sock.recv(65536)
            if not chunk:
                break
            body_out += chunk
    return status, rheaders, body_out


def probe_baselines(routes: dict, timeout_s: float = 15.0) -> dict:
    """Network enrichment (separate artifact): stateful probe per front row.

    15s deadline: cold python fronts on this RAM-pressed box legitimately take >5s
    to answer the FIRST initialize (measured nuclei 31117: >5s cold, 0.2s warm).

    Fronts are STATEFUL streamable-http (VERIFIED live 2026-09-22 on cve 31111:
    initialize returns mcp-session-id; tools/list without it => HTTP 400). The
    probe therefore: initialize -> capture mcp-session-id -> tools/list WITH the
    session header. (The first implementation used urllib without the session —
    0/33 'dead' against a live fleet: a detector failure, not ground truth.)

    Writes generated/gateway-desc-baselines.json:
      {name: {alive, desc_sha8, tools_count, probe_ts, error?}}
    desc_sha8 = sha8 of canonical JSON [{name, description}] — the design §4.5
    poison-check baseline. Stdlib only, sequential (RAM discipline).
    """
    import socket
    from urllib.parse import urlsplit

    out: dict[str, dict] = {}
    for name, row in routes["tool_plane"].items():
        if row["kind"] != "front":
            continue
        rec: dict = {"probe_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        u = urlsplit(row["url"])
        sock = None
        try:
            sock = socket.create_connection((u.hostname, u.port or 80),
                                            timeout=timeout_s)
            init = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                               "params": {"protocolVersion": "2025-03-26",
                                          "capabilities": {},
                                          "clientInfo": {"name": "gw-gen-routes",
                                                         "version": "1"}}}).encode()
            st, rh, _b = _sock_exchange(sock, "POST", u.path or "/mcp", u.netloc, init,
                                        {"Content-Type": "application/json",
                                         "Accept": "application/json, text/event-stream",
                                         "Connection": "keep-alive"}, timeout_s)
            if st != 200:
                rec.update(alive=False, error=f"initialize HTTP {st}")
                out[name] = rec
                continue
            sid = rh.get("mcp-session-id")
            req2 = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).encode()
            h2 = {"Content-Type": "application/json",
                  "Accept": "application/json, text/event-stream",
                  "Connection": "close"}
            if sid:
                h2["Mcp-Session-Id"] = sid
            st2, _rh2, raw = _sock_exchange(sock, "POST", u.path or "/mcp", u.netloc,
                                            req2, h2, timeout_s)
            text = raw.decode("utf-8", "replace").strip()
            if text.startswith("{"):
                payload = json.loads(text)
            else:
                data = next((ln[5:] for ln in text.splitlines()
                             if ln.startswith("data:")), None)
                payload = json.loads(data) if data else {}
            tools = (payload or {}).get("result", {}).get("tools", [])
            canon = json.dumps([{"name": t.get("name"),
                                 "description": t.get("description", "")}
                                for t in tools], sort_keys=True).encode()
            rec.update(alive=True, tools_count=len(tools), desc_sha8=sha8_bytes(canon))
        except Exception as e:  # dead/unreachable front is a FINDING, not a crash
            rec.update(alive=False, error=f"{type(e).__name__}: {str(e)[:120]}")
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
        out[name] = rec
    return out


def main(argv: list[str]) -> int:
    if not SSOT.exists():
        print(f"FAILED:gen-routes ssot missing {SSOT}")
        return 1
    ssot = load_ssot()
    routes = build_routes(ssot)
    dups = lint_duplicate_aliases(routes)
    if dups:
        for d in dups:
            print(f"FAILED:gen-routes duplicate-alias {d}")
        return 1

    if "--check" in argv:
        return check(routes)

    if "--probe" in argv:
        baselines = probe_baselines(routes)
        GEN_DIR.mkdir(parents=True, exist_ok=True)
        BASELINES_OUT.write_text(json.dumps(baselines, indent=1), encoding="utf-8")
        alive = sum(1 for r in baselines.values() if r.get("alive"))
        print(f"SUCCESS:gen-routes-probe {alive}/{len(baselines)} fronts alive -> {BASELINES_OUT}")

    GEN_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(routes, indent=1), encoding="utf-8")
    n = len(routes["tool_plane"])
    print(f"SUCCESS:gen-routes wrote {OUT} ({n} rows, from {routes['generated_from']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
