#!/usr/bin/env python3
"""Measure shard-07 IDs inside WSL p2-g1. Writes JSONL on the Windows tree."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path.home() / "p2-g1")
MEAS = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"
IDS = Path(
    "/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/"
    "ovh-monitor/g1-shards/shard-07.txt"
)
OUT = Path(
    "/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/"
    "ovh-monitor/g1-shards/_shard07_g1_measure.jsonl"
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
        text = "TIMEOUT"
        rc = 124
    lines = [ln for ln in text.splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    ok = last == f"SUCCESS:delivered {uid}"
    return {"id": uid, "ok": ok, "rc": rc, "last": last[:300], "tail": text[-2500:]}


def main() -> int:
    ids = [ln.strip() for ln in IDS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    OUT.write_text("", encoding="utf-8")
    ok_n = 0
    with OUT.open("a", encoding="utf-8") as fh:
        for uid in ids:
            rec = one(uid)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if rec["ok"]:
                ok_n += 1
            print(uid, "OK" if rec["ok"] else "FAIL", rec["last"][:160], flush=True)
    print(f"BATCH-DONE n={len(ids)} ok={ok_n} fail={len(ids)-ok_n}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
