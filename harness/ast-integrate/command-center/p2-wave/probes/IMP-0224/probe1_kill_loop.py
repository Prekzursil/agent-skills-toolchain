#!/usr/bin/env python3
"""IMP-0224 probe 1: 50 SIGKILL iterations leave 50 parseable published ledgers.

Signal: computed pass count. A kill mid-write must leave the published JSONL
parseable with the in-flight record ABSENT (staging leftover is allowed).
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LEDGER_DIR = REPO / "tools" / "event-ledger"
sys.path.insert(0, str(LEDGER_DIR))

import ledger as L  # noqa: E402

UNIT = "IMP-0224"
KILL_TARGET = LEDGER_DIR / "kill_target.py"
ITERATIONS = 50
PAYLOAD = 131072
CHUNK = 256


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def seed(path: Path) -> None:
    L.LedgerWriter(path).append(
        actor="probe1",
        unit_id=UNIT,
        phase="7",
        from_state="absent",
        to_state="seeded",
        correlation_id="probe1-seed",
        causality_id="genesis",
        payload={"seed": True},
    )


def one_kill() -> dict:
    tmp = tempfile.mkdtemp(prefix="imp0224-p1-")
    path = Path(tmp) / "run.jsonl"
    seed(path)
    before = path.read_bytes()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-B",
            str(KILL_TARGET),
            "--path",
            str(path),
            "--mode",
            "atomic",
            "--payload-bytes",
            str(PAYLOAD),
            "--chunk-size",
            str(CHUNK),
        ],
        cwd=str(REPO),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    t0 = time.monotonic()
    saw_staging = False
    while time.monotonic() - t0 < 2.5:
        if L.staging_paths(Path(tmp)):
            saw_staging = True
            break
        if proc.poll() is not None:
            break
        time.sleep(0.0004)
    if proc.poll() is None:
        time.sleep(0.001)
        try:
            os.kill(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    raw = path.read_bytes() if path.is_file() else b""
    info = L.inspect_published_bytes(raw)
    staging_left = [p.name for p in L.staging_paths(Path(tmp))]
    # Keep published bytes for the count; drop the temp dir after measuring.
    try:
        for p in Path(tmp).iterdir():
            p.unlink()
        Path(tmp).rmdir()
    except OSError:
        pass
    return {
        "parseable": bool(info["parseable"]),
        "half_written": int(info["half_written"]),
        "line_count": int(info["line_count"]),
        "saw_staging": saw_staging,
        "staging_left": len(staging_left),
        "grew": len(raw) > len(before),
        "rc": proc.returncode,
    }


def main() -> int:
    rows = [one_kill() for _ in range(ITERATIONS)]
    parseable = sum(1 for r in rows if r["parseable"])
    half = sum(r["half_written"] for r in rows)
    interrupted = sum(1 for r in rows if r["saw_staging"] or r["staging_left"])
    out = {
        "unit_id": UNIT,
        "probe": "probe1-kill-loop",
        "iterations": ITERATIONS,
        "parseable_ledgers": parseable,
        "half_written_total": half,
        "interrupted_staging_observed": interrupted,
        "pass": parseable == ITERATIONS and half == 0,
        "sample": rows[:3],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"parseable={parseable}/{ITERATIONS} half_written={half} "
        f"staging_hits={interrupted}"
    )
    if parseable != ITERATIONS:
        return fail(f"parseable {parseable}/{ITERATIONS}")
    if half != 0:
        return fail(f"half_written={half}")
    print(f"SUCCESS:{UNIT}-probe1 50/50 kill-loop parseable; partial records absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
