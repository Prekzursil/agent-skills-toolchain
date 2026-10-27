#!/usr/bin/env python3
"""TST-0227 probe 2: the denial holds while the victim session is GENUINELY alive.

A real child OS process plays the victim: it creates a marker in its own
worktree, announces its PID, and stays alive until told to stop. The parent
registers that session in the broker, verifies the child process is alive
(Popen.poll() is None, plus a heartbeat file with a fresh mtime), then the
brokered cross-session write is denied while the process is still running.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "lib"))

from workspace import Codes, SessionBroker, SessionDenied, independent_tree_hash  # noqa: E402

ROOTS = HERE / "fixtures" / "p2"
CHILD = (
    "import os, sys, time\n"
    "wt, run, stop = sys.argv[1], sys.argv[2], sys.argv[3]\n"
    "os.makedirs(wt, exist_ok=True)\n"
    "os.makedirs(run, exist_ok=True)\n"
    "open(os.path.join(wt, 'child-marker.txt'), 'w').write('child live marker')\n"
    "open(os.path.join(run, 'heartbeat.json'), 'w').write(json_placeholder)\n"
    "open(os.path.join(run, 'pid.txt'), 'w').write(str(os.getpid()))\n"
    "while not os.path.exists(stop):\n"
    "    time.sleep(0.05)\n"
    "    with open(os.path.join(run, 'heartbeat.json'), 'a') as f: f.write('.')\n"
).replace("json_placeholder", "'{}'")

STOP = None
PROC = None


def spawn_child() -> tuple[subprocess.Popen, Path]:
    global PROC, STOP
    STOP = ROOTS / "child-stop.flag"
    if STOP.exists():
        STOP.unlink()
    PROC = subprocess.Popen([sys.executable, "-B", "-c", CHILD, str(ROOTS / "victim" / "wt"), str(ROOTS / "victim" / "run"), str(STOP)])
    return PROC, STOP


def main() -> int:
    if ROOTS.exists():
        shutil.rmtree(ROOTS)
    broker = SessionBroker()
    victim_session = broker.register(
        "sess-live-victim",
        worktree_root=ROOTS / "victim" / "wt",
        artifact_root=ROOTS / "victim" / "art",
        runtime_dir=ROOTS / "victim" / "run",
    )
    broker.register(
        "sess-live-actor",
        worktree_root=ROOTS / "actor" / "wt",
        artifact_root=ROOTS / "actor" / "art",
        runtime_dir=ROOTS / "actor" / "run",
    )
    try:
        proc, stop_flag = spawn_child()
        deadline = time.time() + 15
        while time.time() < deadline:
            if (victim_session.runtime_dir / "pid.txt").is_file():
                break
        time.sleep(0.2)
        alive_before = proc.poll() is None
        marker_present = (victim_session.worktree_root / "child-marker.txt").is_file()
        heartbeat = victim_session.runtime_dir / "heartbeat.json"
        heartbeat_fresh = heartbeat.is_file() and (time.time() - heartbeat.stat().st_mtime) < 10

        hash_before = independent_tree_hash(victim_session.worktree_root)
        denied = False
        code = None
        alert_names = {}
        try:
            broker.write_file("sess-live-actor", victim_session.worktree_root / "intrusion.txt", b"x")
        except SessionDenied as exc:
            denied = True
            code = exc.code
            alert_names = exc.alert.as_dict()
        alive_after = proc.poll() is None
        hash_after = independent_tree_hash(victim_session.worktree_root)

        checks = {
            "victim_process_genuinely_alive": alive_before is True and alive_after is True,
            "victim_wrote_marker_live": marker_present is True,
            "heartbeat_fresh": heartbeat_fresh is True,
            "denial_while_alive": denied is True and code == Codes.CROSS_SESSION_WRITE,
            "alert_names_both_live_ids": alert_names.get("actor") == "sess-live-actor" and alert_names.get("victim") == "sess-live-victim",
            "victim_tree_unchanged": hash_after == hash_before,
        }
        out = {
            "probe": "probe2_concurrent_active",
            "unit": "TST-0227",
            "child_pid": proc.pid,
            "alive_before": alive_before,
            "alive_after": alive_after,
            "alert": alert_names,
            "checks": checks,
            "ok": all(checks.values()),
        }
        (HERE / "probe2_concurrent_active.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(out, sort_keys=True))
        return 0 if out["ok"] else 1
    finally:
        if STOP is not None:
            try:
                STOP.write_text("stop")
            except OSError:
                pass
        try:
            if PROC is not None:
                PROC.wait(timeout=10)
        except subprocess.TimeoutExpired:
            PROC.kill()
        shutil.rmtree(ROOTS, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
