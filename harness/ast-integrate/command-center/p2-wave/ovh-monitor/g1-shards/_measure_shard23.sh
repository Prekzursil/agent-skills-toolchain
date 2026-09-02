#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 2
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(os.environ["AST_INTEGRATE_ROOT"])
MEAS = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"
IDS = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-23.txt")
OUT = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard23_measure.jsonl")
ids = [ln.strip() for ln in IDS.read_text(encoding="utf-8").splitlines() if ln.strip()]
only = [x for x in sys.argv[1:] if x]
if only:
    ids = [i for i in ids if i in only]
done = set()
if OUT.is_file() and not only:
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("id") and rec.get("last"):
            done.add(rec["id"])
else:
    OUT.write_text("", encoding="utf-8")

def one(uid: str) -> dict:
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
    ok = last == f"SUCCESS:delivered {uid}"
    return {"id": uid, "ok": ok, "rc": rc, "last": last, "tail": text[-3500:]}

todo = [i for i in ids if i not in done]
print(f"resume done={len(done)} todo={len(todo)} total={len(ids)}", flush=True)
ok = fail = 0
with OUT.open("a", encoding="utf-8") as fh:
    for i, uid in enumerate(todo, 1):
        rec = one(uid)
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        mark = "OK" if rec["ok"] else "FAIL"
        print(f"{i}/{len(todo)} {mark} {uid} {rec['last'][:180]}", flush=True)
        if rec["ok"]:
            ok += 1
        else:
            fail += 1
print(f"DONE ok={ok} fail={fail} attempted={len(todo)}", flush=True)
PY
