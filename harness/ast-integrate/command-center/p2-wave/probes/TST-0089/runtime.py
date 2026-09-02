#!/usr/bin/env python3
"""Fault-injection runtime: kill monitor vs kill work, then harvest.

Work is started in a new session so SIGKILL of the monitor cannot take the
remote process with it. The supervisor, not the dying monitor, records
monitor-died. File mtimes are never used as stall or liveness signals.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from harvest import harvest  # noqa: E402
from ledger import append_event, event_types, read_events  # noqa: E402

PY = sys.executable


def wait_until(pred: Callable[[], bool], timeout_s: float, interval_s: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(interval_s)
    return False


def heartbeat_count(run_dir: Path) -> int:
    return sum(1 for e in read_events(run_dir) if e.get("event") == "monitor-heartbeat")


def _popen(script: str, args: list[str], run_dir: Path) -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(HERE)
    return subprocess.Popen(
        [PY, "-B", str(HERE / script), *args],
        cwd=str(HERE),
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _kill(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.kill(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass


def run_scenario(
    kind: str,
    run_dir: Path,
    duration_s: float = 0.85,
    post_kill_silence_s: float = 0.12,
) -> dict[str, Any]:
    if kind not in {"kill-monitor", "kill-work"}:
        raise ValueError(kind)
    run_dir = Path(run_dir)
    if run_dir.exists():
        for child in run_dir.rglob("*"):
            if child.is_file():
                child.unlink()
    run_dir.mkdir(parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex
    append_event(
        run_dir,
        {"event": "run-started", "actor": "supervisor", "kind": kind, "nonce": nonce},
    )
    work = _popen(
        "worker.py",
        ["--run-dir", str(run_dir), "--nonce", nonce, "--duration-s", str(duration_s)],
        run_dir,
    )
    if not wait_until(lambda: (run_dir / "work.ready").is_file(), 5.0):
        _kill(work)
        raise RuntimeError("worker did not publish work.ready")
    work_pid = work.pid
    monitor = _popen(
        "monitor.py",
        ["--run-dir", str(run_dir), "--work-pid", str(work_pid), "--interval-s", "0.04"],
        run_dir,
    )
    if not wait_until(lambda: heartbeat_count(run_dir) >= 2, 5.0):
        _kill(monitor)
        _kill(work)
        raise RuntimeError("monitor did not heartbeat twice")
    work_alive_before_kill = work.poll() is None
    if not work_alive_before_kill:
        _kill(monitor)
        raise RuntimeError("work finished before injection; timing vacuous")

    if kind == "kill-monitor":
        _kill(monitor)
        append_event(
            run_dir,
            {
                "event": "monitor-died",
                "actor": "supervisor",
                "pid": monitor.pid,
                "signal": "SIGKILL",
                "observed_how": "wait after os.kill; monitor did not self-report",
                "work_pid": work_pid,
            },
        )
    else:
        _kill(work)
        append_event(
            run_dir,
            {
                "event": "work-died",
                "actor": "supervisor",
                "pid": work_pid,
                "signal": "SIGKILL",
                "observed_how": "wait after os.kill of worker",
            },
        )
        _kill(monitor)
        append_event(
            run_dir,
            {
                "event": "monitor-died",
                "actor": "supervisor",
                "pid": monitor.pid,
                "signal": "SIGKILL",
                "observed_how": "supervisor stopped monitor after work death so heartbeat stream is also quiet",
                "work_pid": work_pid,
            },
        )

    hb_at_kill = heartbeat_count(run_dir)
    time.sleep(post_kill_silence_s)
    silence_snapshot = {
        "work_alive": work.poll() is None,
        "result_exists": (run_dir / "result.json").is_file(),
        "heartbeat_delta": heartbeat_count(run_dir) - hb_at_kill,
        "event_types": event_types(run_dir),
        "monitor_exit": monitor.poll(),
    }
    work_alive_after_monitor_kill = silence_snapshot["work_alive"] if kind == "kill-monitor" else False

    if kind == "kill-monitor":
        try:
            rc = work.wait(timeout=max(5.0, duration_s + 2.0))
        except subprocess.TimeoutExpired:
            _kill(work)
            raise RuntimeError("work did not finish after monitor death")
        work_exit = rc
    else:
        work_exit = work.poll()
        if work_exit is None:
            _kill(work)
            work_exit = work.poll()

    harvested = harvest(run_dir)
    types = event_types(run_dir)
    return {
        "kind": kind,
        "nonce": nonce,
        "run_dir": str(run_dir),
        "work_pid": work_pid,
        "monitor_pid": monitor.pid,
        "work_alive_before_kill": work_alive_before_kill,
        "work_alive_after_monitor_kill": work_alive_after_monitor_kill,
        "work_exit": work_exit,
        "silence_snapshot": silence_snapshot,
        "event_types": types,
        "events": read_events(run_dir),
        "harvest": harvested,
        "distinct_monitor_and_work_events": (
            "monitor-died" in types and "work-completed" in types and "work-died" not in types
            if kind == "kill-monitor"
            else "monitor-died" in types and "work-died" in types and "work-completed" not in types
        ),
    }


def silence_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Heartbeat+result view only: the ambiguous silence the ledger exists to break."""
    return {
        "heartbeats_stopped": snapshot.get("heartbeat_delta", 1) == 0,
        "result_present": bool(snapshot.get("result_exists")),
        "monitor_quiet": snapshot.get("monitor_exit") is not None,
    }


