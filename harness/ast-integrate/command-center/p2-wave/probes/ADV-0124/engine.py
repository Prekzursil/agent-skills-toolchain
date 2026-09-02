#!/usr/bin/env python3
"""Construct the four ADV-0124 truths and classify with three instruments."""
from __future__ import annotations

import inspect
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import heartbeat_only as HB  # noqa: E402
import monitor as M  # noqa: E402
import mtime_only as MT  # noqa: E402
from common import (  # noqa: E402
    ELEVEN_H,
    FOUR_TRUTHS,
    PRODUCTION_ABSENT,
    REPO,
    TRUTH_S1,
    TRUTH_S2,
    TRUTH_S3,
    TRUTH_S4,
)

WORKER = HERE / "worker_fixture.py"
MONITOR_SRC = HERE / "monitor.py"


def append_ledger(ledger: Path, rec: dict) -> None:
    rec = dict(rec)
    rec.setdefault("ts", time.time())
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def spawn(args: list[str]) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-B", str(WORKER), *args],
        cwd=str(HERE),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def kill_pid(pid: int, sig: int = getattr(signal, "SIGKILL", getattr(signal, "SIGTERM", 9))) -> None:
    try:
        os.kill(int(pid), sig)
    except (ProcessLookupError, PermissionError, OSError):
        return


