#!/usr/bin/env bash
set -eu
cd /mnt/c/Users/Prekzursil/source/ast-integrate
export PYTHONPATH="$PWD:$PWD/tools:$PWD/tools/command-center"
OUT=command-center/p2-wave/ovh-monitor/local-sample-remeasure.jsonl
: > "$OUT"
python3 - <<'PY'
import json, subprocess, sys
from pathlib import Path
ids = json.loads(Path("command-center/p2-wave/ovh-monitor/local-sample-ids.json").read_text())["ids"]
out = Path("command-center/p2-wave/ovh-monitor/local-sample-remeasure.jsonl")
ok = fail = 0
for i, uid in enumerate(ids, 1):
    p = subprocess.run(
        [sys.executable, "command-center/p2-wave/_measure_one_delivered.py", uid],
        cwd=".",
        capture_output=True,
        text=True,
        timeout=180,
    )
    lines = ((p.stdout or "") + "\n" + (p.stderr or "")).strip().splitlines()
    last = lines[-1] if lines else f"exit={p.returncode}"
    rec = {"id": uid, "ok": last.startswith("SUCCESS:delivered"), "line": last[:300]}
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    if rec["ok"]:
        ok += 1
        mark = "OK"
    else:
        fail += 1
        mark = "NO"
    print(f"{i}/{len(ids)} {mark} {uid} {last[:120]}", flush=True)
print(f"SAMPLE ok={ok} fail={fail} n={len(ids)}", flush=True)
PY
