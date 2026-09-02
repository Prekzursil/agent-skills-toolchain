#!/usr/bin/env python3
"""Reproduce A5 local fan-out vs the commit-charge ceiling on this box.

Calibration spawns at most CALIBRATE_N workers and always terminates them.
The 2048-unit projection is arithmetic, not a live ramp.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import box  # noqa: E402
import preflight as P  # noqa: E402

CALIBRATE_N = 4
WORKER_BYTES = 32 * 1024 * 1024
WORKER = (
    "import mmap,time\n"
    f"n={WORKER_BYTES}\n"
    "m=mmap.mmap(-1, n)\n"
    "m[:] = b'\\x01' * n\n"
    "time.sleep(8)"
)
A5_BATCH = 2048
SMALL_BATCH = 4


def _one_calibrate(n: int) -> dict[str, Any]:
    before_c = box.meminfo()["Committed_AS"]
    before_n = box.process_count()
    procs: list[subprocess.Popen] = []
    live = 0
    try:
        for _ in range(n):
            procs.append(subprocess.Popen([sys.executable, "-c", WORKER]))
        deadline = time.time() + 5.0
        while time.time() < deadline:
            live = sum(1 for p in procs if p.poll() is None)
            if live == n:
                break
            time.sleep(0.1)
        time.sleep(0.8)
        mid_c = box.meminfo()["Committed_AS"]
        mid_n = box.process_count()
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)
    delta = mid_c - before_c
    floor = n * WORKER_BYTES
    per = max(1, delta // n) if delta > 0 else 0
    return {
        "n": n,
        "before_committed": before_c,
        "mid_committed": mid_c,
        "delta": delta,
        "commit_per_worker": per,
        "before_nprocs": before_n,
        "mid_nprocs": mid_n,
        "proc_delta": mid_n - before_n,
        "live_workers": live,
        "mmap_floor_bytes": floor,
    }


def calibrate(n: int = CALIBRATE_N) -> dict[str, Any]:
    if n < 1 or n > 8:
        raise ValueError("calibration N out of abort bound")
    last: dict[str, Any] | None = None
    for _ in range(3):
        last = _one_calibrate(n)
        if last["delta"] >= last["mmap_floor_bytes"] // 2 and last["live_workers"] == n:
            return last
        time.sleep(0.4)
    assert last is not None
    # Workers ran and mapped anonymous pages; use the mmap floor rather than
    # a noisy negative Committed_AS reading from unrelated processes exiting.
    if last["live_workers"] == n:
        last["commit_per_worker"] = max(last["commit_per_worker"], WORKER_BYTES)
        last["used_mmap_floor"] = True
        return last
    raise RuntimeError(f"calibration failed: {last}")


def run_scenario() -> dict[str, Any]:
    estate = P.load_estate()
    cal = calibrate()
    snap = box.snapshot()
    per = int(cal["commit_per_worker"])
    local_big = P.evaluate(
        substrate="local", fanout=A5_BATCH, snap=snap, commit_per_worker=per, estate=estate
    )
    local_small = P.evaluate(
        substrate="local", fanout=SMALL_BATCH, snap=snap, commit_per_worker=per, estate=estate
    )
    cloud_big = P.evaluate(
        substrate="cloud", fanout=A5_BATCH, snap=snap, commit_per_worker=per, estate=estate
    )
    worktree_big = P.evaluate(
        substrate="worktree", fanout=A5_BATCH, snap=snap, commit_per_worker=per, estate=estate
    )
    sessions = int(estate["sessions"])
    servers = int(estate["servers_per_session"])
    blast = {
        "computed_not_asserted": True,
        "method": (
            "estate_processes = sessions * servers_per_session from "
            "fixtures/estate-freeze.json; local projection = live nprocs "
            "+ 3 dispatchers + fanout, commit = live Committed_AS + "
            "extra_processes * calibrated commit_per_worker"
        ),
        "estate_sessions": sessions,
        "estate_servers_per_session": servers,
        "estate_processes": sessions * servers,
        "catalog_stated_product": 2037,
        "catalog_arithmetic_matches": sessions * servers == 2037,
        "a5_fanout_units": A5_BATCH,
        "projected_local_processes": local_big["projection"]["projected_processes"],
        "projected_local_commit_bytes": local_big["projection"]["projected_commit_bytes"],
    }
    vacuity_ok = bool(local_small["allowed"])
    local_refused = not bool(local_big["allowed"])
    cloud_allowed = bool(cloud_big["allowed"])
    worktree_refused = not bool(worktree_big["allowed"])
    ram_hides = bool(snap["ram_hides_commit"])
    stated = 2037
    ok = (
        vacuity_ok
        and local_refused
        and cloud_allowed
        and worktree_refused
        and ram_hides
        and blast["estate_processes"] == sessions * servers
        and blast["estate_processes"] != stated
    )
    return {
        "pass": ok,
        "calibration": cal,
        "snapshot": snap,
        "local_big": local_big,
        "local_small": local_small,
        "cloud_big": cloud_big,
        "worktree_big": worktree_big,
        "process_blast": blast,
        "vacuity_small_local_allowed": vacuity_ok,
        "local_2048_refused": local_refused,
        "cloud_2048_allowed": cloud_allowed,
        "worktree_2048_refused": worktree_refused,
        "ram_hides_commit": ram_hides,
        "resource_ceiling": local_big["resource_ceiling"],
        "commit_per_worker": per,
    }


def main() -> int:
    run = run_scenario()
    print(json.dumps({k: run[k] for k in sorted(run) if k != "pass"}, sort_keys=True, default=str)[:8000])
    if not run.get("pass"):
        print("FAILED:ARC-0037 scenario did not reproduce ceiling")
        return 1
    print("SUCCESS:ARC-0037 scenario")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
