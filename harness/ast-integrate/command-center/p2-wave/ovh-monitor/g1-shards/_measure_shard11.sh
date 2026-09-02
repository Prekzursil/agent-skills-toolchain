#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 2
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(os.environ["AST_INTEGRATE_ROOT"])
MEAS = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"
IDS = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-11.txt")
OUT = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard11_measure.jsonl")
LOG = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard11_measure.log")
ids = [ln.strip() for ln in IDS.read_text(encoding="utf-8").splitlines() if ln.strip()]
only = os.environ.get("ONLY_IDS", "").strip()
if only:
    want = set(only.split())
    ids = [u for u in ids if u in want]
OUT.write_text("", encoding="utf-8")
LOG.write_text("", encoding="utf-8")

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
    rec = {"id": uid, "ok": ok, "rc": rc, "last": last, "tail": text[-3500:]}
    return rec

ok = fail = 0
workers = int(os.environ.get("G1_WORKERS", "3"))
with ThreadPoolExecutor(max_workers=workers) as ex:
    futs = {ex.submit(one, uid): uid for uid in ids}
    for i, fut in enumerate(as_completed(futs), 1):
        rec = fut.result()
        if rec["ok"]:
            ok += 1
        else:
            fail += 1
        with OUT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"==== {rec['id']} ok={rec['ok']} {rec['last']}\n")
            fh.write(rec["tail"] + "\n")
        print(f"[{i}/{len(ids)}] {rec['id']} ok={rec['ok']} {rec['last']}", flush=True)
print(f"SUMMARY attempted={len(ids)} ok={ok} fail={fail}", flush=True)
PY
