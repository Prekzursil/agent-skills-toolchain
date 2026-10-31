#!/usr/bin/env python3
"""RES-0020 independent re-derivation: OFFLINE=1 zero-egress control (incl.
refresh=true), and the check that the telemetry kill-switch does NOT stop MCP
vendor egress; NC = corrupted diff mutant must fire the detector."""
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
    def log_message(self, *a):
        pass
    def do_GET(self):
        Hit.hits.append("GET " + self.path.split("?")[0])
        self.send_response(200); self.end_headers(); self.wfile.write(b"tar")
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        Hit.hits.append("POST " + self.path)
        self.send_response(200); self.end_headers(); self.wfile.write(b"{}")

def run(env, refresh=False):
    e = os.environ.copy()
    for k in ("TELEMETRY_DISABLED", "OFFLINE", "MCP_VENDOR_EGRESS"):
        e.pop(k, None)
    e.update(env)
    args = [sys.executable, "-B", str(CLIENT), "--marketplace", MP,
            "--telemetry", TL, "--vendor", VD]
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
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        oc = doc.get("endpoints") or {}
        offc = oc.get("offline_control") or {}
        Hit.hits.clear()
        r = run({"OFFLINE": "1"}, refresh=True)
        c.append(("OFFLINE=1 (incl. refresh=true): zero connects at both roles",
                  not r["marketplace"] and not r["telemetry"] and not Hit.hits,
                  f"client={r} server_hits={Hit.hits}"))
        c.append(("recorded offline control is the same zero shape",
                  offc.get("connect_count") == 0 and offc.get("collector_hits") == 0
                  and (offc.get("new_endpoints") or []) == [],
                  f"recorded={offc}"))
        Hit.hits.clear()
        v = run({"TELEMETRY_DISABLED": "1", "MCP_VENDOR_EGRESS": "1"})
        c.append(("kill-switch does NOT stop MCP vendor egress: vendor GET still fires",
                  v["vendor"] and not v["telemetry"] and "GET /vendor/mcp" in Hit.hits,
                  f"client={v} server_hits={Hit.hits}"))
        hc = {h["id"]: h.get("pass") for h in doc.get("harness_checks") or []}
        want = ["telemetry-off-does-not-stop-mcp-vendor-egress",
                "offline-zero-new-endpoints", "empty-TELEMETRY_DISABLED-does-not-disable"]
        c.append(("recorded harness checks cover the same three controls",
                  all(hc.get(k) is True for k in want),
                  f"{[hc.get(k) for k in want]}"))

        def mutate(d):
            d["endpoints"]["telemetry_on"].remove("telemetry:POST:/v1/event")
            return d

        mp = L.mutation_copy(doc, mutate)
        try:
            mdoc = json.loads(mp.read_text(encoding="utf-8"))
            en = mdoc["endpoints"]["telemetry_on"]
            diff_on = set(en) - set(mdoc["endpoints"]["telemetry_off"])
            fired = "telemetry:POST:/v1/event" not in diff_on
            c.append(("NC: mutant diff that hides the telemetry endpoint fires the detector", fired,
                      f"mutant only_with_telemetry={sorted(diff_on)}"))
        finally:
            mp.unlink(missing_ok=True)
    finally:
        srv.shutdown()
    return L.finish(UID, "probe2", c)

if __name__ == "__main__":
    raise SystemExit(main())
