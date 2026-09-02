"""Python wrapper around scripts/longrun.sh / longrun.ps1."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LONGRUN_SH = REPO / "scripts" / "longrun.sh"
LONGRUN_PS1 = REPO / "scripts" / "longrun.ps1"


def longrun_script() -> Path:
    if os.name == "nt" and LONGRUN_PS1.is_file():
        return LONGRUN_PS1
    if LONGRUN_SH.is_file():
        return LONGRUN_SH
    return LONGRUN_PS1 if LONGRUN_PS1.is_file() else LONGRUN_SH


def run(
    argv: Sequence[str],
    *,
    ident: str = "longrun",
    heartbeat_sec: int = 15,
    hang_timeout_sec: int = 0,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    script = longrun_script()
    if script.suffix.lower() == ".ps1":
        wrapped = [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script),
            "-Id",
            ident,
            "-HeartbeatSec",
            str(heartbeat_sec),
            "-HangTimeoutSec",
            str(hang_timeout_sec),
            "-Cmd",
            *argv,
        ]
    else:
        wrapped = [
            "bash",
            str(script),
            "-i",
            ident,
            "-h",
            str(heartbeat_sec),
            "-t",
            str(hang_timeout_sec),
            "--",
            *argv,
        ]
    return subprocess.run(
        wrapped,
        cwd=None if cwd is None else str(cwd),
        text=True,
        capture_output=True,
    )


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("usage: longrun.py cmd...", file=sys.stderr)
        return 2
    rec = run(args)
    sys.stdout.write(rec.stdout or "")
    sys.stderr.write(rec.stderr or "")
    return int(rec.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
