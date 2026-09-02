#!/usr/bin/env python3
"""Crash-inject SIGKILL at randomized offsets while a publisher is mid-write."""
from __future__ import annotations

import os
import random
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WRITERS = HERE / "writers.py"

N_TRIALS = 100
PAYLOAD_LEN = 4096
CHUNK = 64
SEED = 146


def classify_dest(dest: Path, old: bytes, new: bytes) -> str:
    if not dest.exists():
        return "absent"
    got = dest.read_bytes()
    if got == old:
        return "old_complete"
    if got == new:
        return "new_complete"
    return "partial"


def _wait_until(pred, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.005)
    return False


def _kill(proc: subprocess.Popen) -> None:
    try:
        os.kill(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)


def run_trial(
    work: Path,
    mode: str,
    old: bytes,
    new: bytes,
    pause_at: int,
    python: str,
) -> dict:
    dest = work / "artifact.bin"
    payload = work / "new.bin"
    tmp_report = work / "tmp-path.txt"
    payload.write_bytes(new)
    dest.write_bytes(old)
    if tmp_report.exists():
        tmp_report.unlink()
    cmd = [
        python,
        "-B",
        str(WRITERS),
        "child",
        "--mode",
        mode,
        "--dest",
        str(dest),
        "--payload-file",
        str(payload),
        "--pause-at",
        str(pause_at),
        "--chunk",
        str(CHUNK),
    ]
    if mode == "atomic":
        cmd.extend(["--tmp-report", str(tmp_report)])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.Popen(
        cmd,
        cwd=str(HERE),
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if mode == "atomic":

            def ready() -> bool:
                if not tmp_report.is_file():
                    return False
                tmp = Path(tmp_report.read_text(encoding="utf-8").strip())
                try:
                    return tmp.stat().st_size >= pause_at
                except OSError:
                    return False

        else:

            def ready() -> bool:
                try:
                    # Truncate-then-write: dest is no longer OLD and has some NEW bytes.
                    if not dest.is_file():
                        return False
                    size = dest.stat().st_size
                    return size >= pause_at and dest.read_bytes() != old
                except OSError:
                    return False

        if not _wait_until(ready, timeout=5.0):
            _kill(proc)
            kind = classify_dest(dest, old, new)
            return {
                "mode": mode,
                "pause_at": pause_at,
                "pid": proc.pid,
                "wait_ready": False,
                "dest_class": kind,
                "dest_bytes": dest.stat().st_size if dest.exists() else 0,
            }
        _kill(proc)
        kind = classify_dest(dest, old, new)
        leftover_tmp = None
        if tmp_report.is_file():
            leftover_tmp = tmp_report.read_text(encoding="utf-8").strip()
        return {
            "mode": mode,
            "pause_at": pause_at,
            "pid": proc.pid,
            "wait_ready": True,
            "dest_class": kind,
            "dest_bytes": dest.stat().st_size if dest.exists() else 0,
            "tmp_path": leftover_tmp,
        }
    finally:
        if proc.poll() is None:
            _kill(proc)


def run_campaign(mode: str, n: int, rng: random.Random, root: Path) -> dict:
    old = bytes((i * 3) % 256 for i in range(PAYLOAD_LEN))
    new = bytes((i * 7 + 1) % 256 for i in range(PAYLOAD_LEN))
    lo = CHUNK
    hi = PAYLOAD_LEN - CHUNK
    offsets = [rng.randrange(lo, hi) for _ in range(n)]
    python = sys.executable
    trials = []
    partials = []
    work_root = root / mode
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    for i, pause_at in enumerate(offsets):
        work = work_root / f"t{i:03d}"
        work.mkdir(parents=True, exist_ok=True)
        rec = run_trial(work, mode, old, new, pause_at, python)
        rec["i"] = i
        trials.append(rec)
        if rec["dest_class"] == "partial":
            partials.append(rec)
        # Drop per-trial trees to keep the probe dir small; keep last partial if any.
        if rec["dest_class"] != "partial":
            shutil.rmtree(work, ignore_errors=True)
    classes = {}
    for rec in trials:
        classes[rec["dest_class"]] = classes.get(rec["dest_class"], 0) + 1
    return {
        "mode": mode,
        "n": n,
        "seed": SEED,
        "payload_len": PAYLOAD_LEN,
        "offsets": offsets,
        "class_counts": classes,
        "partial_count": len(partials),
        "ready_count": sum(1 for r in trials if r["wait_ready"]),
        "partials": partials[:5],
        "trials_sample": trials[:3] + trials[-2:],
    }


def run_both() -> dict:
    rng = random.Random(SEED)
    root = HERE / "runtime" / "crash"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    atomic = run_campaign("atomic", N_TRIALS, rng, root)
    control = run_campaign("non_atomic", N_TRIALS, rng, root)
    atomic_ok = (
        atomic["partial_count"] == 0
        and atomic["n"] == N_TRIALS
        and atomic["ready_count"] == N_TRIALS
        and atomic["class_counts"].get("old_complete", 0) + atomic["class_counts"].get("new_complete", 0)
        == N_TRIALS
    )
    control_ok = (
        control["partial_count"] > 0
        and control["ready_count"] == N_TRIALS
        and control["n"] == N_TRIALS
    )
    return {
        "atomic": atomic,
        "control": control,
        "atomic_zero_partials": atomic_ok,
        "control_found_partials": control_ok,
        "pass": atomic_ok and control_ok,
    }
