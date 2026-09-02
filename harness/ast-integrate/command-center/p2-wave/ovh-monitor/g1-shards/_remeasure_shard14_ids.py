#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("AST_INTEGRATE_ROOT") or str(Path.home() / "p2-g1"))
MEAS = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"
OUT = Path(
    "/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard14_remeasure.jsonl"
)
ids = sys.argv[1:]
ok = fail = 0
for uid in ids:
    env = os.environ.copy()
    env["AST_INTEGRATE_ROOT"] = str(ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        p = subprocess.run(
            [sys.executable, str(MEAS), uid],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=200,
            env=env,
        )
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        rc = p.returncode
    except subprocess.TimeoutExpired:
        text = "TIMEOUT"
        rc = 124
    lines = [ln for ln in text.splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    good = last == f"SUCCESS:delivered {uid}"
    ok += int(good)
    fail += int(not good)
    rec = {"id": uid, "ok": good, "rc": rc, "last": last, "tail": text[-3000:]}
    with OUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(f"{uid} ok={good} {last}", flush=True)
    if not good:
        for ln in text.splitlines()[-10:]:
            print("  ", ln[:220], flush=True)
print(f"SUMMARY ok={ok} fail={fail} attempted={len(ids)}", flush=True)
