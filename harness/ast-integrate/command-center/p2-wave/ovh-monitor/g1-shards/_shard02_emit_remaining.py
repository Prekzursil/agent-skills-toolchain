#!/usr/bin/env python3
"""Run per-unit emit/write_receipts then sync UNIT-ARTIFACT-MANIFEST. No global --write."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path.home() / "p2-g1")
WAVE = ROOT / "command-center" / "p2-wave"
IDS = Path(__file__).with_name("_shard02_fail_ids.txt")
HELPERS = (
    "write_receipts.py",
    "emit_artifact.py",
    "emit_receipt.py",
    "emit.py",
    "emit_migration.py",
    "emit_stability.py",
)


def run(cmd: list[str]) -> int:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(ROOT)
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env)
    return proc.returncode


def main() -> int:
    ids = [ln.strip() for ln in IDS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    py = sys.executable
    sync = WAVE / "seed-stage" / "_g1_sync_manifest.py"
    for uid in ids:
        pdir = WAVE / "probes" / uid
        ran = False
        for name in HELPERS:
            script = pdir / name
            if script.is_file():
                print(f"EMIT {uid} {name}", flush=True)
                rc = run([py, "-B", str(script)])
                print(f"EMIT_RC {uid} {name} {rc}", flush=True)
                ran = True
                if rc == 0:
                    break
        if sync.is_file():
            run([py, "-B", str(sync), uid])
        if not ran:
            print(f"NO_EMIT {uid}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
