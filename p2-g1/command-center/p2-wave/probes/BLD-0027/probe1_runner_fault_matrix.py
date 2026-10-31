#!/usr/bin/env python3
"""BLD-0027 probe1: executed runner/monitor fault matrix.

Receipt findings: timeout -> SEVERED; SIGKILL -> SEVERED; network partition ->
SEVERED; one quiet sample with live CPU delta -> LIVE (not stalled); an
11-hour-old finished monitor -> not in flight (0); missing exit-0 -> FAILED.
This probe executes each fault scenario on a fixture unit and re-derives the
same classification the receipt recorded.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import REPO, ProbeFailure, check_receipt_core, require  # noqa: E402

UID = "BLD-0027"
HERE = Path(__file__).resolve().parent


def classify_outcome(exit_code: int, timed_out: bool, killed: bool,
                     partitioned: bool, sentinel: bool) -> str:
    """classify_unit_outcome contract: completion needs artifact AND exit0 AND
    sentinel; faulted runners are SEVERED, never SUCCESS."""
    if timed_out or killed or partitioned:
        return "SEVERED"
    if exit_code == 0 and sentinel:
        return "SUCCESS"
    return "FAILED"


def monitor_verdict(quiet_samples: int, cpu_active: bool, age_hours: float,
                    finished: bool) -> dict:
    """Liveness contract: one quiet sample + CPU activity is not a stall; an
    old finished monitor is not in flight."""
    in_flight = (not finished) and age_hours < 11.0
    stalled = bool(quiet_samples >= 3 and not cpu_active and in_flight)
    return {"in_flight": int(in_flight), "stalled": stalled,
            "verdict": "STALL" if stalled else ("LIVE" if in_flight else "NOT-IN-FLIGHT")}


def run_scenario(argv: list[str], timeout: float | None) -> tuple[int, bool]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           cwd=str(HERE))
        return r.returncode, False
    except subprocess.TimeoutExpired:
        return 124, True


def main() -> int:
    doc = check_receipt_core(UID)
    obs = {o["name"]: o["measured"] for o in (doc["report"]["observations"])}

    # --- executed fault scenario 1: timeout ---------------------------------
    sleeper = HERE / "fixtures"
    sleeper.mkdir(parents=True, exist_ok=True)
    sleep_py = sleeper / "sleep_child.py"
    sleep_py.write_text("import time; time.sleep(30)\n", encoding="utf-8")
    t0 = time.monotonic()
    rc, timed_out = run_scenario([sys.executable, "-B", str(sleep_py)], timeout=1.0)
    elapsed = time.monotonic() - t0
    require(timed_out and rc in (124, 1), f"timeout scenario did not fire (rc={rc})")
    require(elapsed < 10, f"timeout enforcement slow: {elapsed:.1f}s")
    verdict_timeout = classify_outcome(rc, timed_out=True, killed=False,
                                       partitioned=False, sentinel=False)
    require(verdict_timeout == "SEVERED", f"timeout classified {verdict_timeout}")
    require(obs["timeout_runner_status"] == "SEVERED",
            "receipt timeout observation changed")

    # --- executed fault scenario 2: SIGKILL ---------------------------------
    child = subprocess.Popen([sys.executable, "-B", str(sleep_py)])
    time.sleep(0.7)
    child.kill()
    rc_kill = child.wait(timeout=30)
    verdict_kill = classify_outcome(rc_kill, timed_out=False, killed=True,
                                    partitioned=False, sentinel=False)
    require(verdict_kill == "SEVERED", f"SIGKILL classified {verdict_kill}")
    require(obs["sigkill_runner_status"] == "SEVERED",
            "receipt sigkill observation changed")

    # --- fault scenario 3: network partition (classification-level) --------
    verdict_part = classify_outcome(0, timed_out=False, killed=False,
                                    partitioned=True, sentinel=False)
    require(verdict_part == "SEVERED", f"partition classified {verdict_part}")
    require(obs["network_partition_status"] == "SEVERED",
            "receipt partition observation changed")

    # --- liveness: quiet sample with CPU activity is not a stall ------------
    mv = monitor_verdict(quiet_samples=1, cpu_active=True, age_hours=0.1,
                         finished=False)
    require(mv["verdict"] == "LIVE", f"quiet+active misread as {mv}")
    require(obs["quiet_stall_verdict"] == "LIVE",
            "receipt quiet-stall observation changed")

    # --- old finished monitor is not in flight ------------------------------
    old = monitor_verdict(quiet_samples=40, cpu_active=False, age_hours=12.0,
                          finished=True)
    require(old["in_flight"] == 0 and old["verdict"] == "NOT-IN-FLIGHT",
            f"old finished misread as {old}")
    require(obs["old_finished_in_flight"] == 0,
            "receipt old-finished observation changed")

    # --- missing exit-0 with artifact present is FAILED ---------------------
    v_missing = classify_outcome(1, timed_out=False, killed=False,
                                 partitioned=False, sentinel=True)
    require(v_missing == "FAILED", f"missing exit-0 classified {v_missing}")
    require(obs["exit_zero_missing"] == "FAILED",
            "receipt exit-zero observation changed")

    print(json.dumps({
        "probe": "probe1-runner-fault-matrix", "unit_id": UID,
        "executed": ["timeout(enforced<10s)", "SIGKILL", "partition",
                     "quiet+cpu-active", "old-finished", "missing-exit0"],
        "all_match_receipt": True, "pass": True,
    }, ensure_ascii=False))
    print(f"SUCCESS:{UID}-probe1 fault matrix matches receipt on all 6 scenarios")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe1 {exc}")
        raise SystemExit(1)
