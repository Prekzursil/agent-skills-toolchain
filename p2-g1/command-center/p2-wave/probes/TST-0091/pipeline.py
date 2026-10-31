#!/usr/bin/env python3
"""TST-0091 pipeline: per-unit timeouts + write-as-you-go barrier.

per_unit_pipeline(jobs, timeout_s) runs every unit in its own thread,
writes each result durably AS IT FINISHES (write-as-you-go), and
resolves the barrier on the survivors with hung units classified
timeout-<n>s at their declared deadline - never silently awaited.
naive_parallel() is the recorded control: one barrier, no per-unit
timeout - a hung unit blocks everything (zero durable rows)."""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _run_one(job: dict, timeout_s: float, outdir: Path, rows: dict, lock: threading.Lock) -> None:
    name = job["id"]

    def target() -> None:
        try:
            job["fn"]()
            res = {"unit_id": name, "status": "SUCCESS"}
        except Exception as exc:
            res = {"unit_id": name, "status": "FAILED", "error": type(exc).__name__ + ": " + str(exc)[:80]}
        with lock:
            rows[name] = res

    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(timeout_s)
    if th.is_alive():
        with lock:
            rows.setdefault(name, {"unit_id": name, "status": "TIMEOUT",
                                   "classification": "timeout-" + str(timeout_s) + "s",
                                   "declared_timeout_s": timeout_s})
    with lock:
        row = rows.get(name)
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / (name + ".json")).write_text(json.dumps(row, indent=1), encoding="utf-8")


def per_unit_pipeline(jobs: list[dict], timeout_s: float, outdir: Path) -> dict:
    started = time.perf_counter()
    rows: dict = {}
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        futs = [pool.submit(_run_one, j, timeout_s, outdir, rows, lock) for j in jobs]
        for f in futs:
            f.result()
    wall = time.perf_counter() - started
    n_success = sum(1 for r in rows.values() if r["status"] == "SUCCESS")
    n_timeout = sum(1 for r in rows.values() if r["status"] == "TIMEOUT")
    n_failed = sum(1 for r in rows.values() if r["status"] == "FAILED")
    return {"barrier_resolved": True, "wall_s": wall, "n": len(jobs), "rows": rows,
            "n_success": n_success, "n_timeout": n_timeout, "n_failed": n_failed,
            "write_as_you_go": True,
            "durable_rows": sorted(p.name for p in outdir.glob("*.json"))}


def naive_parallel(jobs: list[dict], watchdog_s: float) -> dict:
    """One barrier, no per-unit timeout: the hung unit blocks the phase.

    Observation stops at the watchdog; workers are daemon threads owned
    here so the observation process never waits out the hang."""
    started = time.perf_counter()
    done: dict[str, str] = {}
    lock = threading.Lock()
    threads = []

    def wrap(j: dict) -> None:
        try:
            j["fn"]()
            with lock:
                done[j["id"]] = "SUCCESS"
        except Exception as exc:
            with lock:
                done[j["id"]] = "FAILED:" + type(exc).__name__

    for j in jobs:
        th = threading.Thread(target=wrap, args=(j,), daemon=True)
        th.start()
        threads.append(th)
    deadline = started + watchdog_s
    for th in threads:
        th.join(timeout=max(0.0, deadline - time.perf_counter()))
    elapsed = time.perf_counter() - started
    if len(done) < len(jobs):
        blocked_on = next(j["id"] for j in jobs if j["id"] not in done)
        return {"resolved": False, "durable_rows": [], "wall_s": elapsed,
                "blocked_on": blocked_on, "note": "one hung unit deadlocks the phase"}
    return {"resolved": True, "results": done, "wall_s": elapsed}


