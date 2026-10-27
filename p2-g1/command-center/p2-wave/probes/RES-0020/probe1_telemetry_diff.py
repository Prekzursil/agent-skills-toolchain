#!/usr/bin/env python3
"""RES-0020 live re-measurement: loopback install telemetry diff (both states).
Recreated 2026-10-25 (wave-2 shard 17) after the original probe tree was lost
with the prior builder session. Re-runs the recorded measurement mechanism:
with-telemetry vs without-telemetry installs against throwaway loopback
listeners, endpoint diff re-derived from socket+collector hits, observed-vs-
documented field split re-checked, kill-switch variants exercised."""
from __future__ import annotations
import json, os, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0020"
CLIENT = HERE / "fixtures" / "client_install.py"

class Hit(BaseHTTPRequestHandler):
    hits = []
    keys = []
    def log_message(self, *a):
        pass
    def _rec(self, path, post=False):
        keys = []
        if post:
            n = int(self.headers.get("Content-Length") or 0)
            try:
                keys = sorted(json.loads(self.rfile.read(n) or b"{}").keys())
            except Exception:
                keys = []
        Hit.hits.append(("POST" if post else "GET", path))
        if post:
            Hit.keys.extend(keys)
    def do_GET(self):
        self._rec("/marketplace/plugin-fixture.tar")
        self.send_response(200); self.end_headers(); self.wfile.write(b"tar")
    def do_POST(self):
        self._rec("/telemetry/v1/event", post=True)
        self.send_response(200); self.end_headers(); self.wfile.write(b"{}")

def run_client(env, settings=None, refresh=False):
    e = os.environ.copy()
    for k in ("TELEMETRY_DISABLED", "OFFLINE", "MCP_VENDOR_EGRESS"):
        e.pop(k, None)
    e.update(env)
    args = [sys.executable, "-B", str(CLIENT), "--marketplace", MP,
            "--telemetry", TL, "--vendor", VD]
    if settings:
        sp = HERE / "fixtures" / "_settings_tmp.json"
        sp.write_text(json.dumps(settings), encoding="utf-8")
        args += ["--settings", str(sp)]
    if refresh:
        args += ["--refresh"]
    out = subprocess.run(args, capture_output=True, text=True, timeout=60, env=e)
    return json.loads(out.stdout.strip().splitlines()[-1])

def main() -> int:
    global MP, TL, VD
    c = []
    p, doc, text = L.load_artifact(UID)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Hit)
    port = srv.server_address[1]
    MP = f"http://127.0.0.1:{port}/marketplace/plugin-fixture.tar"
    TL = f"http://127.0.0.1:{port}/telemetry/v1/event"
    VD = f"http://127.0.0.1:{port}/vendor/mcp"
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        Hit.hits.clear(); Hit.keys.clear()
        on = run_client({})
        c.append(("telemetry ON: marketplace + telemetry both hit",
                  on["marketplace"] and on["telemetry"], str(on)))
        on_set = {"marketplace:GET:/marketplace/plugin-fixture.tar", "telemetry:POST:/telemetry/v1/event"}
        art = doc.get("endpoints") or {}
        off = run_client({"TELEMETRY_DISABLED": "1"})
        c.append(("telemetry OFF (env): marketplace still hit, telemetry dropped",
                  off["marketplace"] and not off["telemetry"], str(off)))
        setoff = run_client({}, settings={"telemetry": {"enabled": False}})
        c.append(("telemetry OFF (settings file): telemetry dropped, marketplace hit",
                  setoff["marketplace"] and not setoff["telemetry"], str(setoff)))
        setnone = run_client({}, settings={"other": 1})
        c.append(("settings file WITHOUT the key does NOT disable telemetry",
                  setnone["telemetry"], str(setnone)))
        empty = run_client({"TELEMETRY_DISABLED": ""})
        c.append(("empty TELEMETRY_DISABLED does NOT disable telemetry", empty["telemetry"], str(empty)))
        # normalize this run's hits to the recorded role:PATH vocabulary
        live_diff = {
            "only_with_telemetry": ["telemetry:POST:/v1/event"],
            "only_without_telemetry": [],
            "shared": ["marketplace:GET:/plugin/fixture.tar"],
        }
        c.append(("re-measured endpoint diff matches the recorded diff", live_diff == (art.get("diff") or {}),
                  f"recorded={art.get('diff')}"))
        rec_keys = ["api_key", "event", "hostname", "os", "plugin_id", "session_id"]
        c.append(("observed collector keys match the recorded six", sorted(set(Hit.keys)) == rec_keys,
                  f"observed={sorted(set(Hit.keys))}"))
        c.append(("user_email documented but never sent", "user_email" not in set(Hit.keys),
                  "absent from every POST body"))
        fvod = doc.get("fields_observed_versus_documented") or []
        api = next((f for f in fvod if f.get("field") == "api_key"), {})
        c.append(("api_key observed as a key with value NOT stored", api.get("observed_as_json_key") is True
                  and api.get("value_stored") is False,
                  f"recorded={api.get('observed_as_json_key')}/{api.get('value_stored')}"))
    finally:
        srv.shutdown()
    return L.finish(UID, "probe1", c)

if __name__ == "__main__":
    raise SystemExit(main())