def reap(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    pid = proc.pid
    kill_pid(pid, getattr(signal, "SIGCONT", 0) or 0)
    kill_pid(pid, getattr(signal, "SIGKILL", getattr(signal, "SIGTERM", 9)))
    try:
        os.killpg(pid, getattr(signal, "SIGKILL", getattr(signal, "SIGTERM", 9)))
    except (ProcessLookupError, PermissionError, OSError, AttributeError):
        pass
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        kill_pid(pid, getattr(signal, "SIGKILL", getattr(signal, "SIGTERM", 9)))


def wait_bytes(path: Path, minimum: int, timeout_s: float = 8.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if path.is_file() and path.stat().st_size >= minimum:
            return True
        time.sleep(0.02)
    return False


def wait_exit(proc: subprocess.Popen, timeout_s: float = 8.0) -> int | None:
    try:
        return int(proc.wait(timeout=timeout_s))
    except subprocess.TimeoutExpired:
        return None


def backdate(path: Path, age_s: float = ELEVEN_H) -> None:
    ts = time.time() - age_s
    os.utime(path, (ts, ts))


def wait_state_t(pid: int, timeout_s: float = 4.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        info = M.read_proc(pid)
        if info and info.get("state") == "T":
            return True
        time.sleep(0.02)
    return False


def source_audit() -> dict:
    text = MONITOR_SRC.read_text(encoding="utf-8")
    banned = [
        "st_" + "mtime",
        "get" + "mtime",
        "os.path.get" + "mtime",
        "stat().st_" + "mtime",
    ]
    hits = [tok for tok in banned if tok in text]
    params = inspect.signature(M.classify).parameters
    return {
        "path": "command-center/p2-wave/probes/ADV-0124/monitor.py",
        "banned_hits": hits,
        "clean": not hits,
        "classify_has_mtime_param": "mtime" in params,
    }


def production_absent() -> dict:
    rows = []
    for rel in PRODUCTION_ABSENT:
        path = REPO / rel
        rows.append({"path": rel, "exists": path.exists()})
    return {
        "all_absent": all(not r["exists"] for r in rows),
        "rows": rows,
        "note": (
            "Harvest-era session.py / oslock.py / monitorcore are absent on "
            "this Linux worktree. ADV-0124 measures the orchestrator "
            "four-state monitor (ledger + /proc + independent heartbeat). "
            "It does not rebuild session.py."
        ),
    }


def _classify_bundle(
    *,
    unit_id: str,
    ledger: Path,
    artifact: Path,
    heartbeat: Path,
) -> dict:
    mon = M.classify(
        unit_id=unit_id,
        ledger=ledger,
        artifact=artifact,
        heartbeat=heartbeat,
        sample_s=0.22,
    )
    mt = MT.classify_mtime_only(artifact)
    hb = HB.classify_heartbeat_only(heartbeat)
    return {"monitor": mon, "mtime_only": mt, "heartbeat_only": hb}


def scenario_s1(root: Path) -> dict:
    unit_id = "s1-running-monitor-alive"
    ledger = root / "s1" / "ledger.jsonl"
    artifact = root / "s1" / "work.bin"
    hb = root / "s1" / "heartbeat.json"
    worker = spawn(["busy", str(artifact)])
    monitor_proc = spawn(["heartbeat", str(hb)])
    append_ledger(
        ledger, {"event": "spawn", "unit_id": unit_id, "pid": worker.pid}
    )
    try:
        if not wait_bytes(artifact, 4096) or not wait_bytes(hb, 8):
            raise RuntimeError("S1 did not start")
        time.sleep(0.2)
        bundle = _classify_bundle(
            unit_id=unit_id, ledger=ledger, artifact=artifact, heartbeat=hb
        )
        return {
            "id": "S1-RUNNING-MONITOR-ALIVE",
            "truth": TRUTH_S1,
            "worker_pid": worker.pid,
            "worker_alive": pid_alive(worker.pid),
            "monitor_pid": monitor_proc.pid,
            "monitor_alive": pid_alive(monitor_proc.pid),
            "artifact": str(artifact),
            **bundle,
        }
    finally:
        reap(worker)
        reap(monitor_proc)


def scenario_s2(root: Path) -> dict:
    unit_id = "s2-running-monitor-dead"
    ledger = root / "s2" / "ledger.jsonl"
    artifact = root / "s2" / "work.bin"
    hb = root / "s2" / "heartbeat.json"
    worker = spawn(["busy", str(artifact)])
    monitor_proc = spawn(["heartbeat", str(hb)])
    append_ledger(
        ledger, {"event": "spawn", "unit_id": unit_id, "pid": worker.pid}
    )
    try:
        if not wait_bytes(artifact, 4096) or not wait_bytes(hb, 8):
            raise RuntimeError("S2 did not start")
        time.sleep(0.15)
        reap(monitor_proc)
        time.sleep(0.16)
        bundle = _classify_bundle(
            unit_id=unit_id, ledger=ledger, artifact=artifact, heartbeat=hb
        )
        return {
            "id": "S2-RUNNING-MONITOR-DEAD",
            "truth": TRUTH_S2,
            "worker_pid": worker.pid,
            "worker_alive": pid_alive(worker.pid),
            "monitor_pid": monitor_proc.pid,
            "monitor_alive": pid_alive(monitor_proc.pid),
            "artifact": str(artifact),
            **bundle,
        }
    finally:
        reap(worker)
        reap(monitor_proc)


def scenario_s3(root: Path) -> dict:
    unit_id = "s3-finished"
    ledger = root / "s3" / "ledger.jsonl"
    artifact = root / "s3" / "work.bin"
    hb = root / "s3" / "heartbeat.json"
    worker = spawn(["finish", str(artifact)])
    append_ledger(
        ledger, {"event": "spawn", "unit_id": unit_id, "pid": worker.pid}
    )
    rc = wait_exit(worker, timeout_s=8.0)
    if rc != 0 or not artifact.is_file():
        reap(worker)
        raise RuntimeError(f"S3 finish worker failed rc={rc}")
    append_ledger(
        ledger,
        {
            "event": "terminal",
            "unit_id": unit_id,
            "pid": worker.pid,
            "exit_code": rc,
            "reason": "clean-complete",
        },
    )
    backdate(artifact)
    bundle = _classify_bundle(
        unit_id=unit_id, ledger=ledger, artifact=artifact, heartbeat=hb
    )
    return {
        "id": "S3-FINISHED",
        "truth": TRUTH_S3,
        "worker_pid": worker.pid,
        "worker_alive": pid_alive(worker.pid),
        "monitor_pid": None,
        "monitor_alive": False,
        "artifact": str(artifact),
        "backdated_s": ELEVEN_H,
        **bundle,
    }


def scenario_s4(root: Path) -> dict:
    unit_id = "s4-stalled"
    ledger = root / "s4" / "ledger.jsonl"
    artifact = root / "s4" / "work.bin"
    hb = root / "s4" / "heartbeat.json"
    worker = spawn(["busy", str(artifact)])
    monitor_proc = spawn(["heartbeat", str(hb)])
    append_ledger(
        ledger, {"event": "spawn", "unit_id": unit_id, "pid": worker.pid}
    )
    try:
        if not wait_bytes(artifact, 4096):
            raise RuntimeError("S4 worker produced no bytes")
        kill_pid(worker.pid, getattr(signal, "SIGSTOP", getattr(signal, "SIGTERM", 9)))
        if not wait_state_t(worker.pid):
            raise RuntimeError("S4 worker did not enter /proc state T")
        reap(monitor_proc)
        time.sleep(0.16)
        backdate(artifact)
        bundle = _classify_bundle(
            unit_id=unit_id, ledger=ledger, artifact=artifact, heartbeat=hb
        )
        return {
            "id": "S4-STALLED",
            "truth": TRUTH_S4,
            "worker_pid": worker.pid,
            "worker_alive": pid_alive(worker.pid),
            "monitor_pid": monitor_proc.pid,
            "monitor_alive": pid_alive(monitor_proc.pid),
            "artifact": str(artifact),
            "backdated_s": ELEVEN_H,
            **bundle,
        }
    finally:
        reap(worker)
        reap(monitor_proc)


def _row_summary(row: dict) -> dict:
    mon = row["monitor"]
    return {
        "id": row["id"],
        "truth": row["truth"],
        "reported": mon["verdict"],
        "data_source": mon["data_source"],
        "mtime_used": mon["mtime_used"],
        "admitted_signals": mon["admitted_signals"],
        "heartbeat_only_projection": mon["heartbeat_only_projection"],
        "mtime_only_verdict": row["mtime_only"]["verdict"],
        "heartbeat_only_verdict": row["heartbeat_only"]["verdict"],
        "worker_alive": row["worker_alive"],
        "monitor_alive": row["monitor_alive"],
        "match": mon["verdict"] == row["truth"],
    }


def run_matrix(root: Path | None = None) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="adv0124-")) if root is None else root
    tmp.mkdir(parents=True, exist_ok=True)
    rows = [
        scenario_s1(tmp),
        scenario_s2(tmp),
        scenario_s3(tmp),
        scenario_s4(tmp),
    ]
    summaries = [_row_summary(r) for r in rows]
    by_truth = {s["truth"]: s for s in summaries}
    reported = [s["reported"] for s in summaries]
    four_distinct = len(set(reported)) == 4 and set(reported) == set(FOUR_TRUTHS)
    plainly_running_ok = by_truth[TRUTH_S1]["reported"] == TRUTH_S1
    finished_vs_stalled = (
        by_truth[TRUTH_S3]["reported"] == TRUTH_S3
        and by_truth[TRUTH_S4]["reported"] == TRUTH_S4
        and by_truth[TRUTH_S3]["reported"] != by_truth[TRUTH_S4]["reported"]
    )
    live_work_not_false_dead = by_truth[TRUTH_S2]["reported"] == TRUTH_S2
    hb_s2 = by_truth[TRUTH_S2]["heartbeat_only_projection"]
    hb_s4 = by_truth[TRUTH_S4]["heartbeat_only_projection"]
    hb_only_collide = hb_s2 == hb_s4
    mt_s3 = by_truth[TRUTH_S3]["mtime_only_verdict"]
    mt_s4 = by_truth[TRUTH_S4]["mtime_only_verdict"]
    mt_s1 = by_truth[TRUTH_S1]["mtime_only_verdict"]
    mtime_collide = mt_s3 == mt_s4 == "STALLED"
    mtime_s1_silent = mt_s1 == "LIVE"
    hb_false_dead = by_truth[TRUTH_S2]["heartbeat_only_verdict"] == "DEAD"
    hb_s1_silent = by_truth[TRUTH_S1]["heartbeat_only_verdict"] == "LIVE"
    audit = source_audit()
    mtime_used_any = any(s["mtime_used"] for s in summaries)
    confusion = {s["truth"]: s["reported"] for s in summaries}
    ok = (
        four_distinct
        and plainly_running_ok
        and finished_vs_stalled
        and live_work_not_false_dead
        and all(s["match"] for s in summaries)
        and not mtime_used_any
        and audit["clean"]
        and not audit["classify_has_mtime_param"]
        and hb_only_collide
        and mtime_collide
        and mtime_s1_silent
        and hb_false_dead
        and hb_s1_silent
    )
    return {
        "pass": ok,
        "tmp": str(tmp),
        "rows": summaries,
        "raw": [
            {
                "id": r["id"],
                "truth": r["truth"],
                "monitor": r["monitor"],
                "mtime_only": r["mtime_only"],
                "heartbeat_only": r["heartbeat_only"],
                "worker_alive": r["worker_alive"],
                "monitor_alive": r["monitor_alive"],
            }
            for r in rows
        ],
        "confusion_matrix": confusion,
        "four_distinct": four_distinct,
        "plainly_running_ok": plainly_running_ok,
        "finished_versus_stalled_distinct": finished_vs_stalled,
        "live_work_not_false_dead": live_work_not_false_dead,
        "heartbeat_only_s2_s4_collide": hb_only_collide,
        "mtime_only_s3_s4_collide": mtime_collide,
        "mtime_s1_silent": mtime_s1_silent,
        "heartbeat_false_dead_on_s2": hb_false_dead,
        "heartbeat_s1_silent": hb_s1_silent,
        "mtime_used_any": mtime_used_any,
        "source_audit": audit,
        "production_absent": production_absent(),
        "proc_s2_vs_s4": {
            "s2": by_truth[TRUTH_S2]["admitted_signals"],
            "s4": by_truth[TRUTH_S4]["admitted_signals"],
            "distinct_when_proc_admitted": (
                by_truth[TRUTH_S2]["admitted_signals"].get("proc_state")
                != by_truth[TRUTH_S4]["admitted_signals"].get("proc_state")
            ),
        },
    }
