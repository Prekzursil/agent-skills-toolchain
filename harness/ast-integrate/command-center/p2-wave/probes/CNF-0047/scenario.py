#!/usr/bin/env python3
"""Construct CNF-0047 states and run both monitors (orchestrator + mtime-only)."""
from __future__ import annotations

import os
import signal
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import monitor as M  # noqa: E402
import mtime_only as MT  # noqa: E402
import orchestrator as O  # noqa: E402

ELEVEN_H = 11 * 3600


def _source_audit(path: Path) -> dict:
    """Reject age-from-stat tokens without storing them as literals here."""
    text = path.read_text(encoding="utf-8")
    tokens = [
        "st_" + "mtime",
        "get" + "mtime",
        "os.path.get" + "mtime",
        "stat().st_" + "mtime",
    ]
    hits = [tok for tok in tokens if tok in text]
    return {"path": str(path), "banned_hits": hits, "clean": not hits}


def _backdate(path: Path, age_s: float = ELEVEN_H) -> None:
    ts = time.time() - age_s
    os.utime(path, (ts, ts))


def constructed_pair(root: Path | None = None) -> dict:
    """Kill mid-write vs clean finish, then equalize 11-hour-old mtimes."""
    tmp = Path(tempfile.mkdtemp(prefix="cnf0047-pair-")) if root is None else root
    tmp.mkdir(parents=True, exist_ok=True)
    ledger = tmp / "orchestrator.jsonl"
    killed_art = tmp / "killed" / "out.bin"
    finished_art = tmp / "finished" / "out.bin"
    killed_art.parent.mkdir(parents=True, exist_ok=True)
    finished_art.parent.mkdir(parents=True, exist_ok=True)

    kproc = O.spawn_worker(["write-forever", str(killed_art)])
    O.append(
        ledger,
        {"event": "spawn", "unit_id": "killed-mid-write", "pid": kproc.pid},
    )
    if not O.wait_bytes(killed_art, 8192):
        O.kill_pid(kproc.pid)
        raise RuntimeError("killed-mid-write worker did not produce bytes")
    O.kill_pid(kproc.pid, signal.SIGKILL)
    kproc.wait(timeout=5)
    # No terminal record — that is the stall/kill-mid-write tell.

    fproc = O.spawn_worker(["write-complete", str(finished_art)])
    O.append(
        ledger,
        {"event": "spawn", "unit_id": "finished-clean", "pid": fproc.pid},
    )
    rc = O.wait_exit(fproc, timeout_s=45.0)
    if rc != 0 or not finished_art.is_file():
        O.kill_pid(fproc.pid)
        raise RuntimeError(f"finished-clean worker failed rc={rc}")
    O.append(
        ledger,
        {
            "event": "terminal",
            "unit_id": "finished-clean",
            "pid": fproc.pid,
            "exit_code": rc,
            "reason": "clean-complete",
        },
    )

    # Estate regression: an 11-hour-old finish read as a live stall from mtime.
    _backdate(killed_art)
    _backdate(finished_art)

    mon_k = M.classify(
        unit_id="killed-mid-write",
        ledger=ledger,
        artifact=killed_art,
        sample_s=0.2,
    )
    mon_f = M.classify(
        unit_id="finished-clean",
        ledger=ledger,
        artifact=finished_art,
        sample_s=0.2,
    )
    mt_k = MT.classify_mtime_only(killed_art)
    mt_f = MT.classify_mtime_only(finished_art)

    src_audit = _source_audit(HERE / "monitor.py")
    different = mon_k["verdict"] != mon_f["verdict"]
    mtime_same = mt_k["verdict"] == mt_f["verdict"]
    return {
        "tmp": str(tmp),
        "ledger": str(ledger),
        "killed": {
            "truth": "killed-mid-write",
            "artifact": str(killed_art),
            "bytes": killed_art.stat().st_size,
            "complete_trailer": killed_art.read_bytes().endswith(M.COMPLETE),
            "pid_alive": O.pid_alive(kproc.pid),
            "monitor": mon_k,
            "mtime_only": mt_k,
        },
        "finished": {
            "truth": "finished-clean",
            "artifact": str(finished_art),
            "bytes": finished_art.stat().st_size,
            "complete_trailer": finished_art.read_bytes().endswith(M.COMPLETE),
            "pid_alive": O.pid_alive(fproc.pid),
            "monitor": mon_f,
            "mtime_only": mt_f,
        },
        "mtime_equalized_11h": True,
        "states_report_differently": different,
        "mtime_only_indistinguishable": mtime_same,
        "mtime_source_audit": src_audit,
        "pass": (
            different
            and mtime_same
            and mon_k["verdict"] == "KILLED_MID_WRITE"
            and mon_f["verdict"] == "FINISHED"
            and not mon_k["mtime_used"]
            and not mon_f["mtime_used"]
            and src_audit["clean"]
            and mt_k["verdict"] == "STALLED"
            and mt_f["verdict"] == "STALLED"
        ),
    }


