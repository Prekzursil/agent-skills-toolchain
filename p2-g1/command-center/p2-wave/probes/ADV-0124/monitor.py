#!/usr/bin/env python3
"""Orchestrator four-state monitor: ledger + /proc + heartbeat. Never file age.

Labels:
  RUNNING_MONITOR_ALIVE  — worker /proc alive (not T) and heartbeat seq advancing
  RUNNING_MONITOR_DEAD   — worker /proc alive (not T) and heartbeat frozen/absent
  FINISHED               — durable orchestrator terminal record
  STALLED                — /proc state T (SIGSTOP)

Stall-from-file-age is unrepresentable: classify() has no age parameter.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from common import COMPLETE, TRUTH_S1, TRUTH_S2, TRUTH_S3, TRUTH_S4

_STAT_STATE = 0
_STAT_UTIME = 11
_STAT_STIME = 12


def read_proc(pid: int) -> dict | None:
    if os.name == "nt":
        # Windows platform adaptation: /proc/<pid>/stat does not exist. psutil
        # exposes the same (pid, state, cpu_ticks) triple; state letters are
        # mapped from psutil statuses ("T" = stopped/suspended is the state the
        # four-state matrix keys on). Instrument semantics are unchanged.
        try:
            import psutil
        except ImportError:
            return None
        try:
            proc = psutil.Process(int(pid))
            status = str(proc.status())
            cpu = proc.cpu_times()
        except Exception:
            return None
        state = {
            "running": "R",
            "sleeping": "S",
            "stopped": "T",
            "suspended": "T",
            "tracing-stop": "t",
            "disk-sleep": "D",
            "zombie": "Z",
            "dead": "X",
        }.get(status, status[:1].upper())
        return {
            "pid": int(pid),
            "state": state,
            "cpu_ticks": int(round((cpu.user + cpu.system) * 100)),
            "source": f"psutil:{pid}",
        }
    path = Path(f"/proc/{int(pid)}/stat")
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
        return None
    rparen = text.rfind(")")
    if rparen < 0:
        return None
    rest = text[rparen + 2 :].split()
    if len(rest) <= _STAT_STIME:
        return None
    try:
        utime = int(rest[_STAT_UTIME])
        stime = int(rest[_STAT_STIME])
    except ValueError:
        return None
    return {
        "pid": int(pid),
        "state": rest[_STAT_STATE],
        "cpu_ticks": utime + stime,
        "source": str(path),
    }


def sample_cpu(pid: int | None, window_s: float) -> dict:
    if pid is None:
        return {
            "alive": False,
            "state": None,
            "cpu_delta": None,
            "source": "no-pid",
        }
    a = read_proc(pid)
    time.sleep(max(0.08, float(window_s)))
    b = read_proc(pid)
    if a is None and b is None:
        return {
            "alive": False,
            "state": None,
            "cpu_delta": None,
            "source": f"/proc/{pid}/stat",
        }
    if b is None:
        return {
            "alive": False,
            "state": None,
            "cpu_delta": None,
            "source": f"/proc/{pid}/stat",
        }
    state = b["state"]
    cpu_delta = None
    if a is not None:
        cpu_delta = b["cpu_ticks"] - a["cpu_ticks"]
    return {
        "alive": state not in {"Z", "X"},
        "state": state,
        "cpu_delta": cpu_delta,
        "source": b["source"],
    }


def load_ledger(ledger: Path) -> list[dict]:
    if not ledger.is_file():
        return []
    rows: list[dict] = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            rows.append(rec)
    return rows


def last_event(ledger: Path, unit_id: str, event: str) -> dict | None:
    found = None
    for rec in load_ledger(ledger):
        if rec.get("unit_id") == unit_id and rec.get("event") == event:
            found = rec
    return found


def artifact_view(path: Path) -> dict:
    if not path.is_file():
        return {
            "exists": False,
            "bytes": 0,
            "complete_trailer": False,
            "source": str(path),
        }
    raw = path.read_bytes()
    return {
        "exists": True,
        "bytes": len(raw),
        "complete_trailer": raw.endswith(COMPLETE),
        "source": str(path),
    }


def heartbeat_seq(path: Path | None) -> dict:
    if path is None:
        return {"exists": False, "seq": None, "pid": None, "source": None}
    if not path.is_file():
        return {"exists": False, "seq": None, "pid": None, "source": str(path)}
    # shard2-w2 hardening 2026-10-25: the writer rewrites this file every beat
    # (open-truncate-write-close), so a read landing inside that window sees a
    # torn/empty body. Mapping a torn read straight to seq=None made classify()
    # read a healthy advancing monitor as frozen (S1 -> RUNNING_MONITOR_DEAD) —
    # a detector failure in exactly the direction this unit hunts. Bounded
    # retry resolves the race without weakening the frozen-heartbeat verdict:
    # a file still unreadable after the retries stays seq=None, and a stopped
    # writer never rewrites, so S2 detection is unchanged.
    for _attempt in range(6):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            time.sleep(0.02)
            continue
        seq = doc.get("seq")
        if isinstance(seq, int):
            return {
                "exists": True,
                "seq": seq,
                "pid": doc.get("pid"),
                "source": str(path),
            }
        time.sleep(0.02)
    return {"exists": True, "seq": None, "pid": None, "source": str(path)}


def classify(
    *,
    unit_id: str,
    ledger: Path,
    artifact: Path,
    heartbeat: Path | None,
    sample_s: float = 0.22,
) -> dict:
    """Named four-state verdict. File age is not a parameter and is not read."""
    term = last_event(ledger, unit_id, "terminal")
    spawn = last_event(ledger, unit_id, "spawn")
    art = artifact_view(artifact)
    pid = None
    if spawn and spawn.get("pid") is not None:
        pid = int(spawn["pid"])
    proc = sample_cpu(pid, sample_s)
    hb1 = heartbeat_seq(heartbeat)
    if heartbeat is not None and hb1.get("exists"):
        # shard2-w2 hardening 2026-10-25: 0.14s carried ~2 beats of a 50ms
        # heartbeat, which a loaded scheduler can stretch past the whole
        # window, making a live monitor read frozen (the S1 false-dead the
        # measured fleet run hit). 0.35s carries ~7 nominal beats; a frozen
        # writer still never advances, so S2 detection is unchanged.
        time.sleep(0.35)
        hb2 = heartbeat_seq(heartbeat)
        hb_delta = None
        if isinstance(hb1.get("seq"), int) and isinstance(hb2.get("seq"), int):
            hb_delta = hb2["seq"] - hb1["seq"]
    else:
        hb2 = hb1
        hb_delta = None

    hb_fresh = hb_delta is not None and hb_delta > 0
    admitted = {
        "terminal": term is not None,
        "proc_alive": bool(proc.get("alive")),
        "proc_state": proc.get("state"),
        "cpu_delta": proc.get("cpu_delta"),
        "hb_fresh": hb_fresh,
        "hb_delta": hb_delta,
        "complete_trailer": bool(art.get("complete_trailer")),
    }

    if term is not None:
        verdict = TRUTH_S3
        data_source = f"{ledger.as_posix()}:event=terminal:exit={term.get('exit_code')}"
        reason = "durable orchestrator terminal record"
    elif proc.get("alive") and proc.get("state") == "T":
        verdict = TRUTH_S4
        data_source = f"{proc['source']}:state=T"
        reason = "task is SIGSTOP'd (state T); not inferred from file age"
    elif proc.get("alive") and hb_fresh:
        verdict = TRUTH_S1
        data_source = (
            f"{heartbeat.as_posix()}:seq_delta={hb_delta}+{proc['source']}:alive"
        )
        reason = "pid alive (not T) and heartbeat sequence advancing"
    elif proc.get("alive"):
        verdict = TRUTH_S2
        data_source = (
            f"{proc['source']}:alive:state={proc.get('state')}"
            f"+heartbeat:fresh=false:delta={hb_delta}"
        )
        reason = "pid alive (not T) while heartbeat is frozen or absent"
    else:
        verdict = "UNDECIDABLE"
        data_source = (
            f"{ledger.as_posix()}:no-terminal"
            f"+{proc.get('source')}:alive={proc.get('alive')}"
        )
        reason = "orchestrator signals do not decide; refuse to guess from file age"

    return {
        "unit_id": unit_id,
        "verdict": verdict,
        "reason": reason,
        "data_source": data_source,
        "mtime_used": False,
        "mtime_consulted": False,
        "admitted_signals": admitted,
        "heartbeat_only_projection": {"hb_fresh": hb_fresh},
        "signals": {
            "orchestrator_terminal": term,
            "spawn": spawn,
            "proc": proc,
            "artifact": art,
            "heartbeat": {"first": hb1, "second": hb2, "seq_delta": hb_delta},
        },
    }
