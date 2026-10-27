#!/usr/bin/env python3
"""Shard-20 phase 2a: run every named probe live, capture runlog.json.

Runs each probe with the exact command form the measure gate uses
(env prefix + -B), records exit_code + tail per script. Failures are data:
the fix loop is probe-script fixes, never artifact edits to make a red green.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shard20_lib as L  # noqa: E402

REPO = L.REPO


def main() -> int:
    runlog: dict = {}
    total_fail = 0
    for uid in L.UIDS:
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        scripts = sorted(pdir.glob("probe*.py"))
        runlog[uid] = {}
        for sc in scripts:
            import os
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            cmd = f'"{sys.executable}" -B "{sc}"'
            try:
                r = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=600,
                                   env=env)
                tail = ((r.stdout or "") + (r.stderr or "")).strip()
                code = r.returncode
            except subprocess.TimeoutExpired:
                tail, code = "TIMEOUT", 124
            runlog[uid][sc.name] = {"command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {sc.as_posix()}",
                                    "exit_code": code,
                                    "tail": tail[-4000:]}
            if code != 0:
                total_fail += 1
                print(f"RED {uid}/{sc.name} rc={code}")
                for line in tail.splitlines()[:6]:
                    print("   ", line[:220])
            else:
                print(f"green {uid}/{sc.name}")
    (L.SHARD / "runlog.json").write_text(json.dumps(runlog, indent=1), encoding="utf-8")
    print(f"{'SUCCESS' if total_fail == 0 else 'INCOMPLETE'}:run_probes red={total_fail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
