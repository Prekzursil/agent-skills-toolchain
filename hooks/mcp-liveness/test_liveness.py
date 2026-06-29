#!/usr/bin/env python3
"""Tests for mcp-liveness. Runs WITHOUT pytest: `python test_liveness.py`.

SAFETY: never disturbs the live basic-memory daemon. The "up" assertion is a
read-only `initialize` against the real :8765 (skipped if it isn't running). All
"down"/"dead-listening" cases use throwaway local sockets/ports. run() tests point
the critical config at a restart_helper that does NOT exist, so attempt_restart is
a no-op (no real process is ever launched or killed).
"""
import json
import socket
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import liveness  # noqa: E402

_FAILS = []


def check(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class _NonMcpHandler(BaseHTTPRequestHandler):
    """Speaks HTTP + valid JSON, but NOT JSON-RPC MCP (dead-but-listening corpse)."""
    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            self.rfile.read(n)
        except Exception:
            pass
        body = b'{"not":"mcp","status":"corpse"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def start_corpse():
    srv = HTTPServer(("127.0.0.1", 0), _NonMcpHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def main():
    cfg = liveness.load_config()

    # 1. Config loads + keystone present.
    check("config has basic-memory critical", "basic-memory" in (cfg.get("critical") or {}))

    # 2. DOWN: nothing listening on a free port -> state 'down'.
    p_down = free_port()
    r = liveness.probe_critical("test-down",
                                {"host": "127.0.0.1", "port": p_down,
                                 "url": f"http://127.0.0.1:{p_down}/mcp"}, cfg)
    check("free port classified as down", r["state"] == "down" and r["tcp"] is False)

    # 3. DEAD-LISTENING: TCP up + HTTP but not MCP -> 'dead-listening'.
    srv, p_corpse = start_corpse()
    try:
        r = liveness.probe_critical("test-corpse",
                                    {"host": "127.0.0.1", "port": p_corpse,
                                     "url": f"http://127.0.0.1:{p_corpse}/mcp"}, cfg)
        check("corpse classified as dead-listening",
              r["state"] == "dead-listening" and r["tcp"] is True and r["mcp_ok"] is False)
    finally:
        srv.shutdown()

    # 4. UP: read-only handshake against the REAL :8765 (skip if not running).
    bm = (cfg.get("critical") or {}).get("basic-memory", {})
    if liveness.tcp_up(bm.get("host", "127.0.0.1"), bm.get("port", 8765), 1.5):
        r = liveness.probe_critical("basic-memory", bm, cfg)
        check("live basic-memory handshake -> up", r["state"] == "up" and r["mcp_ok"] is True)
    else:
        print("SKIP: live basic-memory not running on :8765 (up-case not asserted)")

    # 5. run(): sessionstart with a DOWN keystone -> emits alert + sets restart_attempted.
    #    restart_helper points at a non-existent file so NOTHING is launched/killed.
    state_dir = Path(tempfile.mkdtemp(prefix="liveness-test-"))
    orig_state, orig_cfg_path = liveness.STATE_DIR, liveness.CONFIG_PATH
    fake_cfg = state_dir / "cfg.json"
    fake_cfg.write_text(json.dumps({
        "throttle_seconds": 60, "handshake_timeout": 1.0, "tcp_timeout": 0.5,
        "critical": {"basic-memory": {
            "host": "127.0.0.1", "port": p_down,
            "url": f"http://127.0.0.1:{p_down}/mcp",
            "auto_restart": True, "restart_helper": "does-not-exist.ps1",
            "why": "test"}},
        "reharness": {"registry": "", "auto_restart": False, "restart_hint": "x"},
    }), encoding="utf-8")
    liveness.STATE_DIR = state_dir
    liveness.CONFIG_PATH = fake_cfg
    try:
        import io
        from contextlib import redirect_stdout

        sid = "test-session-1"
        buf = io.StringIO()
        with redirect_stdout(buf):
            liveness.run("sessionstart", {"session_id": sid})
        out1 = buf.getvalue()
        emitted = json.loads(out1) if out1.strip() else {}
        ctx = emitted.get("hookSpecificOutput", {}).get("additionalContext", "")
        check("sessionstart down -> alert emitted",
              "basic-memory" in ctx and "NOT being saved" in ctx)
        st = liveness.load_state(sid)
        check("restart_attempted recorded", st.get("restart_attempted") is True)
        check("last_state recorded as down", st.get("last_state") == "down")

        # 6. pretool THROTTLE: force a recent 'up' check -> probe is skipped (silent).
        sid2 = "test-session-2"
        liveness.save_state(sid2, {"last_check": time.time(), "last_state": "up",
                                   "alerted_down": False, "restart_attempted": False})
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            rc = liveness.run("pretool", {"session_id": sid2})
        check("pretool throttle skips probe when recently up (silent)",
              rc == 0 and buf2.getvalue().strip() == "")

        # 7. pretool alert-dedup: after first down-alert, a second pretool stays silent.
        sid3 = "test-session-3"
        buf3 = io.StringIO()
        with redirect_stdout(buf3):
            liveness.run("pretool", {"session_id": sid3})   # first: alerts
        first = buf3.getvalue()
        buf4 = io.StringIO()
        with redirect_stdout(buf4):
            liveness.run("pretool", {"session_id": sid3})   # second: deduped
        second = buf4.getvalue()
        check("pretool alerts once then dedups",
              first.strip() != "" and second.strip() == "")
    finally:
        liveness.STATE_DIR, liveness.CONFIG_PATH = orig_state, orig_cfg_path

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
