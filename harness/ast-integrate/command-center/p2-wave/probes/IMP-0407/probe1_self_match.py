#!/usr/bin/env python3
"""Probe 1: self-match control (CreationDate-equals-probe-runtime tell).

Both states:
  * exclude_self=True  -> a process whose cmdline matches the search needle
    and whose start time equals probe runtime MUST be excluded.
  * exclude_self=False -> that same process MUST appear (the detector is not
    vacuously silent).

Surfaces: fixture snapshot pid 9999, plus a live spawned decoy on /proc.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import discover as D  # noqa: E402
import scenario as S  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0407-probe1 {msg}")
    return 1


def _has_creation_tell(exclusions: list[dict], pid: int) -> bool:
    for row in exclusions:
        if int(row["pid"]) == pid:
            return any("creation-date-equals-probe-runtime" in r for r in row["reasons"])
    return False


def _run_fixture(now: datetime) -> int:
    with tempfile.TemporaryDirectory(prefix="imp0407-p1-") as tmp:
        meta = S.build_estate(Path(tmp) / "estate", now=now)
        probe = D.ProbeContext.capture(started_at=now)
        on = D.discover(
            claude_home=Path(meta["claude_home"]),
            codex_home=Path(meta["codex_home"]),
            process_snapshot=meta["snapshot"],
            probe=probe,
            exclude_self=True,
        )
        off = D.discover(
            claude_home=Path(meta["claude_home"]),
            codex_home=Path(meta["codex_home"]),
            process_snapshot=meta["snapshot"],
            probe=probe,
            exclude_self=False,
        )
        self_pid = int(meta["self_pid"])
        on_pids = {int(p["pid"]) for p in on["processes"]}
        off_pids = {int(p["pid"]) for p in off["processes"]}
        if self_pid in on_pids:
            return _fail(f"self pid {self_pid} kept when exclude_self=True")
        if self_pid not in off_pids:
            return _fail(f"self pid {self_pid} missing when exclude_self=False")
        if not _has_creation_tell(on["exclusions"], self_pid):
            return _fail(
                f"pid {self_pid} excluded without creation-date tell: {on['exclusions']}"
            )
        if probe.pid in on_pids:
            return _fail("probe pid appeared in fixture process table")
        print(
            json.dumps(
                {
                    "surface": "fixture-snapshot",
                    "self_pid": self_pid,
                    "excluded_on": True,
                    "present_off": True,
                    "creation_date_tell": True,
                    "exclusion_reasons": on["exclusions"],
                    "process_count_on": on["reconciliation"]["process_table_count"],
                    "process_count_off": off["reconciliation"]["process_table_count"],
                },
                sort_keys=True,
            )
        )
    return 0


def _run_live_decoy(now: datetime) -> int:
    with tempfile.TemporaryDirectory(prefix="imp0407-decoy-") as tmp:
        script = Path(tmp) / "decoy.py"
        script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
        decoy = subprocess.Popen(
            [sys.executable, "-B", str(script), "--search", "claude", "self-match-decoy"],
            cwd=tmp,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.time() + 3
            appeared = False
            while time.time() < deadline:
                live = D.read_live_processes(["claude"])
                if any(p.pid == decoy.pid for p in live):
                    appeared = True
                    break
                time.sleep(0.05)
            if not appeared:
                return _fail(f"live decoy pid={decoy.pid} never matched needle claude")
            probe = D.ProbeContext.capture(started_at=now)
            kept_on, excl_on = D.enumerate_processes(
                snapshot=None,
                needles=["claude"],
                probe=probe,
                exclude_self=True,
            )
            kept_off, _excl_off = D.enumerate_processes(
                snapshot=None,
                needles=["claude"],
                probe=probe,
                exclude_self=False,
            )
            on_pids = {p.pid for p in kept_on}
            off_pids = {p.pid for p in kept_off}
            if decoy.pid in on_pids:
                return _fail(f"live decoy pid={decoy.pid} kept with exclude_self=True")
            if decoy.pid not in off_pids:
                return _fail(f"live decoy pid={decoy.pid} missing with exclude_self=False")
            if os.getpid() in on_pids:
                return _fail("probe pid kept in live process table")
            excl_dicts = [asdict(e) for e in excl_on]
            if not any(e.pid == decoy.pid for e in excl_on):
                return _fail(f"live decoy {decoy.pid} not in exclusions {excl_dicts}")
            print(
                json.dumps(
                    {
                        "surface": "live-/proc",
                        "decoy_pid": decoy.pid,
                        "probe_pid": probe.pid,
                        "excluded_on": True,
                        "present_off": True,
                        "exclusion_reasons": [
                            asdict(e) for e in excl_on if e.pid == decoy.pid
                        ],
                    },
                    sort_keys=True,
                )
            )
        finally:
            decoy.terminate()
            try:
                decoy.wait(timeout=2)
            except subprocess.TimeoutExpired:
                decoy.kill()
                decoy.wait(timeout=2)
    return 0


def main() -> int:
    now = datetime.now(timezone.utc)
    rc = _run_fixture(now)
    if rc != 0:
        return rc
    rc = _run_live_decoy(now)
    if rc != 0:
        return rc
    print("fixture_self_excluded=True live_decoy_excluded=True both_states=True")
    print("SUCCESS:IMP-0407-probe1 self-match exclusion demonstrated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
