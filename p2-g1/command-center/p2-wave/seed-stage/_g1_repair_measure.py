#!/usr/bin/env python3
"""Resumable per-ID G-1 measure for the Claude repair run (27.08.2026).

Usage (WSL): python3 _g1_repair_measure.py <ids-file> <batch-name> [workers]
Appends one row per ID to ovh-monitor/repair-claude/<batch-name>.jsonl (skips
IDs already present) and a line per ID to g1-repair-claude_2026-08-27.log.
Never touches g1-local-full.jsonl. SUCCESS is only the exact last line
'SUCCESS:delivered <ID>'.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path.home() / "p2-g1")
MEAS = ROOT / "command-center" / "p2-wave" / "_measure_one_delivered.py"
WIN_MON = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor")
LOG = WIN_MON / "g1-repair-claude_2026-08-27.log"


def one(uid: str) -> dict:
    env = os.environ.copy()
    env["AST_INTEGRATE_ROOT"] = str(ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        p = subprocess.run(
            [sys.executable, str(MEAS), uid],
            cwd=str(ROOT), capture_output=True, text=True, timeout=300, env=env,
        )
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        rc = p.returncode
    except subprocess.TimeoutExpired:
        text = "TIMEOUT"
        rc = 124
    lines = [ln for ln in text.splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    ok = last == f"SUCCESS:delivered {uid}"
    return {"id": uid, "ok": ok, "rc": rc, "line": last[:400], "tail": text[-1800:]}


def main() -> int:
    ids_file = Path(sys.argv[1])
    name = sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    out = WIN_MON / "repair-claude" / f"{name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    ids = [ln.strip() for ln in ids_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    done: dict[str, dict] = {}
    if out.is_file():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["id"]] = rec
    todo = [u for u in ids if u not in done]
    print(f"REPAIR-MEASURE batch={name} total={len(ids)} done={len(done)} todo={len(todo)} workers={workers}", flush=True)
    ok = sum(1 for r in done.values() if r.get("ok"))
    fail = len(done) - ok
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(one, u): u for u in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            if rec["ok"]:
                ok += 1
            else:
                fail += 1
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            with LOG.open("a", encoding="utf-8") as fh:
                fh.write(f"{name}\t{rec['id']}\tmeasure\t{'OK' if rec['ok'] else 'FAIL'}\t{rec['line'][:160]}\n")
            print(f"{len(done)+i}/{len(ids)} ok={ok} fail={fail} {rec['id']} {rec['line'][:100]}", flush=True)
    print(f"DONE batch={name} n={len(ids)} ok={ok} fail={fail}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
