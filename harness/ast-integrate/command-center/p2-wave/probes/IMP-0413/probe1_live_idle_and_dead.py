#!/usr/bin/env python3
"""IMP-0413 probe 1: live-but-idle HOLD, dead-session REAP, both signals named.

A session with a live process and zero artifact byte-growth over a 20-minute
window must keep its claim. A session whose process is gone and whose
artifacts did not grow must be reaped. Every release names both signals
and their values. A one-signal release is refused. mtime cannot enter the
gate.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center" / "lib"))

from orphan_reaper.liveness import (  # noqa: E402
    HOLD,
    IDLE_WINDOW_SECONDS,
    IncompleteReleaseRecord,
    MtimeSignalUnrepresentable,
    NOT_ALIVE,
    REAP,
    SIGNAL_BYTES,
    SIGNAL_PROCESS,
    SignalObservation,
    observe_bytes,
    observe_process,
    proof_of_death,
    validate_release_signals,
)
from orphan_reaper.reaper import (  # noqa: E402
    make_release_record,
    pid_exists,
    plant_both_states,
    reap_tree,
)

ART = REPO / "command-center" / "receipts" / "IMP-0413.json"
SENTINEL = "SENTINEL:IMP-0413:REAPER-PROOF-OF-DEATH"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0413-probe1 {msg}")
    return 1


def spawn_idle() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(90)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def kill(proc: subprocess.Popen) -> int:
    pid = int(proc.pid)
    proc.kill()
    proc.wait(timeout=10)
    return pid


def main() -> int:
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared:{doc.get('state')}")
        if SENTINEL not in text:
            return fail("sentinel-absent")

    live = spawn_idle()
    dead_proc = spawn_idle()
    try:
        if not pid_exists(live.pid):
            return fail(f"live pid {live.pid} not in process table")
        dead_pid = kill(dead_proc)
        if pid_exists(dead_pid):
            return fail(f"dead pid {dead_pid} still in process table")

        with tempfile.TemporaryDirectory(prefix="imp0413-p1-") as tmp:
            root = Path(tmp)
            planted = plant_both_states(
                root, live_pid=int(live.pid), dead_pid=dead_pid
            )
            result = reap_tree(
                planted["claims"],
                planted["leases"],
                releases_dir=planted["releases"],
            )
            claim_files = {p.stem for p in planted["claims"].glob("*.json")}
            lease_files = {p.stem for p in planted["leases"].glob("*.json")}
            release_files = {p.stem for p in planted["releases"].glob("*.json")}

            idle_held = "WU-IDLE" in claim_files and "lease-idle-src" in lease_files
            dead_gone = "WU-DEAD" not in claim_files and "lease-dead-src" not in lease_files
            dead_logged = "claim-WU-DEAD" in release_files and "lease-dead-src" in {
                p.stem.replace("lease-", "", 1) if p.stem.startswith("lease-") else p.stem
                for p in planted["releases"].glob("*.json")
            }
            # Direct check of release files we wrote.
            claim_rel = planted["releases"] / "claim-WU-DEAD.json"
            lease_rel = planted["releases"] / "lease-lease-dead-src.json"
            if not claim_rel.is_file() or not lease_rel.is_file():
                return fail(
                    f"dead releases missing claim={claim_rel.is_file()} "
                    f"lease={lease_rel.is_file()} files={sorted(release_files)}"
                )

            idle_event = next(
                e
                for e in result.events
                if e.kind == "claim" and e.target_id == "WU-IDLE"
            )
            dead_event = next(
                e
                for e in result.events
                if e.kind == "claim" and e.target_id == "WU-DEAD"
            )
            if idle_event.action != HOLD or idle_event.report.death_proven:
                return fail(f"live-but-idle reaped: {idle_event.to_dict()}")
            if dead_event.action != REAP or not dead_event.report.death_proven:
                return fail(f"dead session held: {dead_event.to_dict()}")
            if not idle_held:
                return fail(f"idle files missing after reap {claim_files} {lease_files}")
            if not dead_gone:
                return fail(f"dead files still present {claim_files} {lease_files}")

            for rel_path in (claim_rel, lease_rel):
                rec = json.loads(rel_path.read_text(encoding="utf-8"))
                names = [s.get("name") for s in rec.get("signals") or []]
                if rec.get("signal_count") != 2:
                    return fail(f"release signal_count {rec.get('signal_count')}")
                if set(names) != {SIGNAL_PROCESS, SIGNAL_BYTES}:
                    return fail(f"release signals {names}")
                by_name = {s["name"]: s for s in rec["signals"]}
                proc = by_name[SIGNAL_PROCESS]
                growth = by_name[SIGNAL_BYTES]
                if proc.get("verdict") != NOT_ALIVE or proc.get("pid_exists") is not False:
                    return fail(f"process signal on dead release {proc}")
                if "cpu_delta_ns" not in proc:
                    return fail("process signal missing cpu_delta_ns")
                if growth.get("verdict") != NOT_ALIVE or growth.get("delta") != 0:
                    return fail(f"byte signal on dead release {growth}")
                if "bytes_t0" not in growth or "bytes_t1" not in growth:
                    return fail("byte signal missing values")

            # Independent OS check: idle pid still live after reap.
            if not pid_exists(int(live.pid)):
                return fail("idle pid died during probe; control collapsed")

            # One-signal release is a defect.
            one = (observe_bytes(bytes_t0=1, bytes_t1=1),)
            try:
                validate_release_signals(one)
            except IncompleteReleaseRecord:
                one_refused = True
            else:
                return fail("one-signal release accepted")

            try:
                make_release_record(
                    kind="claim",
                    target_id="WU-FORGED",
                    session_id="sess-forged",
                    path="forged",
                    report=idle_event.report,
                )
            except IncompleteReleaseRecord:
                hold_release_refused = True
            else:
                return fail("HOLD liveness produced a release record")

            try:
                proof_of_death(
                    (
                        observe_process(pid_exists=True, cpu_delta_ns=0),
                        SignalObservation(
                            name="mtime",
                            verdict=NOT_ALIVE,
                            values={"st_mtime": 1},
                        ),
                    )
                )
                return fail("mtime signal accepted")
            except MtimeSignalUnrepresentable:
                mtime_refused = True

            idle_signals = idle_event.report.signals
            proc_idle = next(s for s in idle_signals if s.name == SIGNAL_PROCESS)
            bytes_idle = next(s for s in idle_signals if s.name == SIGNAL_BYTES)
            if proc_idle.verdict != "ALIVE" or bytes_idle.verdict != NOT_ALIVE:
                return fail(
                    f"idle mixed signals missing process={proc_idle.verdict} "
                    f"bytes={bytes_idle.verdict}"
                )
            if idle_event.report.window_seconds != IDLE_WINDOW_SECONDS:
                return fail(f"window {idle_event.report.window_seconds}")

            payload = {
                "pass": True,
                "probe": "probe1-live-idle-and-dead",
                "unit_id": "IMP-0413",
                "live_pid": int(live.pid),
                "dead_pid": dead_pid,
                "live_pid_exists": True,
                "dead_pid_exists": False,
                "idle_held": True,
                "dead_reaped": True,
                "idle_claim_present": True,
                "dead_claim_present": False,
                "release_signal_names": [SIGNAL_PROCESS, SIGNAL_BYTES],
                "release_signal_count": 2,
                "one_signal_release_refused": one_refused,
                "hold_cannot_emit_release": hold_release_refused,
                "mtime_refused": mtime_refused,
                "window_seconds": IDLE_WINDOW_SECONDS,
                "released_count": result.to_dict()["released_count"],
                "held_count": result.to_dict()["held_count"],
            }
            print(json.dumps(payload, sort_keys=True))
            print(
                f"idle_held=True dead_reaped=True signals={SIGNAL_PROCESS}+{SIGNAL_BYTES} "
                f"window={IDLE_WINDOW_SECONDS}s live_pid={live.pid} dead_pid={dead_pid}"
            )
            print("SUCCESS:IMP-0413-probe1 live-but-idle held; dead reaped")
            return 0
    finally:
        if live.poll() is None:
            live.kill()
            live.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
