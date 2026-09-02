"""Progress heartbeat and hang detector for long-running operations.

Hang windows are measured on the monotonic clock (time.monotonic()); the
wall clock is never read, so an NTP step or a DST change cannot fake a hang.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

HANG_DEFAULT_SEC = 30.0


@dataclass
class Heartbeat:
    token: int = 0
    last_output_bytes: int = 0
    started_monotonic: float = field(default_factory=time.monotonic)
    hang_timeout_sec: float = HANG_DEFAULT_SEC
    last_progress_monotonic: float = field(default_factory=time.monotonic)

    def stamp(self, output_bytes: int = 0) -> int:
        now = time.monotonic()
        if output_bytes > self.last_output_bytes:
            self.last_output_bytes = output_bytes
            self.last_progress_monotonic = now
        self.token += 1
        return self.token

    def hung(self, now: float | None = None) -> bool:
        t = time.monotonic() if now is None else now
        if self.hang_timeout_sec <= 0:
            return False
        return (t - self.last_progress_monotonic) >= self.hang_timeout_sec


def classify_child(
    *,
    token_delta: int,
    cpu_delta: float,
    output_bytes_delta: int,
    hang_timeout_sec: float,
    elapsed_sec: float,
) -> str:
    if hang_timeout_sec > 0 and elapsed_sec >= hang_timeout_sec:
        if token_delta == 0 and cpu_delta == 0 and output_bytes_delta == 0:
            return "FAILED"
    if output_bytes_delta == 0 and cpu_delta == 0 and token_delta == 0:
        return "SILENT"
    return "RUNNING"


def run_with_heartbeat(
    argv: Sequence[str],
    *,
    hang_timeout_sec: float = HANG_DEFAULT_SEC,
    heartbeat_sec: float = 0.2,
    cwd: str | Path | None = None,
) -> dict:
    """Spawn argv via subprocess.Popen and stamp a monotonic heartbeat."""
    hb = Heartbeat(hang_timeout_sec=hang_timeout_sec)
    started = time.monotonic()
    proc = subprocess.Popen(
        list(argv),
        cwd=None if cwd is None else str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    chunks: list[str] = []
    err_chunks: list[str] = []

    def _pump(stream, sink: list[str]) -> None:
        if stream is None:
            return
        for line in stream:
            sink.append(line)
            hb.stamp(sum(len(x) for x in sink))

    t_out = threading.Thread(target=_pump, args=(proc.stdout, chunks), daemon=True)
    t_err = threading.Thread(target=_pump, args=(proc.stderr, err_chunks), daemon=True)
    t_out.start()
    t_err.start()
    token_start = hb.token
    while True:
        rc = proc.poll()
        hb.stamp(sum(len(x) for x in chunks) + sum(len(x) for x in err_chunks))
        if rc is not None:
            break
        if hb.hung():
            proc.kill()
            proc.wait(timeout=3)
            rc = 124
            break
        time.sleep(heartbeat_sec)
    t_out.join(timeout=1)
    t_err.join(timeout=1)
    elapsed = time.monotonic() - started
    token_end = hb.token
    return {
        "ok": rc == 0,
        "exit_code": rc,
        "token_start": token_start,
        "token_end": token_end,
        "token_advanced": token_end > token_start,
        "elapsed_sec": elapsed,
        "stdout": "".join(chunks),
        "stderr": "".join(err_chunks),
        "hang_timeout_sec": hang_timeout_sec,
        "classification": "FAILED" if rc not in (0, None) else "SUCCESS",
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    hang = HANG_DEFAULT_SEC
    if args[:1] == ["--hang-timeout-sec"] and len(args) >= 2:
        hang = float(args[1])
        args = args[2:]
    if not args:
        print("usage: heartbeat.py [--hang-timeout-sec N] -- cmd...", file=sys.stderr)
        return 2
    if args[0] == "--":
        args = args[1:]
    rec = run_with_heartbeat(args, hang_timeout_sec=hang)
    print(json.dumps(rec, sort_keys=True))
    return int(rec["exit_code"] or 0)


if __name__ == "__main__":
    raise SystemExit(main())
