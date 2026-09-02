"""Kill-set guard: protected services survive; proven orphans are reaped.

Contract (TST-0104): a kill-based memory guard may only terminate a
candidate when ALL of the following hold —

* the planted RSS footprint is at or above the pressure ceiling
  (below the ceiling every candidate is SPARE, reason ``below-ceiling``);
* the candidate is NOT on ``PROTECTED_NAMES`` (the allowlist is consulted
  before any orphan classification, so a shared always-on service such as
  agent-mail is never in the kill set);
* the candidate is either a genuine orphan — its owning session pid is gone
  AND its artifact bytes did not grow between two samples — or it has no
  session at all (the naive no-session classifier).

Pressure is measured as commit charge (``Committed_AS``) plus
``MemAvailable`` from ``/proc/meminfo``; commit charge is not the working
set, which is why the guard keys off the planted RSS ceiling rather than
the commit figure. ``apply_kills`` only ever signals pids inside an explicit
allow set so a probe cannot leak SIGKILLs onto the host.

This module is deliberately self-contained (no relative imports): the
allowlist mutation probe re-executes its source in a fresh namespace.
"""
from __future__ import annotations

import os
import signal
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

KILL = "KILL"
SPARE = "SPARE"
REASON_BELOW_CEILING = "below-ceiling"
REASON_NO_SESSION = "no-session"
REASON_ORPHAN = "orphan"
REASON_PROTECTED = "protected"
REASON_SESSION_ALIVE = "session-alive"
PROTECTED_NAMES = frozenset({"agent-mail"})

_MEMINFO = "/proc/meminfo"


@dataclass
class Candidate:
    """One process the guard may consider for termination."""

    pid: int
    name: str
    session_id: str | None = None
    session_pid_exists: bool = False
    session_cpu_delta_ns: int = 0
    artifact_bytes_t0: int = 0
    artifact_bytes_t1: int = 0
    rss_bytes: int = 0
    cmdline: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Pressure:
    """A single pressure sample: planted RSS against a ceiling plus live meminfo."""

    planted_rss_bytes: int
    ceiling_bytes: int
    committed_as_bytes: int
    mem_available_bytes: int
    mem_total_bytes: int
    commit_is_not_working_set: bool = True

    @property
    def at_ceiling(self) -> bool:
        return self.planted_rss_bytes >= self.ceiling_bytes

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["at_ceiling"] = self.at_ceiling
        return d


@dataclass
class Decision:
    pid: int
    name: str
    action: str
    reason: str
    session_id: str | None = None
    session_pid_exists: bool = False
    death_proven: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KillReport:
    pressure: Pressure
    decisions: list[Decision] = field(default_factory=list)

    @property
    def kill_set(self) -> list[int]:
        return [d.pid for d in self.decisions if d.action == KILL]

    def decision_for(self, pid: int) -> Decision | None:
        for d in self.decisions:
            if d.pid == pid:
                return d
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pressure": self.pressure.to_dict(),
            "kill_set": self.kill_set,
            "decisions": [d.to_dict() for d in self.decisions],
        }


def pid_exists(pid: int) -> bool:
    """True when ``pid`` is in the process table (zombies included)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def rss_bytes(pid: int) -> int:
    """Resident set size of ``pid`` from /proc, 0 when unreadable."""
    path = f"/proc/{pid}/statm"
    try:
        with open(path, encoding="utf-8") as fh:
            pages = int(fh.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        return 0


def _meminfo() -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        with open(_MEMINFO, encoding="utf-8") as fh:
            for line in fh:
                key, _, rest = line.partition(":")
                parts = rest.split()
                if not parts:
                    continue
                try:
                    value = int(parts[0])
                except ValueError:
                    continue
                if len(parts) > 1 and parts[1].lower() == "kb":
                    value *= 1024
                out[key.strip()] = value
    except OSError:
        pass
    return out


def sample_pressure(
    *, planted_rss_bytes: int, ceiling_bytes: int | None = None
) -> Pressure:
    """Sample pressure.

    ``ceiling_bytes`` defaults to the planted footprint itself, i.e. the
    planted RSS ceiling has been reached and the guard is armed. Pass a
    ceiling above the footprint to model the below-ceiling control.
    """
    info = _meminfo()
    ceiling = int(planted_rss_bytes if ceiling_bytes is None else ceiling_bytes)
    return Pressure(
        planted_rss_bytes=int(planted_rss_bytes),
        ceiling_bytes=ceiling,
        committed_as_bytes=int(info.get("Committed_AS", 0)),
        mem_available_bytes=int(info.get("MemAvailable", 0)),
        mem_total_bytes=int(info.get("MemTotal", 0)),
        commit_is_not_working_set=True,
    )


def session_death_proven(candidate: Candidate) -> bool:
    """Two-signal AND: owning session pid gone AND artifact bytes did not grow."""
    if candidate.session_id is None:
        return False
    session_pid_gone = not bool(candidate.session_pid_exists)
    artifact_did_not_grow = candidate.artifact_bytes_t1 <= candidate.artifact_bytes_t0
    return session_pid_gone and artifact_did_not_grow


def _reason_for(candidate: Candidate, *, on_list: bool, pressure: Pressure) -> tuple[str, str]:
    """Classify one candidate. The allowlist is consulted before any orphan logic."""
    if not pressure.at_ceiling:
        return SPARE, REASON_BELOW_CEILING
    if on_list:
        return SPARE, REASON_PROTECTED
    if candidate.session_id is None:
        return KILL, REASON_NO_SESSION
    if candidate.session_pid_exists:
        return SPARE, REASON_SESSION_ALIVE
    if session_death_proven(candidate):
        return KILL, REASON_ORPHAN
    return SPARE, REASON_SESSION_ALIVE


def select_kill_set(candidates: Iterable[Candidate], pressure: Pressure) -> KillReport:
    """Build the kill report: one logged decision (with a reason) per candidate."""
    report = KillReport(pressure=pressure)
    for candidate in candidates:
        on_list = candidate.name in PROTECTED_NAMES
        action, reason = _reason_for(candidate, on_list=on_list, pressure=pressure)
        report.decisions.append(
            Decision(
                pid=int(candidate.pid),
                name=candidate.name,
                action=action,
                reason=reason,
                session_id=candidate.session_id,
                session_pid_exists=bool(candidate.session_pid_exists),
                death_proven=session_death_proven(candidate),
            )
        )
    return report


def apply_kills(report: KillReport, *, allowed_pids: Iterable[int]) -> list[int]:
    """SIGKILL every pid in the kill set that is ALSO in ``allowed_pids``.

    Pids outside the allow set are never signalled; the caller owns the
    planted set and nothing else on the host is reachable from here.
    """
    allowed = {int(p) for p in allowed_pids}
    applied: list[int] = []
    for pid in report.kill_set:
        if pid not in allowed:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
        applied.append(pid)
    return applied
