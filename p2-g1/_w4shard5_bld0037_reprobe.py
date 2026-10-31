import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_w4shard5_bld0037_reprobe.json"
PROBES = [
    ("probe1", "command-center/p2-wave/probes/BLD-0037/probe1_recall_controls.py"),
    ("probe2", "command-center/p2-wave/probes/BLD-0037/probe2_contradiction_anchors.py"),
]
env = dict(os.environ)
env["PYTHONDONTWRITEBYTECODE"] = "1"
results = {}
overall = True
for name, rel in PROBES:
    t0 = time.time()
    try:
        proc = subprocess.run([sys.executable, "-B", rel], cwd=str(REPO),
                              capture_output=True, text=True, timeout=3500, env=env)
        outp = (proc.stdout or "") + (proc.stderr or "")
        entry = {
            "exit": proc.returncode,
            "marker": ("SUCCESS:BLD-0037" in outp),
            "duration_s": round(time.time() - t0, 1),
            "tail": outp.strip().splitlines()[-3:] if outp.strip() else [],
        }
        ok = proc.returncode == 0 and entry["marker"]
    except subprocess.TimeoutExpired:
        entry = {"exit": None, "marker": False, "error": "timeout after 3500s",
                 "duration_s": round(time.time() - t0, 1)}
        ok = False
    results[name] = entry
    overall &= ok
    print(name, "->", "OK" if ok else "FAIL", json.dumps(entry)[:400], flush=True)
results["overall"] = "PASS" if overall else "FAIL"
OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
print("OVERALL:", results["overall"])
