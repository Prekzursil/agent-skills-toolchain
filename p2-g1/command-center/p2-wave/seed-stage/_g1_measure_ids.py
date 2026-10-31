#!/usr/bin/env python3
"""Run _measure_one_delivered.py for every assigned envelope ID."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path.home() / "p2-g1")
MEAS = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"
IDS = ROOT / "command-center" / "p2-wave" / "seed-stage" / "_g1_envelope_ids.txt"
OUT = Path(
    "/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/"
    "ovh-monitor/g1-shards/_envelope_measure.jsonl"
)
WORKERS = int(os.environ.get("G1_MEASURE_WORKERS") or "4")


def load_done() -> dict[str, dict]:
    done: dict[str, dict] = {}
    if OUT.is_file():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            uid = rec.get("id")
            if uid:
                done[uid] = rec
    return done


def append_row(rec: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()


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
    return {
        "id": uid,
        "ok": ok,
        "rc": rc,
        "last": last,
        "tail": text[-2500:],
    }


def main() -> int:
    ids = [ln.strip() for ln in IDS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    done = load_done()
    todo = [uid for uid in ids if uid not in done]
    print(f"resume done={len(done)} todo={len(todo)} total={len(ids)}", flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(one, uid): uid for uid in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            append_row(rec)
            print(
                f"{len(done)+i}/{len(ids)} {rec['id']} ok={rec['ok']} {rec['last'][:120]}",
                flush=True,
            )
    final = load_done()
    rows = [final[uid] for uid in ids if uid in final]
    ok = sum(1 for r in rows if r["ok"])
    print(f"DONE n={len(rows)} ok={ok} fail={len(rows) - ok} missing={len(ids)-len(rows)}")
    return 0 if ok == len(ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())
