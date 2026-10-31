"""Regression suite for MON-crcp-2: board block-buffered under redirection.

The defect: every stdout print in monitor/crcp_health_monitor.py ran without
flush and the persistent loop then entered time.sleep(interval), so a non-tty
stdout (file redirect, pipe, tee/log wrapper of `mon crcp`) held the whole
board in the block buffer for the entire sleep. Measured on the unpatched
module (audit AUDIT-monitors, re-measured here with a stubbed crcp.health):
tick receipt advanced (calls.log written, snippet on disk, process alive in
the sleep) while the stdout capture file held 0 bytes; the identical run with
`python -u` showed 350 bytes including the board. A capture reader therefore
sees silence and can misdiagnose a healthy monitor as hung.

These tests are the anti-regression pin: they run the REAL script as a REAL
subprocess WITHOUT -u (the sibling suite's subprocess helper passes -u, which
bypasses buffering and so cannot see this defect) and assert the bytes reach
a redirected stdout while the process is still alive -- never relying on the
exit-time flush.

Hermetic like the sibling suite: the script is copied next to a throwaway
crcp package, so no probe, credential read or network call runs.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

MONITOR_PATH = (
    Path(__file__).resolve().parents[1] / "monitor" / "crcp_health_monitor.py"
)

RECEIPT_DEADLINE_SEC = 30.0
CAPTURE_DEADLINE_SEC = 10.0

FAST_STUB = '''\
"""Throwaway crcp.health: instant tick, writes a receipt per poll."""

from pathlib import Path

CALLS = Path(__file__).resolve().parents[1] / "calls.log"


def full_health():
    with CALLS.open("a", encoding="ascii") as fh:
        fh.write("tick\\n")
    return {"overall": "GREEN"}


def health_table(report):
    return "BOARD overall=" + report["overall"]


def write_wfmon_snippet(report, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="ascii")
    return path
'''

# The slow stub models the real tick (~5-7s of probes): calls.log marks the
# tick as STARTED, then the probe "runs" for a while before the snippet lands.
SLOW_STUB = FAST_STUB.replace(
    '    return {"overall": "GREEN"}',
    '    import time\n    time.sleep(2.5)\n    return {"overall": "GREEN"}',
)


def _script_tree(tmp_path: Path, stub_source: str) -> Path:
    (tmp_path / "crcp").mkdir()
    (tmp_path / "crcp" / "__init__.py").write_text("", encoding="ascii")
    (tmp_path / "crcp" / "health.py").write_text(stub_source, encoding="ascii")
    (tmp_path / "monitor").mkdir()
    script = tmp_path / "monitor" / "crcp_health_monitor.py"
    script.write_bytes(MONITOR_PATH.read_bytes())
    return script


def _spawn_redirected(script: Path, capture: Path, *args: str) -> subprocess.Popen:
    """Launch the script with stdout REDIRECTED and buffering LEFT ALONE.

    Deliberately no -u and no PYTHONUNBUFFERED: the contract under test is
    that the script itself flushes, because `mon crcp` wrappers do not pass -u.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "PYTHONUNBUFFERED", "CRCP_HEALTH_INTERVAL_SEC"}
    }
    with capture.open("wb") as out:
        return subprocess.Popen(
            [sys.executable, str(script), *args],
            stdout=out,
            stderr=subprocess.DEVNULL,
            env=env,
        )


def _wait_for(predicate, deadline_sec: float, poll_sec: float = 0.05) -> bool:
    deadline = time.monotonic() + deadline_sec
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(poll_sec)
    return predicate()


def _read_capture(capture: Path) -> str:
    return capture.read_text(encoding="ascii", errors="replace")


def test_persistent_board_reaches_a_redirected_stdout_before_the_sleep(tmp_path):
    """The headline MON-crcp-2 guard.

    interval=3600 pins the failure shape: after one tick the process sits in
    time.sleep for an hour, so any board byte the capture receives arrived via
    an explicit flush -- exit-time flushing cannot rescue this test.
    """
    script = _script_tree(tmp_path, FAST_STUB)
    capture = tmp_path / "stdout.capture"
    calls = tmp_path / "calls.log"
    snippet = tmp_path / "reports" / "wfmon_crcp_health.json"

    proc = _spawn_redirected(script, capture, "--interval", "3600")
    try:
        assert _wait_for(
            lambda: calls.is_file() and snippet.is_file(), RECEIPT_DEADLINE_SEC
        ), "tick receipt never appeared; cannot probe buffering"

        board_arrived = _wait_for(
            lambda: "snippet ->" in _read_capture(capture), CAPTURE_DEADLINE_SEC
        )
        assert proc.poll() is None, (
            "monitor exited during the probe; the capture no longer "
            "distinguishes a flush from the interpreter's exit-time flush"
        )
        body = _read_capture(capture)
        assert board_arrived, (
            "MON-crcp-2 regression: tick completed (receipt on disk) but the "
            f"redirected stdout held {capture.stat().st_size} bytes through "
            "the sleep -- the board is block-buffered again"
        )
        assert "BOARD overall=" in body
        assert "snippet ->" in body
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_single_shot_banner_is_visible_while_the_tick_is_still_running(tmp_path):
    """--once prints its banner and then probes for seconds; a tee/log reader
    must see the banner DURING the tick, not after exit."""
    script = _script_tree(tmp_path, SLOW_STUB)
    capture = tmp_path / "stdout.capture"
    calls = tmp_path / "calls.log"
    snippet = tmp_path / "reports" / "wfmon_crcp_health.json"

    proc = _spawn_redirected(script, capture, "--once")
    try:
        assert _wait_for(calls.is_file, RECEIPT_DEADLINE_SEC), (
            "tick never started; cannot probe buffering"
        )

        banner_mid_tick = _wait_for(
            lambda: (
                "single-shot" in _read_capture(capture)
                and not snippet.is_file()
                and proc.poll() is None
            ),
            CAPTURE_DEADLINE_SEC,
        )
        assert banner_mid_tick, (
            "MON-crcp-2 regression: the single-shot banner did not reach the "
            "redirected stdout while the tick was still running "
            f"(capture={_read_capture(capture)!r})"
        )
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_capture_probe_sees_output_when_buffering_is_off(tmp_path):
    """Detector control (both-states rule): the SAME capture path, with -u
    forcing unbuffered stdout, must observe the board. If this fails the two
    tests above are measuring a broken capture pipeline, not buffering."""
    script = _script_tree(tmp_path, FAST_STUB)
    capture = tmp_path / "stdout.capture"
    calls = tmp_path / "calls.log"
    snippet = tmp_path / "reports" / "wfmon_crcp_health.json"

    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "PYTHONUNBUFFERED", "CRCP_HEALTH_INTERVAL_SEC"}
    }
    with capture.open("wb") as out:
        proc = subprocess.Popen(
            [sys.executable, "-u", str(script), "--interval", "3600"],
            stdout=out,
            stderr=subprocess.DEVNULL,
            env=env,
        )
    try:
        assert _wait_for(
            lambda: calls.is_file() and snippet.is_file(), RECEIPT_DEADLINE_SEC
        )
        assert _wait_for(
            lambda: "BOARD overall=" in _read_capture(capture), CAPTURE_DEADLINE_SEC
        ), "control failed: even -u shows nothing, the capture probe is broken"
        assert proc.poll() is None
    finally:
        proc.kill()
        proc.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