def typed_view(event_list: list[str]) -> str:
    has_md = "monitor-died" in event_list
    has_wc = "work-completed" in event_list
    has_wd = "work-died" in event_list
    if has_md and has_wc and not has_wd:
        return "monitor-died+work-completed"
    if has_md and has_wd and not has_wc:
        return "monitor-died+work-died"
    if has_wd and not has_wc:
        return "work-died"
    if has_wc and not has_md:
        return "work-completed-without-monitor-death"
    return "ambiguous-silence"


def test_work_survives_monitor_death(result: dict[str, Any]) -> None:
    if result["kind"] != "kill-monitor":
        raise AssertionError("need kill-monitor scenario")
    if not result["work_alive_before_kill"]:
        raise AssertionError("injection was after work already finished")
    if not result["work_alive_after_monitor_kill"]:
        raise AssertionError("work died with the monitor; process-group coupling")
    if result["work_exit"] != 0:
        raise AssertionError(f"work exit {result['work_exit']} after monitor death")
    if "work-completed" not in result["event_types"]:
        raise AssertionError("ledger missing work-completed")


def test_results_are_harvestable_after_monitor_death(result: dict[str, Any]) -> None:
    h = result["harvest"]
    if not h.get("ok"):
        raise AssertionError(f"harvest failed: {h.get('reason')}")
    if h.get("nonce") != result["nonce"]:
        raise AssertionError("harvested nonce does not match live work nonce")
    if h.get("would_redispatch"):
        raise AssertionError("harvester wanted to redispatch completed work")
    if not h.get("has_monitor_died") or not h.get("has_work_completed"):
        raise AssertionError("harvest ledger missing the two distinct events")
    harvested = Path(result["run_dir"]) / "harvested.json"
    if not harvested.is_file():
        raise AssertionError("harvested.json missing")


def test_ledger_distinguishes_monitor_death_from_work_death(
    kill_monitor: dict[str, Any],
    kill_work: dict[str, Any],
) -> None:
    a = typed_view(kill_monitor["event_types"])
    b = typed_view(kill_work["event_types"])
    if a == b:
        raise AssertionError(f"typed views collided: {a}")
    if a != "monitor-died+work-completed":
        raise AssertionError(f"kill-monitor typed view {a}")
    if b != "monitor-died+work-died":
        raise AssertionError(f"kill-work typed view {b}")
    sa = silence_view(kill_monitor["silence_snapshot"])
    sb = silence_view(kill_work["silence_snapshot"])
    if sa != sb:
        raise AssertionError(f"silence views should collide, got {sa} vs {sb}")
    if not sa["heartbeats_stopped"] or sa["result_present"] or not sa["monitor_quiet"]:
        raise AssertionError(f"silence snapshot not actually silent: {sa}")
    if "work-died" in kill_monitor["event_types"]:
        raise AssertionError("kill-monitor ledger also has work-died")
    if "work-completed" in kill_work["event_types"]:
        raise AssertionError("kill-work ledger also has work-completed")
