#!/usr/bin/env python3
"""Run per-unit emit/write_receipts for shard-18 IDs (Windows-safe)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
WRAPPER = WAVE / "seed-stage" / "g1_python.py"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-18.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
CANDS = (
    "emit_receipt.py",
    "emit_artifact.py",
    "emit_security.py",
    "emit_gate.py",
    "emit.py",
    "emit_note.py",
    "write_receipts.py",
)


def main() -> None:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(WAVE / "seed-stage"),
            str(REPO),
            str(REPO / "tools"),
            str(REPO / "tools" / "agentspec"),
            str(REPO / "command-center" / "lib"),
            env.get("PYTHONPATH", ""),
        ]
    )
    only = sys.argv[1:] or IDS
    for uid in only:
        pdir = WAVE / "probes" / uid
        scripts = [pdir / n for n in CANDS if (pdir / n).is_file()]
        if not scripts:
            print(f"NOEMIT {uid}")
            continue
        # emit_* first; write_receipts after if present
        ordered = [p for p in scripts if p.name != "write_receipts.py"]
        ordered += [p for p in scripts if p.name == "write_receipts.py"]
        for script in ordered[:2]:
            cmd = [sys.executable, "-B", str(WRAPPER), str(script)]
            print(f"RUN {uid} {script.name}", flush=True)
            try:
                p = subprocess.run(
                    cmd,
                    cwd=str(REPO),
                    capture_output=True,
                    text=True,
                    timeout=90,
                    env=env,
                )
            except subprocess.TimeoutExpired:
                print(f"TIMEOUT {uid} {script.name}", flush=True)
                continue
            tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-6:]
            mark = "OK" if p.returncode == 0 else f"FAIL rc={p.returncode}"
            print(f"  {mark} {uid} {script.name}")
            for ln in tail:
                print("   ", ln[:180])
            if p.returncode == 0 and script.name != "write_receipts.py":
                break


if __name__ == "__main__":
    main()
