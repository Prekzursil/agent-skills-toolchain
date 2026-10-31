#!/usr/bin/env python3
"""Check B: re-run every named live probe for the 12 shard units, exit 0 required.
Reviewer-owned driver. Captures per-probe exit code, tail of output, duration.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Prekzursil\p2-g1")
PROBES = ROOT / "command-center" / "p2-wave" / "probes"
UNITS = ["RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111",
         "RES-0112", "RES-0114", "RES-0128", "RES-0144", "RES-0151", "RES-0157"]


def probe_files(uid):
    d = PROBES / uid
    out = []
    for p in sorted(d.iterdir()):
        n = p.name
        if n.startswith("probe") and (n.endswith(".py") or n.endswith(".mjs")):
            out.append(p)
    return out


def main():
    results = {}
    overall_fail = 0
    for uid in UNITS:
        results[uid] = []
        for p in probe_files(uid):
            cmd = ["node", str(p)] if p.suffix == ".mjs" else [sys.executable, "-I", str(p)]
            t0 = time.time()
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=240,
                                   cwd=str(p.parent))
                rc, tail = r.returncode, (r.stdout or "")[-400:] + (("|ERR:" + r.stderr[-200:]) if r.returncode else "")
            except subprocess.TimeoutExpired:
                rc, tail = 124, "TIMEOUT after 240s"
            dt = round(time.time() - t0, 1)
            ok = rc == 0
            if not ok:
                overall_fail += 1
            results[uid].append({"probe": p.name, "exit": rc, "secs": dt,
                                 "pass": ok, "tail": tail.replace("\n", " ")[:300]})
        for row in results[uid]:
            print(f"{uid} {row['probe']}: exit={row['exit']} ({row['secs']}s) {'OK' if row['pass'] else 'RED'}")
    (ROOT / "_reviewer-w4s15-r2" / "probe_results.json").write_text(
        json.dumps(results, indent=1), encoding="utf-8")
    print(f"TOTAL probe failures: {overall_fail}")


if __name__ == "__main__":
    main()
