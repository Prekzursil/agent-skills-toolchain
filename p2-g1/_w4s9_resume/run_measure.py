#!/usr/bin/env python3
import json, subprocess, sys, time
UNITS = ["IMP-0202","IMP-0204","IMP-0207","IMP-0219","IMP-0224","IMP-0228",
         "IMP-0229","IMP-0230","IMP-0261","IMP-0264","IMP-0269","IMP-0270"]
M = r"C:\Users\Prekzursil\p2-g1\command-center\p2-wave\_measure_one_delivered.py"
out = {}
for uid in UNITS:
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-B", M, uid], capture_output=True,
                           text=True, timeout=2700, cwd=r"C:\Users\Prekzursil\p2-g1")
        rc, text = p.returncode, ((p.stdout or "") + (p.stderr or ""))
    except subprocess.TimeoutExpired:
        rc, text = 124, "TIMEOUT"
    out[uid] = {"rc": rc, "secs": round(time.time() - t0, 1), "tail": text.strip()[-700:]}
    print(f"{uid} rc={rc} secs={out[uid]['secs']}", flush=True)
open(r"C:\Users\Prekzursil\p2-g1\_w4s9_resume\measure_baseline.json", "w").write(json.dumps(out, indent=1))
print(json.dumps({u: v["rc"] for u, v in out.items()}, indent=0))
