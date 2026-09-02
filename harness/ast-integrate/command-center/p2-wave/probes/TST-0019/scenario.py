#!/usr/bin/env python3
"""Live self-match reproduction and both-states pair for TST-0019."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import session_probe as SP  # noqa: E402


@dataclass
class BothStatesPair:
    """TST-0013-shaped pair: silent on good, fires on broken."""

    silent_on_good: bool
    fires_on_bad: bool
    ok: bool
    good_output: Any
    bad_output: Any


def _fired(output: Any) -> bool:
    if output is None:
        return False
    if isinstance(output, (list, tuple, dict, set, str)):
        return len(output) > 0
    return bool(output)


def run_both_states(check, good_state, broken_state) -> BothStatesPair:
    """(check, good, broken): SILENT on good, FIRES on broken."""
    good_output = check(good_state)
    bad_output = check(broken_state)
    silent_on_good = not _fired(good_output)
    fires_on_bad = _fired(bad_output)
    return BothStatesPair(
        silent_on_good=silent_on_good,
        fires_on_bad=fires_on_bad,
        ok=silent_on_good and fires_on_bad,
        good_output=good_output,
        bad_output=bad_output,
    )

MARKER = SP.MARKER
DECOY = HERE / "fixtures" / "decoy_session.py"
WIN32_DEAD = HERE / "fixtures" / "win32_dead_session.json"
WIN32_LIVE = HERE / "fixtures" / "win32_live_session.json"
PYTHON = sys.executable


def _kill(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def cleanup_decoys() -> None:
    for proc in SP.list_processes():
        cl = proc.get("cmdline") or ""
        if MARKER in cl and "decoy_session.py" in cl:
            _kill(int(proc["pid"]))


def spawn_decoy() -> subprocess.Popen:
    return subprocess.Popen(
        [PYTHON, "-B", str(DECOY), MARKER],
        cwd=str(REPO),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def wait_decoy_alive(pid: int, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if Path(f"/proc/{pid}").exists() and MARKER in SP.read_cmdline(pid):
            return
        time.sleep(0.02)
    raise RuntimeError(f"decoy pid={pid} did not appear in /proc")


def run_scanner(mode: str) -> dict[str, Any]:
    cmd = [
        PYTHON,
        "-B",
        str(HERE / "session_probe.py"),
        "scan",
        "--pattern",
        MARKER,
        "--mode",
        mode,
    ]
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if p.returncode != 0:
        raise RuntimeError(
            f"scanner {mode} exit={p.returncode} stderr={p.stderr[-1500:]}"
        )
    doc = json.loads(p.stdout)
    if not isinstance(doc, dict):
        raise RuntimeError("scanner returned non-object")
    return doc


def run_scanner_distinct_from(decoy_pid: int, mode: str) -> dict[str, Any]:
    decoy_ticks = SP.read_start_ticks(decoy_pid)
    last: dict[str, Any] | None = None
    for _ in range(25):
        last = run_scanner(mode)
        if decoy_ticks is None:
            return last
        if str(decoy_ticks) != str(last.get("probe_start_key") or ""):
            return last
        time.sleep(0.05)
    assert last is not None
    return last


def _self_rows(scan: dict[str, Any]) -> list[dict[str, Any]]:
    pid = int(scan["probe_pid"])
    key = str(scan.get("probe_start_key") or "")
    return [m for m in (scan.get("matches") or []) if SP.is_self(m, pid, key)]


def run_live() -> dict[str, Any]:
    cleanup_decoys()
    before = run_scanner("unguarded")
    self_before = _self_rows(before)
    if not self_before:
        raise RuntimeError(
            "unguarded scan did not match the probing process; "
            "self-match was not reproduced"
        )
    tell_row = self_before[0]
    if str(tell_row.get("start_key") or "") != str(before.get("probe_start_key") or ""):
        raise RuntimeError("self-match tell missing: start_key != probe_start_key")

    decoy = spawn_decoy()
    decoy_pid = int(decoy.pid)
    try:
        wait_decoy_alive(decoy_pid)
        time.sleep(0.05)
        after = run_scanner_distinct_from(decoy_pid, "guarded")
        unguarded_with = run_scanner_distinct_from(decoy_pid, "unguarded")
    finally:
        _kill(decoy_pid)
        try:
            decoy.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _kill(decoy_pid)
        cleanup_decoys()

    self_after = _self_rows(after)
    decoy_guarded = [
        m for m in (after.get("matches") or []) if int(m["pid"]) == decoy_pid
    ]
    decoy_unguarded = [
        m
        for m in (unguarded_with.get("matches") or [])
        if int(m["pid"]) == decoy_pid
    ]
    if self_after:
        raise RuntimeError(
            f"guarded scan still listed probe pid={after['probe_pid']}"
        )
    if not decoy_guarded:
        raise RuntimeError(f"guarded scan missed genuine decoy pid={decoy_pid}")
    if not decoy_unguarded:
        raise RuntimeError("unguarded scan missed decoy; pattern plant is inert")

    dead = SP.load_fixture(WIN32_DEAD)
    live = SP.load_fixture(WIN32_LIVE)
    win_ung = SP.scan_snapshot(dead, guarded=False)
    win_g = SP.scan_snapshot(dead, guarded=True)
    win_live = SP.scan_snapshot(live, guarded=True)
    genuine_pid = 1001
    if not win_ung.get("self_match"):
        raise RuntimeError("Win32 dead-session fixture did not self-match unguarded")
    if win_g.get("self_match") or win_g.get("matches"):
        raise RuntimeError("Win32 guard failed on dead-session fixture")
    live_pids = [int(m["pid"]) for m in win_live.get("matches") or []]
    if genuine_pid not in live_pids:
        raise RuntimeError("Win32 guard dropped the genuine earlier session")
    if 4242 in live_pids:
        raise RuntimeError("Win32 guard kept the probe pid")

    return {
        "before": before,
        "after": after,
        "unguarded_with_decoy": unguarded_with,
        "decoy_pid": decoy_pid,
        "before_probe_pid": int(before["probe_pid"]),
        "after_probe_pid": int(after["probe_pid"]),
        "self_before": self_before,
        "self_after": self_after,
        "decoy_guarded": decoy_guarded,
        "win32_dead_unguarded": win_ung,
        "win32_dead_guarded": win_g,
        "win32_live_guarded": win_live,
        "tell": {
            "reported_pid": tell_row["pid"],
            "reported_start_key": tell_row.get("start_key"),
            "probe_start_key": before.get("probe_start_key"),
            "probe_creation_date": before.get("probe_creation_date"),
            "reported_creation_date": tell_row.get("creation_date"),
        },
    }


def test_probe_excludes_own_pid() -> dict[str, Any]:
    live = run_live()
    ok = (
        bool(live["self_before"])
        and not live["self_after"]
        and int(live["before_probe_pid"]) == int(live["self_before"][0]["pid"])
    )
    return {
        "id": "test_probe_excludes_own_pid",
        "ok": ok,
        "before_probe_pid": live["before_probe_pid"],
        "after_probe_pid": live["after_probe_pid"],
        "self_before_pids": [r["pid"] for r in live["self_before"]],
        "self_after_pids": [r["pid"] for r in live["self_after"]],
        "tell": live["tell"],
    }


def test_probe_still_finds_a_genuinely_running_process() -> dict[str, Any]:
    live = run_live()
    dead = SP.load_fixture(WIN32_DEAD)
    present = SP.load_fixture(WIN32_LIVE)

    def presence_detector(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        return SP.scan_snapshot(snapshot, guarded=True)["matches"]

    pair = run_both_states(presence_detector, dead, present)
    decoy_found = bool(live["decoy_guarded"])
    ok = bool(pair.ok) and decoy_found
    return {
        "id": "test_probe_still_finds_a_genuinely_running_process",
        "ok": ok,
        "decoy_pid": live["decoy_pid"],
        "decoy_found_guarded": decoy_found,
        "harness_ok": pair.ok,
        "silent_on_good": pair.silent_on_good,
        "fires_on_bad": pair.fires_on_bad,
        "good_match_pids": [m["pid"] for m in (pair.good_output or [])],
        "bad_match_pids": [m["pid"] for m in (pair.bad_output or [])],
        "after_probe_pid": live["after_probe_pid"],
    }


def self_match_both_states() -> dict[str, Any]:
    dead = SP.load_fixture(WIN32_DEAD)

    def detector(mode: str) -> list[dict[str, Any]]:
        scan = SP.scan_snapshot(dead, guarded=(mode == "guarded"))
        pid = int(scan["probe_pid"])
        key = str(scan.get("probe_start_key") or "")
        return [m for m in scan["matches"] if SP.is_self(m, pid, key)]

    pair = run_both_states(detector, "guarded", "unguarded")
    live = run_live()
    live_ok = bool(live["self_before"]) and not live["self_after"]
    return {
        "harness_ok": pair.ok,
        "silent_on_good": pair.silent_on_good,
        "fires_on_bad": pair.fires_on_bad,
        "live_ok": live_ok,
        "ok": bool(pair.ok) and live_ok,
        "before_probe_pid": live["before_probe_pid"],
        "after_probe_pid": live["after_probe_pid"],
        "decoy_pid": live["decoy_pid"],
        "live": live,
    }
