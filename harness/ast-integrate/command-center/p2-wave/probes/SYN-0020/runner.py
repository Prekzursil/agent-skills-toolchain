"""Run extracted fenced commands in a clean bash; record exit and head output."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from contract import UNSAFE_RE

UNSAFE = re.compile(UNSAFE_RE, re.I)


def is_unsafe(invocation: str) -> bool:
    return bool(UNSAFE.search(invocation or ""))


def run_one(invocation: str, repo: Path, timeout: int = 20) -> dict:
    if is_unsafe(invocation):
        return {
            "invocation": invocation,
            "attempted": False,
            "exit_code": None,
            "stdout_head": "",
            "stderr_head": "refused:unsafe-pattern",
            "classification": "NOT-RUN",
            "reason": "unsafe-pattern",
        }
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPATH", None)
    try:
        proc = subprocess.run(
            ["bash", "--noprofile", "--norc", "-c", invocation],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "invocation": invocation,
            "attempted": True,
            "exit_code": 124,
            "stdout_head": "",
            "stderr_head": "TIMEOUT",
            "classification": "FAIL",
            "reason": "timeout",
        }
    stdout = (proc.stdout or "")[:400]
    stderr = (proc.stderr or "")[:400]
    code = int(proc.returncode)
    return {
        "invocation": invocation,
        "attempted": True,
        "exit_code": code,
        "stdout_head": stdout,
        "stderr_head": stderr,
        "classification": "PASS" if code == 0 else "FAIL",
        "reason": "exit-0" if code == 0 else f"exit-{code}",
    }


def run_all(commands: list[dict], repo: Path) -> list[dict]:
    rows: list[dict] = []
    for i, cmd in enumerate(commands, start=1):
        rec = run_one(cmd["invocation"], repo)
        rec["id"] = f"cmd-{i:02d}"
        rec["path"] = cmd["path"]
        rec["line"] = cmd["line"]
        rec["anchor"] = f"{cmd['path']}:{cmd['line']}"
        rec["doc_anchor"] = rec["anchor"]
        rows.append(rec)
    return rows
