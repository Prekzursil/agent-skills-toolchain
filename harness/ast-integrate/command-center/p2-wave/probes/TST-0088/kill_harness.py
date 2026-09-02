#!/usr/bin/env python3
"""Run a victim writer as a child process and SIGKILL it in the hold window."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WRITERS = HERE / "writers.py"


def wait_ready(ready: Path, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if ready.is_file() and ready.stat().st_size > 0:
            return True
        time.sleep(0.01)
    return False


def run_writer(
    *,
    mode: str,
    dest: Path,
    ready: Path,
    complete: bool,
    hold_seconds: float = 30.0,
    unit_id: str = "VICTIM-0088",
    sentinel: str = "SUCCESS:VICTIM-0088",
) -> subprocess.Popen:
    cmd = [
        sys.executable,
        "-B",
        str(WRITERS),
        "--mode",
        mode,
        "--dest",
        str(dest),
        "--ready",
        str(ready),
        "--unit-id",
        unit_id,
        "--sentinel",
        sentinel,
        "--hold-seconds",
        str(hold_seconds),
    ]
    if complete:
        cmd.append("--complete")
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if ready.exists():
        ready.unlink()
    if dest.exists():
        dest.unlink()
    tmp = dest.with_name(dest.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    return subprocess.Popen(
        cmd,
        cwd=str(HERE),
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def sigkill(proc: subprocess.Popen) -> dict:
    pid = proc.pid
    killed = False
    try:
        os.kill(pid, signal.SIGKILL)
        killed = True
    except ProcessLookupError:
        killed = False
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        proc.wait(timeout=5)
    return {
        "pid": pid,
        "signal": "SIGKILL",
        "signal_number": int(signal.SIGKILL),
        "kill_issued": killed,
        "returncode": proc.returncode,
    }


def run_and_kill(
    *,
    mode: str,
    dest: Path,
    ready: Path,
    hold_seconds: float = 30.0,
    ready_timeout: float = 10.0,
) -> dict:
    proc = run_writer(
        mode=mode,
        dest=dest,
        ready=ready,
        complete=False,
        hold_seconds=hold_seconds,
    )
    saw_ready = wait_ready(ready, timeout=ready_timeout)
    kill_info = sigkill(proc)
    tmp = dest.with_name(dest.name + ".tmp")
    return {
        **kill_info,
        "mode": mode,
        "saw_ready": saw_ready,
        "ready_token": ready.read_text(encoding="utf-8").strip() if ready.is_file() else None,
        "dest_exists": dest.is_file(),
        "dest_bytes": dest.stat().st_size if dest.is_file() else 0,
        "tmp_exists": tmp.is_file(),
        "tmp_bytes": tmp.stat().st_size if tmp.is_file() else 0,
        "dest": str(dest),
        "tmp": str(tmp),
    }


def run_complete(
    *,
    mode: str,
    dest: Path,
    ready: Path,
) -> dict:
    proc = run_writer(mode=mode, dest=dest, ready=ready, complete=True, hold_seconds=0)
    rc = proc.wait(timeout=10)
    tmp = dest.with_name(dest.name + ".tmp")
    return {
        "mode": mode,
        "complete": True,
        "returncode": rc,
        "dest_exists": dest.is_file(),
        "dest_bytes": dest.stat().st_size if dest.is_file() else 0,
        "tmp_exists": tmp.is_file(),
        "dest": str(dest),
    }
