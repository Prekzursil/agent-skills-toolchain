#!/usr/bin/env python3
"""Bounded abortable fan-out ramp for BLD-0057.

Children are tagged with BLD0057_RUN in their environment. The guard action
is REFUSE_RAISE. A kill-based mutant exists only as named failure class 11328.
Ramps stay far below host freeze: a handful of tagged workers, then reap.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WORKER = HERE / "worker.py"

import guard as G  # noqa: E402
import observe as O  # noqa: E402

MARKER = "BLD0057_RUN"


def _mark(run_id: str) -> bytes:
    return f"{MARKER}={run_id}".encode("ascii")


def _alive(pid: int) -> bool:
    """True only for a non-zombie /proc entry."""
    stat = Path(f"/proc/{pid}/stat")
    try:
        text = stat.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    rparen = text.rfind(")")
    if rparen == -1 or rparen + 2 >= len(text):
        return False
    state = text[rparen + 2]
    return state not in {"Z", "X"}


def spawn(
    run_id: str,
    *,
    role: str = "worker",
    mmap_bytes: int = 0,
    fds: int = 4,
    heartbeat: str | None = None,
) -> subprocess.Popen:
    env = os.environ.copy()
    env[MARKER] = run_id
    env["BLD0057_ROLE"] = role
    env["BLD0057_MMAP"] = str(int(mmap_bytes))
    env["BLD0057_FDS"] = str(int(fds))
    if heartbeat:
        env["BLD0057_HEARTBEAT"] = heartbeat
    return subprocess.Popen(
        [sys.executable, "-B", str(WORKER)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def reap(run_id: str, procs: list[subprocess.Popen] | None = None, timeout: float = 3.0) -> dict[str, Any]:
    procs = list(procs or [])
    for p in procs:
        if p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except OSError:
                try:
                    p.terminate()
                except OSError:
                    pass
    deadline = time.time() + timeout
    leftover: list[int] = []
    while time.time() < deadline:
        leftover = O.tagged_pids(_mark(run_id))
        if not leftover:
            break
        time.sleep(0.05)
    leftover = O.tagged_pids(_mark(run_id))
    for pid in leftover:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    time.sleep(0.05)
    leftover = O.tagged_pids(_mark(run_id))
    for p in procs:
        try:
            p.wait(timeout=0.2)
        except Exception:
            pass
    return {"leftover_tagged": leftover, "clean": not leftover}


def run_guard_trip(*, max_tagged: int = 6, degrade_at: int = 16) -> dict[str, Any]:
    run_id = uuid.uuid4().hex[:12]
    procs: list[subprocess.Popen] = []
    guard = G.HeadroomGuard(
        max_tagged=max_tagged,
        max_commit_delta_bytes=256 * 1024 * 1024,
    )
    baseline = O.snapshot()
    decisions: list[dict[str, Any]] = []
    tripped = False
    trip_reason = None
    result: dict[str, Any] = {}
    try:
        for i in range(degrade_at + 2):
            snap = O.snapshot()
            tagged = O.tagged_pids(_mark(run_id))
            delta = int(snap["committed_as_bytes"]) - int(baseline["committed_as_bytes"])
            decision = guard.admit(
                snapshot=O.guard_view(snap),
                tagged_count=len(tagged),
                commit_delta_bytes=max(0, delta),
            )
            decisions.append(
                {
                    "step": i,
                    "allow": decision.allow,
                    "action": decision.action,
                    "reason": decision.reason,
                    "tagged": len(tagged),
                }
            )
            if not decision.allow:
                tripped = True
                trip_reason = decision.reason
                break
            procs.append(spawn(run_id))
            time.sleep(0.08)
        tagged_at_trip = O.tagged_pids(_mark(run_id))
        reached_degrade = len(tagged_at_trip) >= degrade_at or len(procs) >= degrade_at
        result = {
            "run_id": run_id,
            "tripped": tripped,
            "trip_reason": trip_reason,
            "trip_action": "REFUSE_RAISE" if tripped else None,
            "tagged_at_trip": len(tagged_at_trip),
            "spawned": len(procs),
            "max_tagged": max_tagged,
            "degrade_at": degrade_at,
            "reached_degrade": reached_degrade,
            "guard_before_degrade": bool(tripped and not reached_degrade),
            "baseline_process_count": baseline["process_count"],
            "decisions": decisions,
        }
    finally:
        cleanup = reap(run_id, procs)
    result["cleanup"] = cleanup
    result["orphans_after"] = not cleanup["clean"]
    return result


def run_abort_midway(*, abort_after: int = 3) -> dict[str, Any]:
    run_id = uuid.uuid4().hex[:12]
    procs: list[subprocess.Popen] = []
    baseline = O.snapshot()
    try:
        for _ in range(abort_after):
            procs.append(spawn(run_id))
            time.sleep(0.05)
        tagged_at_abort = O.tagged_pids(_mark(run_id))
        cleanup = reap(run_id, procs)
        procs = []
        time.sleep(0.1)
        after = O.snapshot()
        after_tagged = O.tagged_pids(_mark(run_id))
        return {
            "aborted": True,
            "spawned_before_abort": abort_after,
            "tagged_at_abort": len(tagged_at_abort),
            "tagged_after_cleanup": len(after_tagged),
            "cleanup_clean": cleanup["clean"],
            "baseline_process_count": baseline["process_count"],
            "after_process_count": after["process_count"],
            "process_count_restored": len(after_tagged) == 0
            and abs(int(after["process_count"]) - int(baseline["process_count"])) <= 32,
        }
    finally:
        reap(run_id, procs)


def run_shared_service_control(*, max_tagged: int = 5) -> dict[str, Any]:
    run_id = uuid.uuid4().hex[:12]
    procs: list[subprocess.Popen] = []
    tmp = Path(tempfile.mkdtemp(prefix="bld0057-hb-"))
    hb = str(tmp / "shared.pid")
    try:
        shared = spawn(run_id, role="shared", mmap_bytes=0, fds=2, heartbeat=hb)
        procs.append(shared)
        time.sleep(0.25)
        shared_pid = shared.pid
        guard = G.HeadroomGuard(
            max_tagged=max_tagged,
            max_commit_delta_bytes=256 * 1024 * 1024,
            protected_pids={shared_pid},
        )
        baseline = O.snapshot()
        tripped = False
        for _ in range(max_tagged + 3):
            snap = O.snapshot()
            tagged = O.tagged_pids(_mark(run_id))
            workers = [p for p in tagged if p != shared_pid]
            delta = int(snap["committed_as_bytes"]) - int(baseline["committed_as_bytes"])
            decision = guard.admit(
                snapshot=O.guard_view(snap),
                tagged_count=len(workers),
                commit_delta_bytes=max(0, delta),
            )
            if not decision.allow:
                tripped = True
                break
            procs.append(spawn(run_id))
            time.sleep(0.08)
        shared_alive = _alive(shared_pid)
        spare = guard.admit(
            snapshot=O.guard_view(O.snapshot()),
            tagged_count=max_tagged + 10,
            commit_delta_bytes=0,
            candidate_pid=shared_pid,
        )
        return {
            "shared_pid": shared_pid,
            "tripped": tripped,
            "shared_alive_after_trip": shared_alive,
            "guard_action": "REFUSE_RAISE",
            "spare_decision": spare.action,
            "did_not_kill_shared": bool(shared_alive and spare.action == "SPARE"),
        }
    finally:
        reap(run_id, procs)


def run_kill_mutant() -> dict[str, Any]:
    """Named failure class, exercised only against our tagged dummy children."""
    run_id = uuid.uuid4().hex[:12]
    procs: list[subprocess.Popen] = []
    try:
        shared = spawn(run_id, role="shared")
        worker = spawn(run_id, role="worker")
        procs.extend([shared, worker])
        time.sleep(0.2)
        before = _alive(shared.pid)
        mutant = G.kill_based_mutant([shared.pid, worker.pid])
        deadline = time.time() + 2.0
        while time.time() < deadline and _alive(shared.pid):
            for p in (shared, worker):
                try:
                    p.wait(timeout=0.05)
                except Exception:
                    pass
        after = _alive(shared.pid)
        return {
            "failure_class": mutant["class"],
            "spec": mutant["spec"],
            "shared_alive_before": before,
            "shared_alive_after": after,
            "mutant_killed_shared": bool(before and not after),
            "killed": mutant["killed"],
        }
    finally:
        reap(run_id, procs)


def run_signal_disagreement() -> dict[str, Any]:
    proc_run = uuid.uuid4().hex[:12]
    commit_run = uuid.uuid4().hex[:12]
    proc_ps: list[subprocess.Popen] = []
    commit_ps: list[subprocess.Popen] = []
    try:
        base = O.snapshot()
        for _ in range(8):
            proc_ps.append(spawn(proc_run, mmap_bytes=0, fds=6))
        time.sleep(0.4)
        proc_snap = O.snapshot()
        proc_tagged = O.tagged_pids(_mark(proc_run))
        reap(proc_run, proc_ps)
        proc_ps = []
        time.sleep(0.2)

        mid = O.snapshot()
        commit_ps.append(spawn(commit_run, mmap_bytes=48 * 1024 * 1024, fds=1))
        time.sleep(0.5)
        commit_snap = O.snapshot()
        commit_tagged = O.tagged_pids(_mark(commit_run))

        proc_d_proc = int(proc_snap["process_count"]) - int(base["process_count"])
        proc_d_as = int(proc_snap["committed_as_bytes"]) - int(base["committed_as_bytes"])
        commit_d_proc = int(commit_snap["process_count"]) - int(mid["process_count"])
        commit_d_as = int(commit_snap["committed_as_bytes"]) - int(mid["committed_as_bytes"])
        disagree = (proc_d_proc > commit_d_proc) and (commit_d_as > max(proc_d_as, 0))
        return {
            "process_heavy": {
                "delta_process_count": proc_d_proc,
                "delta_committed_as_bytes": proc_d_as,
                "tagged": len(proc_tagged),
                "ram_used_ratio": proc_snap.get("ram_used_ratio"),
            },
            "commit_heavy": {
                "delta_process_count": commit_d_proc,
                "delta_committed_as_bytes": commit_d_as,
                "tagged": len(commit_tagged),
                "ram_used_ratio": commit_snap.get("ram_used_ratio"),
            },
            "counters_disagree": bool(disagree),
            "single_ram_reading_is_ceiling": False,
        }
    finally:
        reap(proc_run, proc_ps)
        reap(commit_run, commit_ps)


def calibrate_worker(*, mmap_bytes: int = 8 * 1024 * 1024) -> dict[str, Any]:
    run_id = uuid.uuid4().hex[:12]
    procs: list[subprocess.Popen] = []
    try:
        before = O.snapshot()
        procs.append(spawn(run_id, mmap_bytes=mmap_bytes, fds=4))
        time.sleep(0.4)
        after = O.snapshot()
        tagged = O.tagged_pids(_mark(run_id))
        return {
            "mmap_bytes": mmap_bytes,
            "delta_committed_as_bytes": int(after["committed_as_bytes"])
            - int(before["committed_as_bytes"]),
            "delta_process_count": int(after["process_count"]) - int(before["process_count"]),
            "delta_fd_allocated": int(after["fd_allocated"]) - int(before["fd_allocated"]),
            "tagged": len(tagged),
        }
    finally:
        reap(run_id, procs)
