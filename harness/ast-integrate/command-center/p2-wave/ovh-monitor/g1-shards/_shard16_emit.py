#!/usr/bin/env python3
"""Run per-unit emit/write_receipts scripts (never unit_manifest.py --write)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
IDS = [
    ln.strip()
    for ln in (HERE / "shard-16.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
CANDIDATES = (
    "emit_receipt.py",
    "emit_artifact.py",
    "emit.py",
    "write_receipts.py",
)


def main() -> None:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO / "command-center" / "p2-wave" / "seed-stage"),
            str(REPO),
            str(REPO / "tools"),
            str(REPO / "command-center"),
            env.get("PYTHONPATH") or "",
        ]
    )
    for uid in IDS:
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        scripts = [pdir / n for n in CANDIDATES if (pdir / n).is_file()]
        if not scripts:
            print("NO-EMIT", uid)
            continue
        # Prefer emit_receipt over write_receipts when both exist.
        script = scripts[0]
        print("EMIT", uid, script.name)
        p = subprocess.run(
            [sys.executable, "-B", str(script)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        tail = ((p.stdout or "") + (p.stderr or "")).strip()[-400:]
        print(" rc", p.returncode, tail.replace("\n", " | ")[:240])


if __name__ == "__main__":
    main()
