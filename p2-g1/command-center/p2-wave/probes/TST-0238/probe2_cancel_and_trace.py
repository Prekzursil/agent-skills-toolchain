#!/usr/bin/env python3
"""TST-0238 probe 2: a cancelled slow render still spends spawn budget, and
the spawns are confirmed by an OS-level process enumeration.

  * slow render + cancel_ms: renderer answers CANCELLED, shim counted 1
    spawn (the spawn happened BEFORE the cancel decision);
  * slow render without cancel: RENDERED-SLOW, shim counted 2 spawns, so
    the uncancelled render spends strictly more than the cancelled one;
  * OS trace: an injected sleeper.exe (8s lifetime) is observed LIVE by a
    Get-CimInstance Win32_Process enumeration while the render runs, with
    its ExecutablePath verified against the shim directory - independent
    of the shim log file;
  * strace tie-in: spawn_measure's clone counter (documented Windows
    adaptation) moves with the injected spawn.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import shim_exe  # noqa: E402
from hud import spawn_measure  # noqa: E402

PAYLOAD = HERE / "fixtures" / "payload.json"
OS_TOKEN = shim_exe.OS_TOKEN


def cim_find_shim(shim_dir) -> list[int]:
    """OS-level enumeration of sleeper.exe processes under shim_dir."""
    q = (
        "Get-CimInstance Win32_Process -Filter \"Name='sleeper.exe'\" | "
        "Select-Object ProcessId,ExecutablePath | ConvertTo-Json"
    )
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", q], capture_output=True, text=True, timeout=60
    )
    rows = json.loads(r.stdout) if r.stdout.strip() else []
    if isinstance(rows, dict):
        rows = [rows]
    return [
        int(row["ProcessId"])
        for row in rows
        if str(row.get("ExecutablePath", "")).lower().startswith(str(shim_dir).lower())
    ]


def kill_pids(pids: list[int]) -> None:
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


def main() -> int:
    checks: dict[str, bool] = {}
    sleeper_pids: list[int] = []
    with tempfile.TemporaryDirectory(prefix="tst0238-probe2-") as td:
        built = shim_exe.compile_shims(Path(td))
        checks["shim_exe_compiled"] = built["ok"] is True
        if not built["ok"]:
            print(json.dumps({"probe": "probe2-cancel-and-trace", "unit_id": "TST-0238",
                              "checks": checks, "pass": False, "reason": built["reason"]}))
            return 1
        shim_dir: Path = built["shim_dir"]
        log_path = Path(td) / "spawn-log.txt"
        log_path.write_text("", encoding="utf-8")
        # the shims locate the log through their inherited environment
        os.environ["TST0238_SHIM_LOG"] = str(log_path)

        # 1. slow render that IS cancelled: CANCELLED, one spawn spent.
        cancelled = spawn_measure.run_statusline(
            REPO,
            extra_args=["--payload", PAYLOAD.as_posix(), "--slow", "--cancel-ms", "200"],
            shim_dir=shim_dir, log_path=log_path,
        )
        checks["cancel_render_exit_zero"] = cancelled["exit_code"] == 0
        checks["cancel_stdout_says_cancelled"] = "CANCELLED" in cancelled["stdout"]
        checks["cancel_spent_one_spawn"] = cancelled["shim_count"] == 1

        log_path.write_text("", encoding="utf-8")
        # 2. slow render NOT cancelled: two spawns.
        full = spawn_measure.run_statusline(
            REPO,
            extra_args=["--payload", PAYLOAD.as_posix(), "--slow", "--no-cancel"],
            shim_dir=shim_dir, log_path=log_path,
        )
        checks["uncancelled_render_exit_zero"] = full["exit_code"] == 0
        checks["uncancelled_stdout_rendered_slow"] = "RENDERED-SLOW" in full["stdout"]
        checks["uncancelled_spent_two_spawns"] = full["shim_count"] == 2
        checks["uncancelled_exceeds_cancelled"] = full["shim_count"] > cancelled["shim_count"]
        log_path.write_text("", encoding="utf-8")

        # 3. OS-level trace: watch the render spawn a live sleeper.exe.
        env = shim_exe.shim_env(shim_dir, log_path)
        log_path.write_text("", encoding="utf-8")
        render_cmd = [
            sys.executable, "-B", str(REPO / "tools" / "hud" / "statusline.py"),
            "--payload", str(PAYLOAD), "--inject-spawn", "sleeper",
        ]
        proc = subprocess.Popen(
            render_cmd, cwd=str(REPO), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        deadline = time.time() + 10
        while time.time() < deadline:
            sleeper_pids = cim_find_shim(shim_dir)
            if sleeper_pids:
                break
            if proc.poll() is not None:
                break
            time.sleep(0.3)
        checks["os_process_enumeration_finds_spawned_child"] = len(sleeper_pids) >= 1
        out_s, err_s = proc.communicate(timeout=60)
        checks["trace_render_exit_zero"] = proc.returncode == 0
        log_names = [ln.strip() for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        checks["trace_shim_count_one"] = len(log_names) == 1
        checks["trace_shim_names_sleeper"] = log_names == ["sleeper"]

        # 4. strace tie-in: the production module's clone counter moves too
        #    (documented adaptation ties clones to the injected `true`).
        log_path.write_text("", encoding="utf-8")
        traced = spawn_measure.run_statusline(
            REPO,
            extra_args=["--payload", PAYLOAD.as_posix(), "--inject-spawn", "true"],
            shim_dir=shim_dir, log_path=log_path,
        )
        checks["strace_clone_count_tracks_spawn"] = (
            traced["strace"].get("process_clones") == traced["shim_count"] == 1
        )
        if sleeper_pids:
            for pid in sleeper_pids:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)

    os.environ.pop("TST0238_SHIM_LOG", None)
    ok = all(v for v in checks.values() if isinstance(v, bool))
    out = {
        "probe": "probe2-cancel-and-trace",
        "unit_id": "TST-0238",
        "subject": "tools/hud/statusline.py",
        "os_trace_method": "Get-CimInstance Win32_Process enumeration of the live sleeper.exe (path-verified against the shim dir)",
        "os_token": OS_TOKEN,
        "cancel_ms": 200,
        "slow_cancelled_shim_count": cancelled["shim_count"],
        "slow_uncancelled_shim_count": full["shim_count"],
        "cancelled_stdout": cancelled["stdout"][:80],
        "uncancelled_stdout": full["stdout"][:80],
        "traced_shim_names": traced["shim_names"],
        "os_trace_pids_seen": sleeper_pids,
        "strace": traced["strace"],
        "checks": checks,
        "pass": ok,
    }
    (HERE / "probe2_cancel_and_trace.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    if sleeper_pids:
        kill_pids(sleeper_pids)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
