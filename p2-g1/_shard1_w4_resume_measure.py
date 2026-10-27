#!/usr/bin/env python3
"""Shard1-w4 resume: measure all 12 units, write JSON report."""
import json, subprocess, sys, time
UNITS = ["ADV-0127","ADV-0128","ARC-0001","ARC-0012","ARC-0013","ARC-0015",
         "ARC-0019","ARC-0020","ARC-0021","ARC-0047","ARC-0048","ARC-0054"]
M = "command-center/p2-wave/_measure_one_delivered.py"
out = {}
for uid in UNITS:
    t0 = time.time()
    p = subprocess.run([sys.executable, "-B", M, uid], capture_output=True, text=True,
                       timeout=3200, cwd=".")
    out[uid] = {"rc": p.returncode, "secs": round(time.time()-t0,1),
                "tail": ((p.stdout or "") + (p.stderr or "")).strip()[-600:]}
print(json.dumps({u:{"rc":v["rc"],"secs":v["secs"]} for u,v in out.items()}, indent=1))
open("_shard1_w4_resume_measure.json","w").write(json.dumps(out, indent=1))
