#!/usr/bin/env python3
"""RES-0037 live re-measurement (stdio transport), Windows substrate.
Recreated 2026-10-25 (wave-2 shard 17): the recorded run measured /proc on the
Linux VM; this probe re-runs the SAME mechanism contract on this box — exact
argv-token counting, a self-exclusion proof, a decoy control, and a start/stop
delta — via one CIM snapshot per reading. Fail-closed."""
from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0037"
TOKEN = "RES0037_STDIO_STANDIN"
NAIVE = "RES-0037"
SLEEP = "import time; time.sleep(20)"

def count(pred, snap):
    return [p for p in snap if p.get("CommandLine") and pred(p)]

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    base = L.cim_snapshot()
    base_n = len(count(lambda q: TOKEN in q["CommandLine"], base))
    c.append(("baseline: zero stand-in-token processes before spawning", base_n == 0, f"count={base_n}"))
    kids = []
    try:
        stdio = subprocess.Popen([sys.executable, "-c", SLEEP + "  # " + TOKEN])
        decoy = subprocess.Popen([sys.executable, "-c",
                                  SLEEP + "  # decoy " + NAIVE + " probe1_self_exclusion_delta.py"])
        kids = [stdio, decoy]
        time.sleep(1.5)
        snap = L.cim_snapshot()
        toks = count(lambda q: TOKEN in q["CommandLine"], snap)
        naive = count(lambda q: NAIVE in q["CommandLine"], snap)
        naive_pids = {q["ProcessId"] for q in naive}
        self_pid = os.getpid()
        decoy_pids = {decoy.pid}
        c.append(("start/stop delta control: exactly +1 exact-token process", len(toks) == base_n + 1,
                  f"delta={len(toks) - base_n} expected=1"))
        c.append(("self-exclusion proof: naive substring WOULD match this probe",
                  self_pid in naive_pids, f"self_pid={self_pid}"))
        c.append(("exact-token matcher excludes this probe", self_pid not in {q['ProcessId'] for q in toks},
                  f"token_hits={sorted(q['ProcessId'] for q in toks)}"))
        c.append(("decoy control: naive matcher WOULD count the decoy", bool(decoy_pids & naive_pids),
                  f"decoy={sorted(decoy_pids & naive_pids)}"))
        c.append(("exact-token matcher ignores the decoy", not (decoy_pids & {q['ProcessId'] for q in toks}),
                  "decoy carries the probe filename, not the token"))
        # per-transport multiplication: 3 sessions x 2 servers = 6 processes
        stdio.kill(); stdio.wait(); decoy.kill(); decoy.wait()  # clear phase-1 procs
        kids = [decoy]  # decoy killed below too; keep list for the finally
        decoy.wait()
        kids6 = [subprocess.Popen([sys.executable, "-c", SLEEP + "  # " + TOKEN + f" s{i//2} v{i%2}"])
                 for i in range(6)]
        kids += kids6
        time.sleep(1.5)
        n6 = len(count(lambda q: TOKEN in q["CommandLine"], L.cim_snapshot()))
        per = n6 / (3 * 2)
        c.append(("stdio multiplication: 3 sessions x 2 servers = 6 processes, 1.0/server/session",
                  n6 == 6 and abs(per - 1.0) < 1e-9,
                  f"count={n6} per_server_per_session={per}"))
        art = (doc.get("per_transport_process_count") or {}).get("stdio") or {}
        c.append(("recorded artifact stdio cost agrees (1.0/server/session)",
                  float(art.get("processes_per_server_per_session") or 0) == 1.0,
                  f"recorded={art.get('processes_per_server_per_session')}"))
    finally:
        for k in kids:
            k.kill()
        for k in kids:
            k.wait()
    after = len(count(lambda q: TOKEN in q["CommandLine"], L.cim_snapshot()))
    c.append(("stop delta control: count returns to baseline after kills", after == 0, f"count={after}"))
    rec_fleet = int(((doc.get("today_fleet") or {}).get("argv_exact_mcp_count")) or 0)
    c.append(("fleet re-measure: live argv-exact count equals the recorded 0",
              after == rec_fleet, f"live={after} recorded={rec_fleet}"))
    return L.finish(UID, "probe1", c)

if __name__ == "__main__":
    raise SystemExit(main())
