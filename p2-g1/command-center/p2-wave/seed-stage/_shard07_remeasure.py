#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/prekzursil/p2-g1")
MEAS = ROOT / "command-center/p2-wave/_measure_one_delivered.py"
PREV = Path(
    "/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard07_g1_measure.jsonl"
)
OUT = Path(
    "/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard07_g1_remeasure.jsonl"
)
ALL = Path(
    "/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-07.txt"
)


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
            timeout=240,
            env=env,
        )
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        rc = p.returncode
    except subprocess.TimeoutExpired:
        text, rc = "TIMEOUT", 124
    lines = [ln for ln in text.splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    return {"id": uid, "ok": last == f"SUCCESS:delivered {uid}", "rc": rc, "last": last[:300], "tail": text[-1800:]}


def main() -> None:
    done_ok = set()
    if PREV.is_file():
        for line in PREV.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("ok"):
                done_ok.add(rec["id"])
    ids = [ln.strip() for ln in ALL.read_text(encoding="utf-8").splitlines() if ln.strip()]
    todo = [u for u in ids if u not in done_ok]
    print("todo", len(todo), "already_ok", len(done_ok), flush=True)
    OUT.write_text("", encoding="utf-8")
    ok_n = 0
    with OUT.open("a", encoding="utf-8") as fh:
        for uid in todo:
            rec = one(uid)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            ok_n += int(rec["ok"])
            print(uid, "OK" if rec["ok"] else "FAIL", rec["last"][:160], flush=True)
    print(f"REMEASURE-DONE new_ok={ok_n} fail={len(todo)-ok_n}", flush=True)


if __name__ == "__main__":
    main()
