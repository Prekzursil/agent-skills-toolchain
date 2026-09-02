#!/usr/bin/env python3
"""Remeasure previously-failed shard-13 IDs on WSL p2-g1."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(os.environ.get("AST_INTEGRATE_ROOT") or str(Path.home() / "p2-g1"))
MEAS = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"
WIN = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards")
PREV = WIN / "_shard13_measure.jsonl"
OUT = WIN / "_shard13_remeasure.jsonl"
LOG = WIN / "_shard13_remeasure.log"


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


def main() -> None:
    prev = []
    if PREV.is_file():
        for line in PREV.read_text(encoding="utf-8").splitlines():
            if line.strip():
                prev.append(json.loads(line))
    ok_ids = {r["id"] for r in prev if r.get("ok")}
    all_ids = [
        ln.strip()
        for ln in (WIN / "shard-13.txt").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    ids = [u for u in all_ids if u not in ok_ids]
    only = [x for x in sys.argv[1:] if x]
    if only:
        ids = only
    OUT.write_text("", encoding="utf-8")
    LOG.write_text("", encoding="utf-8")
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=3) as ex:
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


if __name__ == "__main__":
    main()
