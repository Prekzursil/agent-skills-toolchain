#!/usr/bin/env python3
"""Targeted re-run (reviewer lane): BLD-0037 probe1 under a healthy-runner budget.

Used ONLY if the full sweep's 2700s budget expired under measured fleet load
(multiple concurrent BLD-0037 probe1 scans observed live). Same probe script,
same env, same exit-code requirement; only the wall-clock budget differs
(5400s). Also gives BLD-0023/0024 a second fresh execution against the CURRENT
(amended) receipts, since their SUBAGENT-RETURN records predate the amendments.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
RUNS = [
    ("BLD-0023", "probe1_planted_or_true.py"),
    ("BLD-0023", "probe2_ast_powershell.py"),
    ("BLD-0024", "probe1_lf_falsify.py"),
    ("BLD-0024", "probe2_console_reviewer.py"),
    ("BLD-0037", "probe1_recall_controls.py"),
    ("BLD-0037", "probe2_contradiction_anchors.py"),
]
OUT = REPO / "_rev-w2s6-indep" / "rerun-heavy-results.json"


def main() -> int:
    results = []
    for uid, name in RUNS:
        p = REPO / "command-center" / "p2-wave" / "probes" / uid / name
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["AST_INTEGRATE_ROOT"] = str(REPO)
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, "-B", str(p)], cwd=str(REPO),
                               capture_output=True, text=True, timeout=5400, env=env)
            rc = r.returncode
            tail = ((r.stdout or "") + (r.stderr or "")).strip()[-500:]
        except subprocess.TimeoutExpired:
            rc, tail = 124, "TIMEOUT-5400s"
        results.append({"unit": uid, "probe": name, "exit_code": rc,
                        "secs": round(time.time() - t0, 1), "tail": tail})
        print(f"{uid} {name} rc={rc} secs={results[-1]['secs']}", flush=True)
        OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    bad = [x for x in results if x["exit_code"] != 0]
    print("RERUN-ALL-EXIT0" if not bad else "RERUN-FAILURES:" + repr(bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
