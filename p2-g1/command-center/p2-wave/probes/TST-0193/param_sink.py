#!/usr/bin/env python3
"""TST-0193 measured layer: the workflow parameter sink.

sink() forwards parameters to a child through a LIST-ARGV spawn (shell=False,
CreateProcess direct) - the reference no-reparse sink. observe() returns the
exact strings the child received.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sink(params: list[str]) -> tuple[int, str]:
    echo = (HERE / "echo_args.py").as_posix()
    p = subprocess.run(
        [sys.executable, "-B", echo, *params],
        capture_output=True, text=True, timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def observed(params: list[str]) -> list[str]:
    rc, out = sink(params)
    return json.loads(out.strip().splitlines()[-1])["argv"]