def harvest_after_monitor_death(root: Path | None = None) -> dict:
    import subprocess

    tmp = Path(tempfile.mkdtemp(prefix="cnf0047-harvest-")) if root is None else root
    tmp.mkdir(parents=True, exist_ok=True)
    ledger = tmp / "harvest.jsonl"
    artifact = tmp / "remote" / "out.bin"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    status = tmp / "monitor-status.json"
    unit_id = "remote-continues"

    rproc = O.spawn_worker(
        ["harvest-remote", str(ledger), str(artifact), unit_id, "0.55"]
    )
    poller = subprocess.Popen(
        [
            sys.executable,
            "-B",
            str(HERE / "poller.py"),
            str(ledger),
            str(artifact),
            unit_id,
            str(status),
        ],
        cwd=str(HERE),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    time.sleep(0.15)
    O.kill_pid(poller.pid, signal.SIGKILL)
    try:
        poller.wait(timeout=5)
    except subprocess.TimeoutExpired:
        O.kill_pid(poller.pid, signal.SIGKILL)
    monitor_dead = not O.pid_alive(poller.pid)
    rc = O.wait_exit(rproc, timeout_s=45.0)
    remote_continued = rc == 0
    rows = M.load_ledger(ledger)
    terminal = [r for r in rows if r.get("event") == "terminal"]
    harvested = M.classify(
        unit_id=unit_id,
        ledger=ledger,
        artifact=artifact,
        sample_s=0.15,
    )
    recovered = harvested["verdict"] == "FINISHED" and bool(terminal)
    return {
        "tmp": str(tmp),
        "monitor_killed": monitor_dead,
        "remote_continued": remote_continued,
        "remote_exit": rc,
        "terminal_in_durable_ledger": bool(terminal),
        "harvest_verdict": harvested,
        "harvested": recovered,
        "pass": monitor_dead and remote_continued and recovered,
    }


def idle_alive(root: Path | None = None) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="cnf0047-idle-")) if root is None else root
    tmp.mkdir(parents=True, exist_ok=True)
    ledger = tmp / "orchestrator.jsonl"
    artifact = tmp / "idle" / "out.bin"
    hb = tmp / "idle" / "heartbeat.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    proc = O.spawn_worker(["idle-heartbeat", str(artifact), str(hb)])
    O.append(ledger, {"event": "spawn", "unit_id": "idle-no-write", "pid": proc.pid})
    if not O.wait_bytes(artifact, 1):
        O.kill_pid(proc.pid)
        raise RuntimeError("idle worker did not start")
    size0 = artifact.stat().st_size
    time.sleep(0.55)
    size1 = artifact.stat().st_size
    # Backdate the work file so mtime-only would call it STALLED/DEAD.
    _backdate(artifact)
    mon = M.classify(
        unit_id="idle-no-write",
        ledger=ledger,
        artifact=artifact,
        heartbeat=hb,
        sample_s=0.25,
    )
    mt = MT.classify_mtime_only(artifact)
    O.kill_pid(proc.pid)
    proc.wait(timeout=5)
    reported_dead = mon["verdict"] in M.DEAD_VERDICTS or mon["verdict"] == "FINISHED"
    return {
        "tmp": str(tmp),
        "artifact_bytes_start": size0,
        "artifact_bytes_end": size1,
        "artifact_bytes_unchanged": size0 == size1,
        "monitor": mon,
        "mtime_only": mt,
        "reported_dead": reported_dead,
        "pass": (
            size0 == size1
            and mon["verdict"] == "IDLE_ALIVE"
            and not reported_dead
            and not mon["mtime_used"]
            and mt["verdict"] == "STALLED"
        ),
    }


def run_all() -> dict:
    pair = constructed_pair()
    harvest = harvest_after_monitor_death()
    idle = idle_alive()
    ok = bool(pair.get("pass") and harvest.get("pass") and idle.get("pass"))
    return {"pair": pair, "harvest": harvest, "idle": idle, "pass": ok}
