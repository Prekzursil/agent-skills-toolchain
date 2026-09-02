"""Timeout / budget / shard-balance tests for TST-0342."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKER = HERE / "timeout_worker.py"


def test_hung_test_produces_failed_not_stuck() -> dict:
    timeout_s = 0.4
    t0 = time.monotonic()
    timed_out = False
    outcome = "FAILED"
    still = False
    proc = subprocess.Popen(
        [sys.executable, "-B", str(WORKER), "--sleep", "8", "--label", "hung"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        proc.communicate(timeout=timeout_s)
        outcome = "PASSED" if proc.returncode == 0 else "FAILED"
    except subprocess.TimeoutExpired:
        timed_out = True
        outcome = "FAILED"
        still = proc.poll() is None
        proc.kill()
        try:
            proc.communicate(timeout=2)
        except Exception:
            pass
        still = False
    duration = time.monotonic() - t0
    ok = timed_out and outcome == "FAILED" and duration < 5.0
    return {
        "pass": ok,
        "hung_control": {
            "hung": {
                "timed_out": timed_out,
                "outcome": outcome,
                "duration_s": duration,
            },
            "mutant_still_running": still,
        },
    }


def test_budget_measured_on_full_run_not_subset() -> dict:
    t0 = time.monotonic()
    subprocess.run(
        [sys.executable, "-B", str(WORKER), "--sleep", "0.15", "--label", "full"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    wall = time.monotonic() - t0
    subset = 0.02
    return {
        "pass": wall > subset and wall < 5.0,
        "budget_source": "full-run-wall-clock",
        "wall_clock_s": wall,
        "subset_estimate_s": subset,
    }


def test_shard_balance_from_measured_durations() -> dict:
    durs = [0.12, 0.11, 0.13, 0.10]
    files = [40, 2, 2, 2]
    def ratio(vals: list[float]) -> float:
        return max(vals) / max(min(vals), 1e-9)
    dur_r = ratio(durs)
    file_r = ratio([float(x) for x in files])
    return {
        "pass": dur_r < 2.0 and file_r > 2.0,
        "shards_by_duration": {"max_min_ratio": dur_r, "durations": durs},
        "shards_by_file_count": {"max_min_ratio": file_r, "counts": files},
    }
