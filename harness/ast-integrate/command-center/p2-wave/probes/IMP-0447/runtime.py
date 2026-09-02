"""Spawn hang-detection fixture workers and import the runner module."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RUNNER = REPO / "command-center" / "runner"
WORKER = HERE / "fixtures" / "worker.py"

if str(RUNNER) not in sys.path:
    sys.path.insert(0, str(RUNNER))

import hang_detect as HD  # noqa: E402


def spawn(mode: str, hb: Path, out: Path, interval: float = 0.05) -> subprocess.Popen:
    hb.parent.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [sys.executable, "-B", str(WORKER), mode, str(hb), str(out), str(interval)],
        cwd=str(REPO),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if hb.is_file() and out.is_file():
            return proc
        if proc.poll() is not None:
            err = (proc.stderr.read() if proc.stderr else b"") or b""
            raise RuntimeError(f"fixture {mode} exited {proc.returncode}: {err[:400]!r}")
        time.sleep(0.01)
    raise RuntimeError(f"fixture {mode} did not create heartbeat/output files")


def kill(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        proc.kill()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.terminate()
