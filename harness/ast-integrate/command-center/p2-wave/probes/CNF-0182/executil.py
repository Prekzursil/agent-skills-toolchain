"""Subprocess execution of a package's one-command, with runtime credential inject."""
from __future__ import annotations

import os
import subprocess

from common import REPO, RUNTIME_ENV


def inject_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault(RUNTIME_ENV, "runtime-injected-not-bundled")
    return env


def run_cmd(cmd: str, cwd=None, timeout: int = 60) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=inject_env(),
        timeout=timeout,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text
