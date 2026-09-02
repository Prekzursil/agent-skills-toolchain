#!/usr/bin/env python3
"""Durable orchestrator ledger helpers (append-only JSONL)."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKER = HERE / "worker.py"


def append(ledger: Path, rec: dict) -> None:
    rec = dict(rec)
    rec.setdefault("ts", time.time())
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def spawn_worker(args: list[str]) -> subprocess.Popen:
    cmd = [sys.executable, "-B", str(WORKER), *args]
    return subprocess.Popen(
        cmd,
        cwd=str(HERE),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def kill_pid(pid: int, sig: int = signal.SIGKILL) -> None:
    try:
        os.kill(int(pid), sig)
    except ProcessLookupError:
        return
    except PermissionError:
        return


def wait_bytes(path: Path, minimum: int, timeout_s: float = 45.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if path.is_file() and path.stat().st_size >= minimum:
            return True
        time.sleep(0.02)
    return False


def wait_exit(proc: subprocess.Popen, timeout_s: float = 45.0) -> int | None:
    try:
        return int(proc.wait(timeout=timeout_s))
    except subprocess.TimeoutExpired:
        return None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False
