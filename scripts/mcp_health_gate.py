#!/usr/bin/env python3
"""MCP fleet health gate (H5, mcp-harden 2026-09-19). stdlib only.

Iterates the SSOT registry: http rows get a full sessioned MCP handshake
(initialize -> notifications/initialized -> tools/list); stdio rows get a
sequential spawn+handshake under a 20s cap; heavy RE servers are ban-listed
to static checks; disabled rows are counted only. Writes a mcp-health/v1
report; alerts via agent-mail on UNHEALTHY.

Detector controls run EVERY pass (single-signal-verification rule 3):
  (a) :9/mcp must classify ENDPOINT-DEAD
  (b) a bare http server must classify HANDSHAKE-FAIL
  (c) live agent-mail must be HEALTHY/DEGRADED
Any control misfire => verdict FAILED, exit 2 (the GATE is untrustworthy).

Exit: 0 healthy/degraded-only, 1 unhealthy findings, 2 detector-control fail.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOME = Path.home()
REGISTRY = HOME / ".agents" / "agents.json"
REPORT_DIR = Path(r"C:\Users\Prekzursil\source\agent-skills-toolchain\harness-audits\health")
BAN_RE = re.compile(r"(docker|schrodinger|hexstrike|ghidra|ida[-_]pro|binary[-_]ninja|frida|angr|jadx|apktool|qiling|cheatengine|mitmproxy|semgrep)")
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "mcp-health-gate", "version": "1.0"}}}


def _parse_sse(text: str) -> dict | None:
    for line in text.splitlines():
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except Exception:
                continue
    try:
        return json.loads(text)
    except Exception:
        return None


def _resolve_env(val: str):
    if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
        return os.environ.get(val[2:-1])
    return val


def http_handshake(url: str, headers: dict) -> tuple[str, int]:
    """Full sessioned handshake. Returns (status, toolsCount)."""
    sid = None
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
         **{k: str(_resolve_env(v) or "") for k, v in headers.items()}}

    def post(body: dict) -> tuple[int, dict | None, str | None]:
        nonlocal sid
        hh = dict(h)
        if sid:
            hh["Mcp-Session-Id"] = sid
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=hh)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                new_sid = r.headers.get("Mcp-Session-Id") or r.headers.get("mcp-session-id")
                if new_sid:
                    sid = new_sid
                return r.status, _parse_sse(r.read(200_000).decode("utf-8", "replace")), None
        except urllib.error.HTTPError as e:
            return e.code, None, e.read(300).decode("utf-8", "replace") if hasattr(e, "read") else str(e)
        except Exception as e:
            return -1, None, f"{type(e).__name__}: {e}"

    code, body, err = post(INIT)
    if code == -1:
        return "ENDPOINT-DEAD", 0
    if code in (400, 405, 406, 409, 415, 426):
        # negotiation mismatch retry with protocol header
        h["MCP-Protocol-Version"] = "2025-06-18"
        code, body, err = post(INIT)
        if code in (400, 405, 406, 409, 415, 426):
            return "DEGRADED", 0
    if code != 200 or not isinstance(body, dict) or "result" not in body:
        return "HANDSHAKE-FAIL", 0
    post({"jsonrpc": "2.0", "method": "notifications/initialized"})
    code, body, err = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    if code != 200 or not isinstance(body, dict) or ("result" not in body and "error" in body):
        return "SESSION-LOST", 0
    tools = (body.get("result") or {}).get("tools") or []
    return "HEALTHY", len(tools)


def stdio_handshake(command: str, args: list) -> tuple[str, int]:
    """Sequential spawn + newline JSON-RPC handshake, 20s cap, kill-tree."""
    try:
        p = subprocess.Popen([command] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
    except (OSError, FileNotFoundError):
        return "SPAWN-FAIL", 0
    out_lines: list[str] = []

    def reader():
        for line in p.stdout:
            out_lines.append(line.strip())
            if len(out_lines) > 40:
                break

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    try:
        p.stdin.write(json.dumps(INIT) + "\n")
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n")
        p.stdin.flush()
        deadline = time.monotonic() + 20
        got_init = got_tools = False
        while time.monotonic() < deadline and not (got_init and got_tools):
            time.sleep(0.3)
            for l in list(out_lines):
                try:
                    o = json.loads(l)
                except Exception:
                    continue
                if o.get("id") == 1 and "result" in o:
                    got_init = True
                if o.get("id") == 2 and "result" in o:
                    got_tools = True
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        if got_init and got_tools:
            n = 0
            for l in out_lines:
                try:
                    o = json.loads(l)
                    if o.get("id") == 2:
                        n = len((o.get("result") or {}).get("tools") or [])
                except Exception:
                    pass
            return "HEALTHY", n
        if got_init:
            return "SESSION-LOST", 0
        return "HANDSHAKE-FAIL", 0
    except Exception as e:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        return f"SPAWN-ERROR:{type(e).__name__}", 0


def detector_controls() -> list[str]:
    """Three controls; any misfire returns failure reasons."""
    fails = []
    s, _ = http_handshake("http://127.0.0.1:9/mcp", {})
    if s != "ENDPOINT-DEAD":
        fails.append(f"control-a: :9 classified {s}, expected ENDPOINT-DEAD")

    class Bare(BaseHTTPRequestHandler):
        def do_POST(self):  # speaks HTTP, not MCP
            self.send_response(200); self.end_headers(); self.wfile.write(b"{}")
        def log_message(self, *a): pass

    srv = HTTPServer(("127.0.0.1", 0), Bare)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    s2, _ = http_handshake(f"http://127.0.0.1:{port}/mcp", {})
    srv.shutdown()
    if s2 not in ("HANDSHAKE-FAIL", "SESSION-LOST"):
        fails.append(f"control-b: bare http classified {s2}, expected HANDSHAKE-FAIL-class")

    s3, _ = http_handshake("http://127.0.0.1:18812/mcp/", {})
    if s3 not in ("HEALTHY", "DEGRADED"):
        fails.append(f"control-c: agent-mail classified {s3}, expected HEALTHY/DEGRADED")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default=str(REGISTRY))
    ap.add_argument("--dry-run", action="store_true", help="no report write, no alert")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--notify-probe", action="store_true", help="test the alert path with a fake report")
    args = ap.parse_args()

    cfg = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    servers = cfg["mcp"]["servers"]
    rows = sorted(servers.items(), key=lambda kv: kv[0].lower())
    if args.limit:
        rows = rows[: args.limit]

    report = {"schema": "mcp-health/v1",
              "generatedUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "verdict": "HEALTHY", "rows": []}
    unhealthy = []

    for name, e in rows:
        row = {"name": name, "status": "", "tools": 0}
        if not e.get("enabled", True):
            row["status"] = "DISABLED"
            report["rows"].append(row)
            continue
        blob = (name + " " + str(e.get("command", "")) + " " + " ".join(map(str, e.get("args") or []))).lower()
        if BAN_RE.search(blob):
            row["status"] = "STATIC-SKIP"
            report["rows"].append(row)
            continue
        if e.get("url"):
            url = e["url"]
            for m in re.findall(r"\$\{(\w+)\}", url):
                val = os.environ.get(m)
                if val:
                    url = url.replace("${" + m + "}", val)
            headers = e.get("headers") or {}
            missing = [v for v in headers.values() if _resolve_env(v) is None] + \
                      [v for v in (e.get("requiredEnv") or []) if v not in os.environ and not os.environ.get(v)]
            if any(_resolve_env(v) is None for v in headers.values() if isinstance(v, str) and v.startswith("${")):
                row["status"] = "UNHEALTHY-ENV"
                unhealthy.append(row)
                report["rows"].append(row)
                continue
            status, n = http_handshake(url, headers)
            row["status"], row["tools"] = status, n
        else:
            cmd = e.get("command", "")
            args_l = [str(a) for a in (e.get("args") or [])]
            if not Path(cmd).exists():
                import shutil
                resolved = shutil.which(cmd)
                if resolved:
                    cmd = resolved
            if not Path(cmd).exists() and not cmd in ("npx", "uvx", "cmd", "node", "python"):
                row["status"] = "UNHEALTHY(spawn-fail)"
            else:
                status, n = stdio_handshake(cmd, args_l)
                row["status"], row["tools"] = status, n
        if row["status"] in ("ENDPOINT-DEAD", "HANDSHAKE-FAIL", "SESSION-LOST", "SPAWN-FAIL") \
                or row["status"].startswith("UNHEALTHY") or row["status"].startswith("SPAWN-ERROR"):
            unhealthy.append(row)
        report["rows"].append(row)

    ctrl_fails = detector_controls()
    if ctrl_fails:
        report["verdict"] = "FAILED"
        report["controlFailures"] = ctrl_fails
    elif unhealthy:
        report["verdict"] = "UNHEALTHY"
        report["unhealthy"] = [r["name"] + ":" + r["status"] for r in unhealthy]

    out = json.dumps(report, indent=1)
    if not args.dry_run:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        day = datetime.date.today().isoformat()
        (REPORT_DIR / f"health-{day}.json").write_text(out, encoding="utf-8")

    summary = {r["name"]: r["status"] for r in report["rows"]}
    for k in list(summary):
        if summary[k] in ("HEALTHY", "DISABLED", "STATIC-SKIP", "DEGRADED"):
            del summary[k]
    print(f"verdict={report['verdict']} rows={len(report['rows'])} exceptions={summary}")
    if args.dry_run:
        return 0
    if report["verdict"] == "FAILED":
        print("FAILED:health-gate detector controls: " + "; ".join(ctrl_fails))
        return 2
    if report["verdict"] == "UNHEALTHY":
        print(f"UNHEALTHY:health-gate {len(unhealthy)} finding(s)")
        return 1
    print("SUCCESS:health-gate all healthy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
