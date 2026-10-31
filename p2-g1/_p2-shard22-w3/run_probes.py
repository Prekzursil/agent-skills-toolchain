#!/usr/bin/env python3
"""Run a unit's named probes, capture raw outputs + exit codes into PROBE-RUNS.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROBES = REPO / "command-center" / "p2-wave" / "probes"


def main() -> int:
    uid = sys.argv[1]
    pdir = PROBES / uid
    probe_files = sorted(pdir.glob("probe1*.py")) + sorted(pdir.glob("probe2*.py"))
    named = [p for p in probe_files if p.name not in {"probe1.py", "probe2.py"}] or probe_files
    if not named:
        print(f"FAILED:run {uid} no-probes")
        return 2
    runs = []
    all_ok = True
    for pf in named:
        cmd = f"PYTHONDONTWRITEBYTECODE=1 python -B {pf.as_posix().replace(REPO.as_posix(), 'command-center/..', 1) if False else pf.relative_to(REPO).as_posix()}"
        command = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {pf.relative_to(REPO).as_posix()}"
        t0 = time.time()
        p = subprocess.run(
            [sys.executable, "-B", str(pf)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=2700,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        raw = ((p.stdout or "") + (p.stderr or "")).strip()
        runs.append(
            {
                "id": pf.stem.split("_")[0],
                "command": command,
                "role": pf.stem.replace("_", " ", 1).replace("_", "-"),
                "exit_code": p.returncode,
                "raw_output": raw[-4000:],
                "seconds": round(time.time() - t0, 2),
            }
        )
        if p.returncode != 0:
            all_ok = False
        print(f"{pf.name} rc={p.returncode} {round(time.time()-t0,1)}s")
    doc = {
        "schema_version": 1,
        "unit_id": uid,
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runs": runs,
        "all_exit_zero": all_ok,
    }
    (pdir / "PROBE-RUNS.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"{'SUCCESS' if all_ok else 'FAILED'}:run {uid} all_exit_zero={all_ok}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
