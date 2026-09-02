"""Plant agent-mail + live-idle + genuine-orphan and run the kill guard."""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from memory_guard.guard import (  # noqa: E402
    KILL,
    PROTECTED_NAMES,
    REASON_BELOW_CEILING,
    REASON_NO_SESSION,
    REASON_ORPHAN,
    REASON_PROTECTED,
    REASON_SESSION_ALIVE,
    SPARE,
    Candidate,
    apply_kills,
    pid_exists,
    rss_bytes,
    sample_pressure,
    select_kill_set,
    session_death_proven,
)

STUB = HERE / "agent_mail_stub.py"
HOG_BYTES = 4 * 1024 * 1024


@dataclass
class Fixture:
    mail: subprocess.Popen
    idle: subprocess.Popen
    orphan: subprocess.Popen
    port: int
    health_url: str
    session_dead_pid: int
    candidates: list[Candidate]
    planted_pids: set[int]


def _stop(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    if proc.poll() is not None:
        return
    proc.kill()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.wait(timeout=2)


def fetch_health(url: str, timeout: float = 2.0) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        status = int(resp.status)
    body = json.loads(raw.decode("utf-8"))
    if not isinstance(body, dict):
        raise ValueError("health body is not an object")
    return status, body


def wait_health(url: str, timeout: float = 8.0) -> tuple[int, dict[str, Any]]:
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            return fetch_health(url, timeout=1.0)
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            last = exc
            time.sleep(0.05)
    raise RuntimeError(f"health never answered {url}: {last}")


def spawn_mail() -> tuple[subprocess.Popen, int, str]:
    proc = subprocess.Popen(
        [sys.executable, "-B", str(STUB), "TST-0104-agent-mail"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    assert proc.stdout is not None
    line = proc.stdout.readline()
    if not line.strip():
        _stop(proc)
        raise RuntimeError("agent-mail stub did not print a port")
    port = int(line.strip())
    url = f"http://127.0.0.1:{port}/health"
    wait_health(url)
    if not pid_exists(int(proc.pid)):
        raise RuntimeError("agent-mail pid missing after health-ok")
    return proc, port, url


def spawn_sleeper(marker: str, hog: bool = False) -> subprocess.Popen:
    if hog:
        code = (
            "import sys,time;"
            f"sys.argv.append({marker!r});"
            f"b=bytearray({HOG_BYTES});"
            "time.sleep(120)"
        )
    else:
        code = (
            "import sys,time;"
            f"sys.argv.append({marker!r});"
            "time.sleep(120)"
        )
    return subprocess.Popen(
        [sys.executable, "-B", "-c", code],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def plant() -> Fixture:
    mail = idle = orphan = session = None
    try:
        mail, port, url = spawn_mail()
        idle = spawn_sleeper("TST-0104-live-idle")
        session = spawn_sleeper("TST-0104-dead-session")
        orphan = spawn_sleeper("TST-0104-orphan", hog=True)
        time.sleep(0.15)
        if not pid_exists(int(idle.pid)) or not pid_exists(int(orphan.pid)):
            raise RuntimeError("idle or orphan pid missing after spawn")
        if not pid_exists(int(session.pid)):
            raise RuntimeError("session pid missing before kill")
        dead_pid = int(session.pid)
        session.kill()
        session.wait(timeout=8)
        session = None
        if pid_exists(dead_pid):
            raise RuntimeError(f"session pid {dead_pid} still live after kill")
        if not pid_exists(int(orphan.pid)):
            raise RuntimeError("orphan worker died when session was killed")
        candidates = [
            Candidate(
                pid=int(mail.pid),
                name="agent-mail",
                session_id=None,
                session_pid_exists=False,
                session_cpu_delta_ns=0,
                artifact_bytes_t0=0,
                artifact_bytes_t1=0,
                rss_bytes=rss_bytes(int(mail.pid)),
                cmdline="TST-0104-agent-mail",
            ),
            Candidate(
                pid=int(idle.pid),
                name="session-worker",
                session_id="sess-live-idle",
                session_pid_exists=True,
                session_cpu_delta_ns=0,
                artifact_bytes_t0=4096,
                artifact_bytes_t1=4096,
                rss_bytes=rss_bytes(int(idle.pid)),
                cmdline="TST-0104-live-idle",
            ),
            Candidate(
                pid=int(orphan.pid),
                name="orphan-worker",
                session_id="sess-dead",
                session_pid_exists=False,
                session_cpu_delta_ns=0,
                artifact_bytes_t0=2048,
                artifact_bytes_t1=2048,
                rss_bytes=rss_bytes(int(orphan.pid)),
                cmdline="TST-0104-orphan",
            ),
        ]
        planted = {int(mail.pid), int(idle.pid), int(orphan.pid)}
        return Fixture(
            mail=mail,
            idle=idle,
            orphan=orphan,
            port=port,
            health_url=url,
            session_dead_pid=dead_pid,
            candidates=candidates,
            planted_pids=planted,
        )
    except Exception:
        _stop(mail)
        _stop(idle)
        _stop(orphan)
        _stop(session)
        raise


def close_fixture(fix: Fixture) -> None:
    _stop(fix.mail)
    _stop(fix.idle)
    _stop(fix.orphan)


def wait_gone(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pid_exists(pid):
            return True
        time.sleep(0.02)
    return not pid_exists(pid)


def run_live(*, apply: bool = True) -> dict[str, Any]:
    """Drive pressure, select, optionally reap the orphan, re-check health."""
    fix = plant()
    try:
        planted_rss = sum(c.rss_bytes for c in fix.candidates)
        pressure = sample_pressure(planted_rss_bytes=planted_rss)
        below = sample_pressure(
            planted_rss_bytes=planted_rss,
            ceiling_bytes=planted_rss + 10**9,
        )
        report = select_kill_set(fix.candidates, pressure)
        below_report = select_kill_set(fix.candidates, below)
        mail_d = report.decision_for(int(fix.mail.pid))
        idle_d = report.decision_for(int(fix.idle.pid))
        orphan_d = report.decision_for(int(fix.orphan.pid))
        if mail_d is None or idle_d is None or orphan_d is None:
            raise RuntimeError("kill log missing a planted pid")
        reasons_complete = len(report.decisions) == len(fix.candidates) and all(
            isinstance(d.reason, str) and d.reason for d in report.decisions
        )
        kill_set = list(report.kill_set)
        protected_pids = [int(fix.mail.pid)]
        kill_hits_protected = bool(set(kill_set) & set(protected_pids))
        health_before = wait_health(fix.health_url)
        applied: list[int] = []
        if apply:
            applied = apply_kills(report, allowed_pids=fix.planted_pids)
            if int(fix.orphan.pid) in kill_set:
                # SIGKILL leaves a zombie until the parent wait()s; the
                # process table still lists Z until then.
                try:
                    fix.orphan.wait(timeout=5)
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError("orphan did not exit after SIGKILL") from exc
                if not wait_gone(int(fix.orphan.pid)):
                    raise RuntimeError("orphan still in process table after KILL")
        health_after = wait_health(fix.health_url)
        mail_alive = pid_exists(int(fix.mail.pid))
        idle_alive = pid_exists(int(fix.idle.pid))
        orphan_alive = pid_exists(int(fix.orphan.pid))
        return {
            "protected_list": sorted(PROTECTED_NAMES),
            "mail_pid": int(fix.mail.pid),
            "idle_pid": int(fix.idle.pid),
            "orphan_pid": int(fix.orphan.pid),
            "session_dead_pid": int(fix.session_dead_pid),
            "health_url": fix.health_url,
            "port": fix.port,
            "pressure": pressure.to_dict(),
            "below_ceiling_pressure": below.to_dict(),
            "report": report.to_dict(),
            "below_ceiling_kill_set": below_report.kill_set,
            "below_ceiling_all_spare": all(
                d.action == SPARE and d.reason == REASON_BELOW_CEILING
                for d in below_report.decisions
            ),
            "mail_decision": mail_d.to_dict(),
            "idle_decision": idle_d.to_dict(),
            "orphan_decision": orphan_d.to_dict(),
            "kill_set": kill_set,
            "kill_set_hits_protected": kill_hits_protected,
            "reasons_complete": reasons_complete,
            "health_before_status": health_before[0],
            "health_before_service": health_before[1].get("service"),
            "health_after_status": health_after[0],
            "health_after_service": health_after[1].get("service"),
            "mail_alive_after": mail_alive,
            "idle_alive_after": idle_alive,
            "orphan_alive_after": orphan_alive,
            "applied_kills": applied,
            "orphan_death_proven": session_death_proven(
                next(c for c in fix.candidates if c.name == "orphan-worker")
            ),
            "idle_death_proven": session_death_proven(
                next(c for c in fix.candidates if c.name == "session-worker")
            ),
            "mail_death_proven": session_death_proven(
                next(c for c in fix.candidates if c.name == "agent-mail")
            ),
            "candidates": [c.to_dict() for c in fix.candidates],
            "expected_mail_reason": REASON_PROTECTED,
            "expected_idle_reason": REASON_SESSION_ALIVE,
            "expected_orphan_reason": REASON_ORPHAN,
            "naive_no_session_reason": REASON_NO_SESSION,
            "kill": KILL,
            "spare": SPARE,
        }
    finally:
        close_fixture(fix)
