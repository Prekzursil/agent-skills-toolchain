"""Negative-control concatenated spawn (shell=True + f-string command)."""
from __future__ import annotations

import subprocess
import sys


def run_concatenated(python: str, child: str, token: str):
    return subprocess.run(
        f"{python} {child} {token}",
        shell=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
