#!/usr/bin/env python3
"""Windows-safe local G-1 remesure. Does not use bash VAR= python3 prefixes."""
from __future__ import annotations

import importlib.util
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

STAGE = Path(__file__).resolve().parent
MEASURE = STAGE.parent / "_measure_one_delivered.py"
REPO = MEASURE.resolve().parents[2]


def windows_run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    body = cmd.strip()
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=([^\s]+)\s+(.*)$", body)
        if not m:
            break
        env[m.group(1)] = m.group(2)
        body = m.group(3)
    parts = body.split()
    if not parts:
        return 2, "empty-cmd"
    if parts[0] in {"python3", "python"}:
        argv = [sys.executable] + parts[1:]
    else:
        argv = parts
    try:
        p = subprocess.run(
            argv,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text[-4000:]


def load_measure():
    spec = importlib.util.spec_from_file_location("measure_one_delivered", MEASURE)
    if spec is None or spec.loader is None:
        raise SystemExit("FAILED:measure-missing")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.run_cmd = windows_run_cmd
    return mod


def main() -> int:
    if len(sys.argv) < 2:
        print("FAILED:usage remeasure_local.py <UNIT-ID> [<UNIT-ID>...]")
        return 2
    mod = load_measure()
    rc = 0
    for uid in sys.argv[1:]:
        sys.argv = ["_measure_one_delivered.py", uid]
        one = mod.main()
        if one != 0:
            rc = one
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
