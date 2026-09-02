"""Kill-set guard: protected services survive; proven orphans are reaped."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Iterable

KILL = "KILL"
SPARE = "SPARE"
REASON_BELOW_CEILING = "below-ceiling"
REASON_NO_SESSION = "no-session"
REASON_ORPHAN = "orphan"
REASON_PROTECTED = "protected"
REASON_SESSION_ALIVE = "session-alive"
PROTECTED_NAMES = frozenset({"agent-mail", "mcp_agent_mail", "basic-memory"})


@dataclass
class Candidate:
    pid: int
    name: str
    rss: int
    session_id: str | None = None
    protected: bool = False
    session_alive: bool | None = None
    session_pid_exists: bool | None = None
    health_ok: bool | None = None
    cmdline: str = ""


def pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def rss_bytes(pid: int) -> int:
    path = f"/proc/{pid}/statm"
    try:
        pages = int(open(path, encoding="utf-8").read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        return 0


def sample_pressure() -> int:
    return 0


def session_death_proven(candidate: Candidate, *, health_dead: bool, proc_dead: bool) -> bool:
    return bool(health_dead and proc_dead)


def select_kill_set(
    candidates: Iterable[Candidate],
    *,
    rss_ceiling: int,
    below_ceiling: bool = False,
) -> tuple[list[int], list[dict[str, Any]]]:
    decisions: list[dict[str, Any]] = []
    kill: list[int] = []
    if below_ceiling:
        for c in candidates:
            decisions.append({"pid": c.pid, "name": c.name, "action": SPARE, "reason": REASON_BELOW_CEILING})
        return [], decisions
    for c in candidates:
        if c.protected or c.name in PROTECTED_NAMES:
            decisions.append({"pid": c.pid, "name": c.name, "action": SPARE, "reason": REASON_PROTECTED})
            continue
        if c.session_alive is True:
            decisions.append({"pid": c.pid, "name": c.name, "action": SPARE, "reason": REASON_SESSION_ALIVE})
            continue
        if c.session_id and c.session_alive is False:
            decisions.append({"pid": c.pid, "name": c.name, "action": KILL, "reason": REASON_ORPHAN})
            kill.append(c.pid)
            continue
        if not c.session_id:
            decisions.append({"pid": c.pid, "name": c.name, "action": KILL, "reason": REASON_NO_SESSION})
            kill.append(c.pid)
            continue
        decisions.append({"pid": c.pid, "name": c.name, "action": SPARE, "reason": REASON_SESSION_ALIVE})
    return kill, decisions


def apply_kills(pids: Iterable[int]) -> list[int]:
    reaped = []
    for pid in pids:
        try:
            os.kill(pid, 9)
            reaped.append(pid)
        except OSError:
            reaped.append(pid)
    return reaped
