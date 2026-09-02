"""Process fixtures: live / finished / stalled."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .liveness import Observation

HERE = Path(__file__).resolve().parent
WORKER = HERE / "live_worker.py"


@dataclass
class Handle:
    name: str
    root: Path
    proc: subprocess.Popen | None
    artifact_dir: Path

    def observe(self) -> Observation:
        cpu_p = self.root / "cpu.counter"
        log_p = self.root / "artifact.log"
        cpu = float(cpu_p.read_text(encoding="utf-8")) if cpu_p.is_file() else 0.0
        nbytes = log_p.stat().st_size if log_p.is_file() else 0
        running = bool(self.proc is not None and self.proc.poll() is None)
        pid = int(self.proc.pid) if self.proc is not None else 0
        return Observation(self.name, pid, running, cpu, nbytes, time.time())


@contextmanager
def live_session(root: Path):
    d = Path(root) / "live"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cpu.counter").write_text("1", encoding="utf-8")
    (d / "artifact.log").write_bytes(b"seed")
    proc = subprocess.Popen(
        [sys.executable, "-B", str(WORKER), str(d)],
        cwd=str(d),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.2)
    try:
        yield Handle("live", d, proc, d)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()


@contextmanager
def finished_session(root: Path):
    d = Path(root) / "finished"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cpu.counter").write_text("0", encoding="utf-8")
    log = d / "artifact.log"
    log.write_bytes(b"frozen" * 8)
    ancient = time.time() - 11 * 3600
    os.utime(log, (ancient, ancient))
    yield Handle("finished", d, None, d)


@contextmanager
def stalled_session(root: Path):
    d = Path(root) / "stalled"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cpu.counter").write_text("5", encoding="utf-8")
    (d / "artifact.log").write_bytes(b"quiet" * 8)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(3600)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        yield Handle("stalled", d, proc, d)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
