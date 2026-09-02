#!/usr/bin/env python3
"""CNF-0047 liveness monitor: orchestrator state, never file mtime.

Stall / finished / idle-alive claims are derived from:
  * durable orchestrator ledger (terminal records)
  * /proc/<pid>/stat (existence + task state + CPU ticks)
  * artifact byte length + COMPLETE trailer (not mtime)
  * independent heartbeat sequence written by the unit

mtime is unreadable from this API. A stall claim from mtimes alone is
structurally unrepresentable: classify() has no mtime parameter.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

COMPLETE = b"\nCNF-0047-COMPLETE\n"
DEAD_VERDICTS = frozenset({"DEAD", "STALLED", "KILLED_MID_WRITE"})

# /proc/<pid>/stat after the comm field: index 0 is state (field 3),
# index 11 is utime (field 14), index 12 is stime (field 15).
_STAT_STATE = 0
_STAT_UTIME = 11
_STAT_STIME = 12


def read_proc(pid: int) -> dict | None:
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


def load_ledger(ledger: Path) -> list[dict]:
    if not ledger.is_file():
        return []
    rows = []
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


def terminal_for(ledger: Path, unit_id: str) -> dict | None:
    found = None
    for rec in load_ledger(ledger):
        if rec.get("unit_id") == unit_id and rec.get("event") == "terminal":
            found = rec
    return found


def spawn_for(ledger: Path, unit_id: str) -> dict | None:
    found = None
    for rec in load_ledger(ledger):
        if rec.get("unit_id") == unit_id and rec.get("event") == "spawn":
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


def heartbeat_seq(path: Path) -> dict:
    if not path.is_file():
        return {"exists": False, "seq": None, "pid": None, "source": str(path)}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"exists": True, "seq": None, "pid": None, "source": str(path)}
    return {
        "exists": True,
        "seq": doc.get("seq"),
        "pid": doc.get("pid"),
        "source": str(path),
    }


def sample_cpu(pid: int, window_s: float) -> dict:
    a = read_proc(pid)
    time.sleep(max(0.05, float(window_s)))
    b = read_proc(pid)
    if a is None and b is None:
        return {
            "alive": False,
            "state": None,
            "cpu_delta": None,
            "source": f"/proc/{pid}/stat",
        }
    if a is None or b is None:
        state = None if b is None else b["state"]
        return {
            "alive": bool(b is not None and state not in {"Z", "X"}),
            "state": state,
            "cpu_delta": None,
            "source": f"/proc/{pid}/stat",
        }
    state = b["state"]
    return {
        "alive": state not in {"Z", "X"},
        "state": state,
        "cpu_delta": b["cpu_ticks"] - a["cpu_ticks"],
        "source": b["source"],
    }


def classify(
    *,
    unit_id: str,
    ledger: Path,
    artifact: Path,
    heartbeat: Path | None = None,
    sample_s: float = 0.35,
) -> dict:
    """Return a named verdict. Never consults file age."""
    term = terminal_for(ledger, unit_id)
    spawn = spawn_for(ledger, unit_id)
    art = artifact_view(artifact)
    pid = None
    if spawn and spawn.get("pid") is not None:
        pid = int(spawn["pid"])
    proc = sample_cpu(pid, sample_s) if pid is not None else {
        "alive": False,
        "state": None,
        "cpu_delta": None,
        "source": "no-spawn-pid",
    }
    hb1 = heartbeat_seq(heartbeat) if heartbeat is not None else {"exists": False}
    if heartbeat is not None and hb1.get("exists"):
        time.sleep(0.12)
        hb2 = heartbeat_seq(heartbeat)
        hb_delta = None
        if isinstance(hb1.get("seq"), int) and isinstance(hb2.get("seq"), int):
            hb_delta = hb2["seq"] - hb1["seq"]
    else:
        hb2 = hb1
        hb_delta = None

    data_source = None
    verdict = "UNDECIDABLE"
    reason = "insufficient orchestrator signals"

    if term is not None:
        verdict = "FINISHED"
        data_source = f"{ledger.as_posix()}:event=terminal:exit={term.get('exit_code')}"
        reason = "durable orchestrator terminal record"
    elif proc.get("alive") and proc.get("state") == "T":
        verdict = "STALLED"
        data_source = f"{proc['source']}:state=T"
        reason = "task is SIGSTOP'd (state T); not inferred from mtime"
    elif proc.get("alive") and hb_delta is not None and hb_delta > 0:
        verdict = "IDLE_ALIVE"
        data_source = (
            f"{heartbeat.as_posix()}:seq_delta={hb_delta}"
            f"+{proc['source']}:alive"
        )
        reason = "pid alive and heartbeat sequence advancing with no terminal"
    elif proc.get("alive") and (proc.get("cpu_delta") or 0) > 0:
        if art["bytes"] > 0 and not art["complete_trailer"]:
            verdict = "RUNNING"
            data_source = (
                f"{proc['source']}:cpu_delta={proc['cpu_delta']}"
                f"+artifact.bytes={art['bytes']}"
            )
            reason = "cpu ticks advancing and artifact growing, no terminal"
        else:
            verdict = "IDLE_ALIVE"
            data_source = f"{proc['source']}:cpu_delta={proc['cpu_delta']}"
            reason = "cpu ticks advancing; no terminal; not dead"
    elif not proc.get("alive") and not art["complete_trailer"] and term is None:
        verdict = "KILLED_MID_WRITE"
        data_source = (
            f"{ledger.as_posix()}:no-terminal"
            f"+artifact.bytes={art['bytes']}:complete_trailer=false"
            f"+/proc/{pid}/stat:absent"
        )
        reason = "pid gone, no orchestrator terminal, incomplete artifact"
    else:
        verdict = "UNDECIDABLE"
        data_source = (
            f"{ledger.as_posix()}:no-terminal"
            f"+{proc.get('source')}:alive={proc.get('alive')}"
        )
        reason = "orchestrator signals do not decide; refuse to guess from mtime"

    return {
        "unit_id": unit_id,
        "verdict": verdict,
        "reason": reason,
        "data_source": data_source,
        "mtime_used": False,
        "mtime_consulted": False,
        "signals": {
            "orchestrator_terminal": term,
            "spawn": spawn,
            "proc": proc,
            "artifact": art,
            "heartbeat": {"first": hb1, "second": hb2, "seq_delta": hb_delta},
        },
    }
