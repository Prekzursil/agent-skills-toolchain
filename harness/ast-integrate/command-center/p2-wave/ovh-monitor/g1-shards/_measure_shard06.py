#!/usr/bin/env python3
"""Measure every shard-06 ID on the WSL p2-g1 tree. Writes jsonl + log on Windows."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("AST_INTEGRATE_ROOT") or (Path.home() / "p2-g1"))
MEAS = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"
WIN = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards")
IDS = WIN / "shard-06.txt"
LOG = WIN / "_shard06_measure.log"
JSONL = WIN / "_shard06_measure.jsonl"


def main() -> int:
    ids = [ln.strip() for ln in IDS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    env = os.environ.copy()
    env["AST_INTEGRATE_ROOT"] = str(ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    LOG.write_text("", encoding="utf-8")
    JSONL.write_text("", encoding="utf-8")
    ok = fail = 0
    with LOG.open("a", encoding="utf-8") as log, JSONL.open("a", encoding="utf-8") as jl:
        for i, uid in enumerate(ids, 1):
            log.write(f"===== {uid} =====\n")
            log.flush()
            print(f"===== {uid} =====", flush=True)
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
                text = "TIMEOUT"
                rc = 124
            log.write(text + "\n")
            lines = [ln for ln in text.splitlines() if ln.strip()]
            last = lines[-1] if lines else ""
            success = last == f"SUCCESS:delivered {uid}"
            if success:
                ok += 1
                status = "ok"
            else:
                fail += 1
                status = "fail"
            rec = {"id": uid, "status": status, "rc": rc, "last": last, "tail": text[-2500:]}
            jl.write(json.dumps(rec, ensure_ascii=False) + "\n")
            jl.flush()
            log.write(f"PROGRESS n={i} ok={ok} fail={fail} last={last}\n")
            log.flush()
            print(f"PROGRESS n={i}/{len(ids)} ok={ok} fail={fail} last={last}", flush=True)
        summary = f"SUMMARY attempted={len(ids)} ok={ok} fail={fail}"
        log.write(summary + "\n")
        print(summary, flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
