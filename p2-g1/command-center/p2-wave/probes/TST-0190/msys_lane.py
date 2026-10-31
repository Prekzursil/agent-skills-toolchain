#!/usr/bin/env python3
"""TST-0190 measured layer: bash-driven invocations of a native child, used to
observe MSYS path conversion of arguments with and without MSYS_NO_PATHCONV."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def git_bash() -> str:
    """Absolute Git Bash binary. The bare name resolves to WSL bash
    (System32) when spawned from a Windows process; WSL cannot see /c/...
    paths, which degraded every child call to rc=127."""
    cand = os.environ.get("GITBASH")
    if cand and Path(cand).is_file():
        return cand
    for c in (
        "C:" + chr(92) + "Program Files" + chr(92) + "Git" + chr(92) + "bin" + chr(92) + "bash.exe",
        "C:" + chr(92) + "Program Files" + chr(92) + "Git" + chr(92) + "usr" + chr(92) + "bin" + chr(92) + "bash.exe",
        "C:" + chr(92) + "Program Files (x86)" + chr(92) + "Git" + chr(92) + "bin" + chr(92) + "bash.exe",
    ):
        if Path(c).is_file():
            return c
    import shutil
    w = shutil.which("bash")
    if w and "git" in w.lower():
        return w
    raise RuntimeError("Git Bash not found; set GITBASH")


def run_bash(script: str, timeout: int = 60) -> tuple[int, str]:
    p = subprocess.run(
        [git_bash(), "-c", script], capture_output=True, text=True, timeout=timeout
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def child_argv(posix_style_arg: str, suppress: bool) -> tuple[int, str]:
    """Spawn the native argv-echo child from bash; suppress toggles the env prefix."""
    py = sys.executable.replace("\\", "/")
    echo = (HERE / "echo_args.py").as_posix()
    prefix = "MSYS_NO_PATHCONV=1 " if suppress else ""
    script = "%s%s %s %s" % (prefix, py, echo, posix_style_arg)
    return run_bash(script)
