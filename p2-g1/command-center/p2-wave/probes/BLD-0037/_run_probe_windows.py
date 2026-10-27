#!/usr/bin/env python3
"""Windows-portable probe runner for BLD-0037 write_receipts.py.

Repair 2026-10-26 (resume shard4-w4): write_receipts.py's run_probe feeds
`VAR=value python3 -B ...` to cmd.exe via shell=True; cmd.exe cannot execute
POSIX env prefixes ('PYTHONDONTWRITEBYTECODE' is not recognized...), so the
receipt-refresh cycle could not run on this Windows host. This mirrors the
identical fix already shipped in command-center/p2-wave/_measure_one_delivered.py
("shard11 repair 2026-10-24"): move env prefixes into the child env, and
route python3 through the g1_python.py wrapper exactly as the measure does.
Probe selection, exit codes, and every other check are unchanged; no-op on
POSIX where the original prefix form already works.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]  # file sits in probes/BLD-0037/, so 4 levels up to repo root


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if os.name == "nt":
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip(chr(34)).strip(chr(39))
            cmd = cmd[m.end():]
        wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
        if wrapper.is_file() and "python3" in cmd:
            _exe = str(sys.executable).replace("\\", "/")
            cmd = cmd.replace("python3", f"{_exe} {wrapper.as_posix()}", 1)
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text
