"""Known-broken string-concatenation spawn (mutation control for TST-0191).

Not a production launcher. Joining argv with spaces and handing the result to
a shell is the defect the property test must detect.
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ECHO = REPO / "tools" / "lib" / "argv_echo.py"


def concat_spawn(argv: Sequence[str], timeout: float = 30.0) -> subprocess.CompletedProcess[bytes]:
    cmd = " ".join(str(a) for a in argv)
    return subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def concat_echo(args: Sequence[str]) -> list[dict]:
    proc = concat_spawn([sys.executable, "-B", str(ECHO), *[str(a) for a in args]])
    if proc.returncode != 0:
        return []
    try:
        return json.loads(proc.stdout.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
