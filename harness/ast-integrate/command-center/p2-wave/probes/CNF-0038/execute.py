"""Run a test file against an isolated snapshot directory (stand-in commit)."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path


def tree_id(snapshot: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in snapshot.rglob("*") if p.is_file()):
        rel = path.relative_to(snapshot).as_posix().encode()
        h.update(rel)
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return "fixture:" + h.hexdigest()[:40]


def run_python(script: Path, snapshot: Path, timeout: int = 30) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(snapshot.resolve())
    proc = subprocess.run(
        [sys.executable, "-B", str(script)],
        cwd=str(snapshot),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    code = int(proc.returncode)
    return {
        "snapshot_path": str(snapshot),
        "exit_code": code,
        "verbatim_stdout": stdout,
        "verbatim_stderr": stderr,
        "verdict": "GREEN" if code == 0 else "RED",
    }
