#!/usr/bin/env python3
import os, subprocess, sys
from pathlib import Path

REPO = Path("/home/prekzursil/p2-g1")
IDS = [
    "ADV-0062",
    "CNF-0004",
    "CNL-0112",
    "IMP-0110",
    "IMP-0261",
    "IMP-0306",
    "RES-0144",
    "TST-0003",
    "TST-0129",
]
env = os.environ.copy()
env["AST_INTEGRATE_ROOT"] = str(REPO)
env["PYTHONDONTWRITEBYTECODE"] = "1"
out_path = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard03_remeasure_ok.json")
rows = []
for uid in IDS:
    print("=====", uid, "=====", flush=True)
    p = subprocess.run(
        [sys.executable, "-B", str(REPO / "command-center/p2-wave/_measure_one_delivered.py"), uid],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    last = text.splitlines()[-1] if text else ""
    print(last, flush=True)
    rows.append({"id": uid, "rc": p.returncode, "line": last, "ok": last == f"SUCCESS:delivered {uid}", "tail": text[-1500:]})
    out_path.write_text(__import__("json").dumps({"rows": rows}, indent=2), encoding="utf-8")
print("DONE", sum(1 for r in rows if r["ok"]), "/", len(rows), flush=True)
