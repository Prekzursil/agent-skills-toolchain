#!/usr/bin/env python3
"""Reusable CNF-0186 scenarios (imported by named probes and emit_receipt)."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WATCHDOG = HERE / "watchdog.py"
CLASSIFICATIONS = HERE / "fixtures/classifications.json"
FIXTURES = HERE / "fixtures/packages"

sys.path.insert(0, str(HERE))
import interpret as I  # noqa: E402
import watchdog as W  # noqa: E402


def materialize(dest: Path, names: list[str]) -> Path:
    packages = dest / "packages"
    if packages.exists():
        shutil.rmtree(packages)
    packages.mkdir(parents=True)
    for name in names:
        src = FIXTURES / name
        shutil.copytree(src, packages / name)
    return packages


def run_cli(
    packages_dir: Path,
    state_dir: Path,
    date: str,
    *,
    timeout_sec: float = 15.0,
) -> tuple[int, str, str]:
    cmd = [
        sys.executable,
        "-B",
        str(WATCHDOG),
        "--packages-dir",
        str(packages_dir),
        "--state-dir",
        str(state_dir),
        "--date",
        date,
        "--classifications",
        str(CLASSIFICATIONS),
        "--timeout-sec",
        str(timeout_sec),
    ]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def scenario_both_states_and_known_broken(tmp: Path) -> dict[str, Any]:
    packages = materialize(tmp, ["pkg-healthy", "pkg-widget"])
    state = tmp / "state"
    day1 = "2026-08-20"
    day2 = "2026-08-21"
    day3 = "2026-08-22"
    rc1, out1, _err1 = run_cli(packages, state, day1)
    lines1 = [ln for ln in out1.splitlines() if ln.strip()]
    want_green = ["SUCCESS:pkg-healthy", "SUCCESS:pkg-widget"]
    both_states_ok = rc1 == 0 and lines1 == want_green

    pins = packages / "pkg-widget" / "pins.json"
    pins.write_text(json.dumps({"widget": "9.9.9"}, indent=1) + "\n", encoding="utf-8")
    rc2, out2, _err2 = run_cli(packages, state, day2)
    lines2 = [ln for ln in out2.splitlines() if ln.strip()]
    widget_fail = any(
        ln.startswith("FAILED:pkg-widget") and "pin-mismatch" in ln for ln in lines2
    )
    healthy_still = "SUCCESS:pkg-healthy" in lines2
    known_broken_ok = rc2 != 0 and widget_fail and healthy_still

    st = json.loads((state / "packages" / "pkg-widget.json").read_text(encoding="utf-8"))
    first = st.get("first_fail_day")
    rc3, out3, _err3 = run_cli(packages, state, day3)
    st3 = json.loads((state / "packages" / "pkg-widget.json").read_text(encoding="utf-8"))
    first_held = first == day2 and st3.get("first_fail_day") == day2
    still_failed = any(ln.startswith("FAILED:pkg-widget") for ln in out3.splitlines())

    return {
        "both_states_ok": both_states_ok,
        "known_broken_ok": known_broken_ok,
        "first_fail_day": first,
        "first_fail_held_on_later_day": first_held,
        "still_failed_day3": still_failed,
        "day1": {"rc": rc1, "stdout": out1, "lines": lines1},
        "day2": {"rc": rc2, "stdout": out2, "lines": lines2},
        "day3": {"rc": rc3, "stdout": out3},
        "pass": both_states_ok and known_broken_ok and first_held and still_failed,
    }


def scenario_attribution(tmp: Path) -> dict[str, Any]:
    packages = materialize(tmp, ["pkg-widget"])
    state = tmp / "state"
    _rc1, out1, _ = run_cli(packages, state, "2026-08-20")
    st = json.loads((state / "packages" / "pkg-widget.json").read_text(encoding="utf-8"))
    stored_canonical = st["last_green"]["environment_fingerprint_canonical"]
    stored_fp = json.loads(stored_canonical)
    stored_pin = stored_fp["pins_sha256"]

    pins = packages / "pkg-widget" / "pins.json"
    pins.write_text(json.dumps({"widget": "9.9.9"}) + "\n", encoding="utf-8")
    _rc2, out2, _ = run_cli(packages, state, "2026-08-21")
    st2 = json.loads((state / "packages" / "pkg-widget.json").read_text(encoding="utf-8"))
    last = st2["last_run"]
    delta = last["env_delta_vs_last_green"]
    changed = (delta.get("changed") or {}).get("pins_sha256") or {}
    from_stored = (
        delta.get("source") == "stored-canonical-bytes"
        and changed.get("before") == stored_pin
        and changed.get("after")
        and changed.get("before") != changed.get("after")
    )

    current_fp = W.capture_fingerprint(packages / "pkg-widget")
    planted = dict(stored_fp)
    planted["pins_sha256"] = "0" * 64
    planted_canonical = W.canonical_json(planted)
    planted_delta = W.env_delta(planted_canonical, current_fp)
    planted_before = ((planted_delta.get("changed") or {}).get("pins_sha256") or {}).get(
        "before"
    )
    reconstructed_would_match = planted_before == current_fp["pins_sha256"]
    planted_ok = planted_before == "0" * 64 and not reconstructed_would_match

    return {
        "green_stdout": out1,
        "fail_stdout": out2,
        "from_stored_bytes": from_stored,
        "planted_stored_fingerprint_honored": planted_ok,
        "delta": delta,
        "planted_delta": planted_delta,
        "pass": from_stored and planted_ok and "FAILED:pkg-widget" in out2,
    }


def scenario_silence(tmp: Path) -> dict[str, Any]:
    empty = I.adjudicate("", ["pkg-healthy", "pkg-widget"])
    silence_ok = (
        empty["silence"] is True
        and empty["overall"] == "FAILED"
        and empty["packages"]["pkg-healthy"]["reason"] == "silence"
        and empty["packages"]["pkg-widget"]["reason"] == "silence"
        and not any(p["status"] == "SUCCESS" for p in empty["packages"].values())
    )
    missing = I.missing_run(tmp / "empty-state", "1999-01-01", ["pkg-healthy"])
    missing_ok = (
        missing.get("missing_run") is True
        and missing["overall"] == "FAILED"
        and missing["packages"]["pkg-healthy"]["reason"] == "missing-run"
    )
    return {
        "silence_ok": silence_ok,
        "missing_run_ok": missing_ok,
        "empty_adjudication": empty,
        "missing_adjudication": missing,
        "pass": silence_ok and missing_ok,
    }


def scenario_kill_mid_run(tmp: Path) -> dict[str, Any]:
    packages = materialize(tmp, ["pkg-healthy", "pkg-sleepy"])
    state = tmp / "state"
    date = "2026-08-24"
    cmd = [
        sys.executable,
        "-B",
        str(WATCHDOG),
        "--packages-dir",
        str(packages),
        "--state-dir",
        str(state),
        "--date",
        date,
        "--classifications",
        str(CLASSIFICATIONS),
        "--timeout-sec",
        "40",
    ]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    )
    time.sleep(0.7)
    killed = False
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        killed = True
    except ProcessLookupError:
        killed = False
    stdout = ""
    stderr = ""
    try:
        stdout, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate(timeout=5)
    adj = I.incomplete_kill(stdout or "", ["pkg-healthy", "pkg-sleepy"], state, date)
    sleepy = adj["packages"]["pkg-sleepy"]
    sleepy_not_success = sleepy["status"] != "SUCCESS"
    overall_failed = adj["overall"] == "FAILED"
    return {
        "killed": killed,
        "stdout": stdout,
        "stderr_tail": (stderr or "")[-500:],
        "adjudication": adj,
        "sleepy_not_success": sleepy_not_success,
        "overall_failed": overall_failed,
        "run_complete": adj.get("run_complete"),
        "pass": killed and sleepy_not_success and overall_failed,
    }
