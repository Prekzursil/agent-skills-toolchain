#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
IDS = ["CC-0009", "CNF-0004", "RES-0079", "CNF-0001", "ADV-0005"]


def pick(probe_dir: Path, globn: str) -> Path | None:
    paths = sorted(probe_dir.glob(globn))
    named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
    if named:
        return named[0]
    return paths[0] if paths else None


def main() -> int:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    hook = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    env["PYTHONPATH"] = os.pathsep.join(
        [
            hook,
            str(REPO),
            str(REPO / "tools"),
            str(REPO / "tools" / "command-center"),
            env.get("PYTHONPATH", ""),
        ]
    )
    rc_all = 0
    for uid in IDS:
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        for globn in ("probe1*.py", "probe2*.py"):
            script = pick(pdir, globn)
            if script is None:
                print(f"{uid} {globn} MISSING")
                rc_all = 1
                continue
            p = subprocess.run(
                [sys.executable, "-B", str(script)],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                timeout=180,
                env=env,
            )
            text = ((p.stdout or "") + (p.stderr or "")).strip()
            last = text.splitlines()[-1] if text else f"exit={p.returncode}"
            print(f"{uid} {script.name} rc={p.returncode} {last[:200]}")
            if p.returncode != 0:
                rc_all = p.returncode
                for ln in text.splitlines()[-12:]:
                    print("   ", ln)
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
