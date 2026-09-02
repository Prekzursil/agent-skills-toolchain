"""Commit-charge pressure guard for plugin activation (IMP-0066).

The guard has exactly three levers - warn, shed optional queued work, refuse
new work - and deliberately no fourth: it never sends a signal to any process,
so a shared service that other sessions depend on survives every pressure
band. The action ledger exists to prove that. Every step the guard takes is
recorded with its target (``work`` or ``operator``), and
:meth:`PressureGuard.process_actions_issued` filters that ledger to
process-targeted entries, which no code path here can create.

Pressure is the commit-charge ratio ``committed / limit`` from a meter:
:class:`LinuxCommitMeter` reads ``Committed_AS`` / ``CommitLimit`` from
``/proc/meminfo``; :class:`InjectedMeter` lets a probe dial the ratio without
touching the host. Bands, from :class:`Thresholds`::

    ratio <  warn            normal  admit, no warning
    warn   <= ratio < shed   warn    admit, warning to the sink
    shed   <= ratio < refuse shed    optional work deferred + queued optional
                                     tickets shed; required work admitted
    ratio >= refuse          refuse  nothing new admitted; optional queue shed

The read-only ``/proc`` helpers (:func:`snapshot_pids`, :func:`pid_state`,
:func:`pid_is_live`) let a probe show that a pid recorded on a refused ticket
is still in the process table afterwards.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator, Protocol

__all__ = [
    "BANDS",
    "Admit",
    "BoundedWarningSink",
    "CommitSample",
    "InjectedMeter",
    "LinuxCommitMeter",
    "Meter",
    "PressureGuard",
    "PressureWarning",
    "SHARED_NAMES",
    "Thresholds",
    "WorkQueue",
    "WorkTicket",
    "is_shared",
    "pid_is_live",
    "pid_state",
    "read_meminfo",
    "snapshot_pids",
    "would_kill",
]

SHARED_NAMES = ("MCPAgentMailSupervisor", "basic-memory", "sshd")

BANDS = ("normal", "warn", "shed", "refuse")

PROC = Path("/proc")
MEMINFO = PROC / "meminfo"


def is_shared(proc: dict[str, Any]) -> bool:
    """True when a process-table row names one of the shared supervisors."""
    name = str(proc.get("name") or proc.get("comm") or "")
    return any(s.lower() in name.lower() for s in SHARED_NAMES)


def would_kill(proc: dict[str, Any], *, rss_limit: int) -> bool:
    """Predicate only: would a naive RSS reaper pick this row? Shared rows never qualify."""
    if is_shared(proc):
        return False
    rss = int(proc.get("rss") or 0)
    return rss > rss_limit


# --------------------------------------------------------------------------- meters


@dataclass(frozen=True)
class CommitSample:
    """One commit-charge reading. ``ratio`` fails closed to 1.0 when the limit is unknown."""

    committed_units: int
    limit_units: int
    source: str
    unit: str = "kB"

    @property
    def ratio(self) -> float:
        if self.limit_units <= 0:
            return 1.0
        return max(0.0, self.committed_units / self.limit_units)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ratio"] = round(self.ratio, 6)
        return data


class Meter(Protocol):
    def sample(self) -> CommitSample: ...


class InjectedMeter:
    """A meter whose reading a test controls; nothing on the host is consulted."""

    def __init__(self, committed_units: int = 0, limit_units: int = 1000) -> None:
        if limit_units <= 0:
            raise ValueError(f"limit_units must be positive, got {limit_units}")
        if committed_units < 0:
            raise ValueError(f"committed_units must be >= 0, got {committed_units}")
        self.committed_units = int(committed_units)
        self.limit_units = int(limit_units)

    def set_committed(self, committed_units: int) -> CommitSample:
        if committed_units < 0:
            raise ValueError(f"committed_units must be >= 0, got {committed_units}")
        self.committed_units = int(committed_units)
        return self.sample()

    def set_ratio(self, ratio: float) -> CommitSample:
        """Dial the reading so that ``committed / limit`` rounds to ``ratio``."""
        if ratio < 0:
            raise ValueError(f"ratio must be >= 0, got {ratio}")
        return self.set_committed(round(float(ratio) * self.limit_units))

    def sample(self) -> CommitSample:
        return CommitSample(self.committed_units, self.limit_units, source="injected")


def read_meminfo(path: Path = MEMINFO) -> dict[str, int]:
    """``/proc/meminfo`` as ``{field: kB}``; fields without a numeric value are skipped."""
    values: dict[str, int] = {}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            values[key.strip()] = int(parts[0])
    return values


class LinuxCommitMeter:
    """Host commit charge: ``Committed_AS`` over ``CommitLimit`` from ``/proc/meminfo``."""

    def __init__(self, meminfo: Path = MEMINFO) -> None:
        self.meminfo = Path(meminfo)

    def sample(self) -> CommitSample:
        values = read_meminfo(self.meminfo)
        missing = [k for k in ("Committed_AS", "CommitLimit") if k not in values]
        if missing:
            raise ValueError(f"{self.meminfo}: missing {', '.join(missing)}")
        return CommitSample(values["Committed_AS"], values["CommitLimit"], source=str(self.meminfo))


# --------------------------------------------------------------------------- thresholds


@dataclass(frozen=True)
class Thresholds:
    """Band edges as commit ratios; must satisfy ``0 <= warn <= shed <= refuse``."""

    warn: float = 0.50
    shed: float = 0.70
    refuse: float = 0.85

    def __post_init__(self) -> None:
        if not 0.0 <= self.warn <= self.shed <= self.refuse:
            raise ValueError(
                f"thresholds must be ordered 0 <= warn <= shed <= refuse, got "
                f"warn={self.warn} shed={self.shed} refuse={self.refuse}"
            )

    def band(self, ratio: float) -> str:
        if ratio >= self.refuse:
            return "refuse"
        if ratio >= self.shed:
            return "shed"
        if ratio >= self.warn:
            return "warn"
        return "normal"

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


# --------------------------------------------------------------------------- work + warnings


@dataclass
class WorkTicket:
    """A unit of work waiting for admission. Optional tickets are the ones shedding drops."""

    ticket_id: str
    kind: str
    optional: bool = False
    holder_pid: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkQueue:
    """Insertion-ordered pending tickets keyed by ``ticket_id``."""

    def __init__(self) -> None:
        self._tickets: dict[str, WorkTicket] = {}

    def enqueue(self, ticket: WorkTicket) -> None:
        if ticket.ticket_id in self._tickets:
            raise ValueError(f"duplicate ticket_id {ticket.ticket_id!r}")
        self._tickets[ticket.ticket_id] = ticket

    def remove(self, ticket_id: str) -> WorkTicket | None:
        return self._tickets.pop(ticket_id, None)

    def pending(self) -> list[WorkTicket]:
        return list(self._tickets.values())

    def shed_optional(self) -> list[WorkTicket]:
        """Drop every optional ticket, in queue order, and return them."""
        shed = [t for t in self._tickets.values() if t.optional]
        for ticket in shed:
            del self._tickets[ticket.ticket_id]
        return shed

    def __len__(self) -> int:
        return len(self._tickets)

    def __contains__(self, ticket_id: object) -> bool:
        return ticket_id in self._tickets

    def __iter__(self) -> Iterator[WorkTicket]:
        return iter(list(self._tickets.values()))


@dataclass(frozen=True)
class PressureWarning:
    seq: int
    band: str
    ratio: float
    ticket_id: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class BoundedWarningSink:
    """Keeps the newest ``cap`` warnings; older ones are dropped and counted, never raised."""

    def __init__(self, cap: int = 64) -> None:
        if cap <= 0:
            raise ValueError(f"cap must be positive, got {cap}")
        self.cap = int(cap)
        self._records: deque[PressureWarning] = deque(maxlen=self.cap)
        self.dropped = 0

    def emit(self, warning: PressureWarning) -> bool:
        """Store ``warning``; returns False when an older record was evicted to make room."""
        evicted = len(self._records) == self.cap
        if evicted:
            self.dropped += 1
        self._records.append(warning)
        return not evicted

    def records(self) -> list[PressureWarning]:
        return list(self._records)

    def __len__(self) -> int:
        return len(self._records)


# --------------------------------------------------------------------------- guard


@dataclass
class Admit:
    """Outcome of one admission decision."""

    admitted: bool
    band: str
    ratio: float
    ticket_id: str
    kind: str
    optional: bool
    reason: str
    warning: str | None = None
    shed_ticket_ids: list[str] = field(default_factory=list)
    holder_pid: int | None = None
    holder_state: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ratio"] = round(self.ratio, 6)
        return data


class PressureGuard:
    """Admission control on commit pressure with warn / shed / refuse as its only levers."""

    def __init__(
        self,
        meter: Meter,
        *,
        thresholds: Thresholds | None = None,
        sink: BoundedWarningSink | None = None,
        queue: WorkQueue | None = None,
    ) -> None:
        self.meter = meter
        self.thresholds = thresholds if thresholds is not None else Thresholds()
        # Explicit None checks: an empty sink/queue is falsy (both define __len__)
        # and must still be the caller's object, not a silent replacement.
        self.sink = sink if sink is not None else BoundedWarningSink()
        self.queue = queue if queue is not None else WorkQueue()
        self._ledger: list[dict[str, Any]] = []
        self._seq = 0

    # -- readings
    def sample(self) -> CommitSample:
        return self.meter.sample()

    def band(self) -> str:
        return self.thresholds.band(self.sample().ratio)

    # -- ledger
    def _record(self, target: str, action: str, **detail: Any) -> None:
        entry = {"seq": self._seq, "target": target, "action": action}
        entry.update(detail)
        self._ledger.append(entry)

    def ledger(self) -> list[dict[str, Any]]:
        """Every action taken so far, oldest first (copies)."""
        return [dict(e) for e in self._ledger]

    def process_actions_issued(self) -> list[dict[str, Any]]:
        """Ledger entries aimed at a process. The guard has no lever that creates one."""
        return [dict(e) for e in self._ledger if e.get("target") == "process"]

    def work_actions_issued(self) -> list[dict[str, Any]]:
        return [dict(e) for e in self._ledger if e.get("target") == "work"]

    # -- decisions
    def admit_new_work(
        self,
        kind: str,
        *,
        optional: bool = False,
        ticket_id: str | None = None,
        holder_pid: int | None = None,
    ) -> Admit:
        """Decide whether new work of ``kind`` may start under the current pressure band.

        ``holder_pid`` is the process that would run the work; it is recorded
        (and its ``/proc`` state peeked read-only) so the ledger can show the
        guard knew the pid and still left it alone.
        """
        sample = self.meter.sample()
        ratio = sample.ratio
        band = self.thresholds.band(ratio)
        self._seq += 1
        tid = ticket_id or f"{kind}-{self._seq}"
        holder_state = pid_state(holder_pid) if holder_pid is not None else None

        shed_ids: list[str] = []
        warning: str | None = None
        if band == "normal":
            admitted = True
            reason = "below-warn-threshold"
        elif band == "warn":
            admitted = True
            reason = "warn-band-admitted-with-warning"
            warning = (
                f"commit charge {ratio:.1%} >= warn {self.thresholds.warn:.0%}: "
                f"admitting {kind!r} ({tid}) with warning"
            )
        elif band == "shed":
            shed_ids = self._shed_optional_queue(band, ratio)
            if optional:
                admitted = False
                reason = "shed-band-optional-work-deferred"
            else:
                admitted = True
                reason = "shed-band-required-work-admitted"
            warning = (
                f"commit charge {ratio:.1%} >= shed {self.thresholds.shed:.0%}: "
                f"{'deferring optional' if optional else 'admitting required'} {kind!r} ({tid}); "
                f"shed {len(shed_ids)} optional ticket(s)"
            )
        else:
            shed_ids = self._shed_optional_queue(band, ratio)
            admitted = False
            reason = "refuse-band-new-work-refused"
            warning = (
                f"commit charge {ratio:.1%} >= refuse {self.thresholds.refuse:.0%}: "
                f"refusing {kind!r} ({tid}); shed {len(shed_ids)} optional ticket(s); "
                "no process was signalled"
            )

        if warning is not None:
            record = PressureWarning(self._seq, band, ratio, tid, warning)
            self.sink.emit(record)
            self._record("operator", "warn", band=band, ratio=ratio, ticket_id=tid, message=warning)

        self._record(
            "work",
            "admit" if admitted else ("defer" if band == "shed" else "refuse"),
            band=band,
            ratio=ratio,
            ticket_id=tid,
            kind=kind,
            optional=optional,
            holder_pid=holder_pid,
            reason=reason,
        )
        return Admit(
            admitted=admitted,
            band=band,
            ratio=ratio,
            ticket_id=tid,
            kind=kind,
            optional=optional,
            reason=reason,
            warning=warning,
            shed_ticket_ids=shed_ids,
            holder_pid=holder_pid,
            holder_state=holder_state,
        )

    def _shed_optional_queue(self, band: str, ratio: float) -> list[str]:
        shed = self.queue.shed_optional()
        for ticket in shed:
            self._record(
                "work",
                "shed",
                band=band,
                ratio=ratio,
                ticket_id=ticket.ticket_id,
                kind=ticket.kind,
                optional=True,
                holder_pid=ticket.holder_pid,
            )
        return [t.ticket_id for t in shed]


# --------------------------------------------------------------------------- read-only /proc


def snapshot_pids(proc: Path = PROC) -> set[int]:
    """Every numeric entry of ``/proc`` right now."""
    root = Path(proc)
    if not root.is_dir():
        return set()
    return {int(entry.name) for entry in root.iterdir() if entry.name.isdigit()}


def pid_state(pid: int | None, proc: Path = PROC) -> str | None:
    """The one-letter state from ``/proc/<pid>/stat`` (R, S, D, Z, T, ...), or None when gone."""
    if pid is None or pid <= 0:
        return None
    try:
        stat = (Path(proc) / str(pid) / "stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    # comm may contain spaces and parentheses; the state follows the last ')'.
    _, _, rest = stat.rpartition(")")
    fields = rest.split()
    return fields[0] if fields else None


def pid_is_live(pid: int | None, proc: Path = PROC) -> bool:
    """True when the pid is in the table and neither a zombie (Z) nor dead (X)."""
    state = pid_state(pid, proc)
    return state is not None and state not in {"Z", "X", "x"}
