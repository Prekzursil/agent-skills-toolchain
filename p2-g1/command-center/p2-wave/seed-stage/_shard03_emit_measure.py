#!/usr/bin/env python3
"""Emit (if present) then G-1 measure every shard-03 id. Run inside $HOME/p2-g1."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path(__file__).resolve().parents[2])
WAVE = REPO / "command-center" / "p2-wave"
SHARD = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-03.txt")
IDS = [ln.strip().replace("\r", "") for ln in SHARD.read_text(encoding="utf-8").splitlines() if ln.strip()]
LOG = Path.home() / "p2-g1-shard03-emit-measure.log"
MEASURE = WAVE / "_measure_one_delivered.py"
EMIT_NAMES = (
    "write_receipts.py",
    "emit_artifact.py",
    "emit_receipt.py",
    "emit_report.py",
    "emit_census.py",
    "emit.py",
    "emit_migration.py",
)


def run(cmd: list[str], timeout: int = 180) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    rows = []
    ok = fail = 0
    for i, uid in enumerate(IDS, 1):
        pdir = WAVE / "probes" / uid
        emit = next((pdir / n for n in EMIT_NAMES if (pdir / n).is_file()), None)
        line = f"===== {uid} ({i}/{len(IDS)}) ====="
        print(line, flush=True)
        LOG.write_text(LOG.read_text(encoding="utf-8") + line + "\n", encoding="utf-8")
        emit_rc, emit_tail = None, ""
        if emit is not None:
            try:
                emit_rc, emit_out = run([sys.executable, "-B", str(emit)], timeout=180)
            except subprocess.TimeoutExpired:
                emit_rc, emit_out = 124, "TIMEOUT"
            emit_tail = emit_out[-1500:]
            print(f"EMIT {emit.name} rc={emit_rc}", flush=True)
            if emit_tail:
                print(emit_tail[-500:], flush=True)
        try:
            mrc, mout = run([sys.executable, "-B", str(MEASURE), uid], timeout=180)
        except subprocess.TimeoutExpired:
            mrc, mout = 124, "TIMEOUT"
        last = mout.splitlines()[-1] if mout else ""
        success = last == f"SUCCESS:delivered {uid}"
        if success:
            ok += 1
            print(f"OK:{uid}", flush=True)
        else:
            fail += 1
            print(f"FAIL:{uid} {last}", flush=True)
            print("\n".join(mout.splitlines()[-12:]), flush=True)
        rows.append(
            {
                "id": uid,
                "emit": None if emit is None else emit.name,
                "emit_rc": emit_rc,
                "rc": mrc,
                "ok": success,
                "line": last,
                "tail": mout[-1200:],
            }
        )
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(mout[-2000:] + "\n")
            fh.write(f"{'OK' if success else 'FAIL'}:{uid}\n")
        # persist incremental json
        dest = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard03_live.json")
        dest.write_text(json.dumps({"ok": ok, "fail": fail, "n": i, "rows": rows}, indent=2), encoding="utf-8")
    summary = f"SUMMARY attempted={len(IDS)} ok={ok} fail={fail}"
    print(summary, flush=True)
    LOG.open("a", encoding="utf-8").write(summary + "\nMEASURE-DONE\n")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
