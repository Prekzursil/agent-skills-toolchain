#!/usr/bin/env python3
"""Remesure unmeasured + previously failing shard-06 IDs."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("AST_INTEGRATE_ROOT") or (Path.home() / "p2-g1"))
MEAS = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"
WIN = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards")
IDS = [ln.strip() for ln in (WIN / "shard-06.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
JSONL = WIN / "_shard06_measure.jsonl"
LOG = WIN / "_shard06_remeasure2.log"


def load_rows() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if JSONL.is_file():
        for line in JSONL.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            out[rec["id"]] = rec
    return out


def one(uid: str) -> dict:
    env = os.environ.copy()
    env["AST_INTEGRATE_ROOT"] = str(ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        p = subprocess.run(
            [sys.executable, "-B", str(MEAS), uid],
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
    ok = last == f"SUCCESS:delivered {uid}"
    return {"id": uid, "status": "ok" if ok else "fail", "rc": rc, "last": last, "tail": text[-2500:]}


def main() -> int:
    rows = load_rows()
    todo = [uid for uid in IDS if uid not in rows or rows[uid].get("status") != "ok"]
    print(f"todo={len(todo)} already_ok={sum(1 for u in IDS if rows.get(u, {}).get('status')=='ok')}", flush=True)
    LOG.write_text("", encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as log, JSONL.open("a", encoding="utf-8") as jl:
        for i, uid in enumerate(todo, 1):
            print(f"===== {uid} =====", flush=True)
            rec = one(uid)
            jl.write(json.dumps(rec, ensure_ascii=False) + "\n")
            jl.flush()
            log.write(f"===== {uid} =====\n{rec['tail']}\n{rec['last']}\n")
            log.flush()
            print(f"PROGRESS i={i}/{len(todo)} {rec['last']}", flush=True)
    # summary from latest per id
    latest = load_rows()
    ok = sum(1 for u in IDS if latest.get(u, {}).get("status") == "ok")
    fail = len(IDS) - ok
    print(f"SUMMARY attempted={len(IDS)} ok={ok} fail={fail}", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
