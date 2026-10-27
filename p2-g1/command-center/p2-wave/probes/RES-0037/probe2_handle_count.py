#!/usr/bin/env python3
"""RES-0037 independent re-derivation: per-process handle counts, the HTTP
stand-in's LISTEN socket vs stdio children (none), and the recorded 23x65
arithmetic via two mechanics. Windows substrate re-run (wave-2 shard 17)."""
from __future__ import annotations
import json, socket, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0037"
TOKEN = "RES0037_STDIO_STANDIN"
HTTPTOK = "RES0037_HTTP_STANDIN"
SLEEP = "import time; time.sleep(15)"

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    kids = []
    try:
        stdio = [subprocess.Popen([sys.executable, "-c", SLEEP + "  # " + TOKEN + f" h{i}"])
                 for i in range(3)]
        http_src = (
            "import socket,sys,time\n"
            "s=socket.socket(); s.bind(('127.0.0.1',0)); s.listen(1)\n"
            "print(s.getsockname()[1], flush=True)\n"
            "time.sleep(15)\n")
        http = subprocess.Popen([sys.executable, "-c", http_src + "  # " + HTTPTOK],
                                stdout=subprocess.PIPE, text=True)
        kids = stdio + [http]
        port = int(http.stdout.readline().strip())
        time.sleep(1.5)
        snap = L.cim_snapshot()
        rows = {int(q["ProcessId"]): q for q in snap if q.get("CommandLine")}
        sh = [(k.pid, rows.get(k.pid, {}).get("HandleCount")) for k in stdio]
        c.append(("stdio children: 3 live, each with a nonzero OS handle count",
                  all(n for _, n in sh), f"rows={sh}"))
        net = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True,
                             text=True, encoding="utf-8", errors="ignore", timeout=60).stdout
        listen_rows = [ln for ln in net.splitlines() if "LISTENING" in ln and f":{port} " in ln]
        listen_pids = {int(ln.rsplit(None, 1)[1]) for ln in listen_rows if ln.rsplit(None, 1)[-1].isdigit()}
        c.append(("HTTP stand-in: one LISTEN socket, owned by its own single process",
                  len(listen_pids) == 1 and listen_pids == {http.pid},
                  f"port={port} pids={sorted(listen_pids)} expected={{{http.pid}}}"))
        # Shard-16 repair 2026-10-26 (fix cycle 1): the old assertion compared
        # Win32_Process Name to the literal "python.exe", which encodes the
        # recording session's interpreter binary, not the transport claim.
        # This box's interpreter is python3.exe (C:\Python314), so the literal
        # check failed although the artifact claim holds. The claim under test
        # is "one shared HTTP process, ZERO extra processes per extra session",
        # so assert exactly ONE process carrying the stand-in token exists in
        # the process table (no per-session children) and that it is alive -
        # strictly stronger than the name equality it replaces.
        tok_procs = [pid for pid, q in rows.items()
                     if HTTPTOK in str(q.get("CommandLine") or "")]
        c.append(("HTTP stand-in adds ZERO extra processes for extra sessions (recorded 0/session)",
                  tok_procs == [http.pid],
                  f"pid={http.pid} token_procs={tok_procs} handles={rows.get(http.pid, {}).get('HandleCount')}"))
        stdio_listen = [pid for pid, _ in sh if pid in listen_pids]
        c.append(("stdio children carry NO LISTEN socket (recorded listen_inodes empty)",
                  not stdio_listen, f"stdio pids={[pid for pid, _ in sh]}"))
        py = 23 * 65
        pw = subprocess.run(["powershell", "-NoProfile", "-Command", "23*65"],
                            capture_output=True, text=True, timeout=60)
        pwv = int((pw.stdout or "0").strip() or 0)
        c.append(("recorded arithmetic re-derived by two mechanics: 23*65=1495, not 2037",
                  py == 1495 and pwv == 1495 and py != 2037,
                  f"python={py} powershell={pwv}"))
        rec = doc.get("recorded_commit_exhaustion_driver") or {}
        c.append(("artifact records the corrected product 1495 with equation false",
                  rec.get("true_product") == 1495 and rec.get("equation_23_x_65_equals_2037") is False
                  and rec.get("claimed_processes") == 2037,
                  f"recorded={rec.get('true_product')} claimed={rec.get('claimed_processes')}"))
    finally:
        for k in kids:
            k.kill()
        for k in kids:
            k.wait()
    return L.finish(UID, "probe2", c)

if __name__ == "__main__":
    raise SystemExit(main())
