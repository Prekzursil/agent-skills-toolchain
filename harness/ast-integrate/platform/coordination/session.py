"""Session registration and discovery, with two-signal liveness.

WHY LIVENESS IS AN AND-GATE AND NOT A TIMESTAMP CHECK

``rules/common/bash-hud-and-terminal-emit.md`` section 3 records the measurement that governs this
module: *"A stalled process and a long-completed one are indistinguishable from mtimes"* - a HUD
segment built on file age reported an 11-hour-old FINISHED agent as a live stall. A stale
heartbeat is a fact about the LEASE, never about the PROCESS.

So every session carries two liveness signals with no shared mechanism:

  signal A  ``heartbeat_at`` freshness       userspace file CONTENT written by the session
  signal B  the OS advisory lock at ``lock_path``  KERNEL state, released by the OS at exit

and the classification is:

  ============================  =============  ==========================================
  A (heartbeat)                 B (OS lock)    liveness
  ============================  =============  ==========================================
  fresh                         held           LIVE
  stale                         free           DEAD          both signals agree
  fresh                         free           UNVERIFIED    disagree - just died, or skew
  stale                         held           UNVERIFIED    running but not heartbeating.
                                               NOT "hung": that claim needs orchestrator
                                               state a file listing does not contain.
  any                           NOT-COMPUTABLE UNVERIFIED    no second signal exists
  record ``closed_at`` set      any            CLOSED        graceful exit, not a crash
  ============================  =============  ==========================================

``UNVERIFIED`` is first-class and it BLOCKS: recovery will not reap an UNVERIFIED session without
an explicit force decision, and lease conflict detection treats UNVERIFIED as CONFLICTING. Both
are fail-closed choices - reaping a live session's claim is the expensive direction of the error,
so the heuristic is graded by error DIRECTION rather than by accuracy.

Vendor is stored raw AND resolved. Discovery filters by CANONICAL identity so ``claude`` and
``anthropic`` are one vendor, which is the DEFECT D1 lesson applied at the session plane.
"""

from __future__ import annotations

import os
import socket
import uuid
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import _libpath  # noqa: F401  - side effect: platform/lib on sys.path
from .errors import StoreCorrupt
from .oslock import LivenessLock, LockOutcome, LockProbe, probe_lock
from .store import Store, safe_record_name

import vendor_identity  # noqa: E402  - resolved by _libpath above

__all__ = [
    "DEFAULT_HEARTBEAT_TTL",
    "Liveness",
    "SessionRecord",
    "SessionView",
    "classify",
    "close_session",
    "discover",
    "heartbeat",
    "register_session",
]

#: Seconds after which a heartbeat is STALE. 90s = 6x the 15s longrun heartbeat interval in
#: AGENTS.md section 4a, so a single missed beat (or a slow Windows commit stall) does not flip a
#: live session to stale. Injected everywhere; never read from a global at a decision point.
DEFAULT_HEARTBEAT_TTL = 90.0


class Liveness(str, Enum):
    LIVE = "LIVE"
    DEAD = "DEAD"
    #: Closed gracefully. Distinct from DEAD: nothing needs recovering.
    CLOSED = "CLOSED"
    #: The two signals disagree, or the second signal does not exist. Blocks automatic reaping.
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class SessionRecord:
    """The durable session row."""

    session_id: str
    vendor: str
    adapter_id: str
    tool: str
    pid: int
    host: str
    cwd: str
    capabilities: tuple[str, ...] = ()
    started_at: float = 0.0
    heartbeat_at: float = 0.0
    heartbeat_seq: int = 0
    closed_at: float | None = None
    lock_name: str = ""
    labels: Mapping[str, str] = field(default_factory=dict)

    @property
    def vendor_canonical(self) -> str | None:
        return vendor_identity.resolve(self.vendor).canonical_id

    @property
    def vendor_resolution(self) -> str:
        return vendor_identity.resolve(self.vendor).resolution.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "session",
            "session_id": self.session_id,
            "vendor": self.vendor,
            "vendor_canonical": self.vendor_canonical,
            "vendor_resolution": self.vendor_resolution,
            "adapter_id": self.adapter_id,
            "tool": self.tool,
            "pid": self.pid,
            "host": self.host,
            "cwd": self.cwd,
            "capabilities": list(self.capabilities),
            "started_at": self.started_at,
            "heartbeat_at": self.heartbeat_at,
            "heartbeat_seq": self.heartbeat_seq,
            "closed_at": self.closed_at,
            "lock_name": self.lock_name,
            "labels": dict(self.labels),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> SessionRecord:
        return cls(
            session_id=str(raw["session_id"]),
            vendor=str(raw["vendor"]),
            adapter_id=str(raw.get("adapter_id", "")),
            tool=str(raw.get("tool", "")),
            pid=int(raw.get("pid", 0)),
            host=str(raw.get("host", "")),
            cwd=str(raw.get("cwd", "")),
            capabilities=tuple(raw.get("capabilities", ())),
            started_at=float(raw.get("started_at", 0.0)),
            heartbeat_at=float(raw.get("heartbeat_at", 0.0)),
            heartbeat_seq=int(raw.get("heartbeat_seq", 0)),
            closed_at=(
                None if raw.get("closed_at") is None else float(raw["closed_at"])
            ),
            lock_name=str(raw.get("lock_name", "")),
            labels=dict(raw.get("labels", {})),
        )


@dataclass(frozen=True)
class SessionView:
    """A session plus its classified liveness and BOTH declared probes.

    ``rules/common/single-signal-verification.md`` rule 6: an undeclared source probe is zero
    signals, not one. Both probes are therefore fields, not derivations.
    """

    record: SessionRecord
    liveness: Liveness
    heartbeat_age: float
    heartbeat_fresh: bool
    lock_probe: LockProbe
    reason: str

    @property
    def session_id(self) -> str:
        return self.record.session_id

    @property
    def needs_recovery(self) -> bool:
        return self.liveness is Liveness.DEAD

    @property
    def blocks_automatic_recovery(self) -> bool:
        return self.liveness is Liveness.UNVERIFIED

    def to_dict(self) -> dict[str, Any]:
        return {
            "session": self.record.to_dict(),
            "liveness": self.liveness.value,
            "reason": self.reason,
            "signals": {
                "A_heartbeat": {
                    "probe": "heartbeat-age",
                    "age_seconds": self.heartbeat_age,
                    "fresh": self.heartbeat_fresh,
                    "mechanism": "userspace file content written by the session",
                },
                "B_oslock": {
                    **self.lock_probe.to_dict(),
                    "mechanism": "kernel advisory lock, released by the OS on process exit",
                },
            },
        }


def lock_path_for(store: Store, session_id: str) -> Path:
    """Where a session's liveness lock lives. Sibling of the session record, never inside it.

    The stem comes from the store's own filename folding, so a session whose id contains a path
    separator cannot end up with its record under one name and its lock under another.
    """
    return store.dir_for("sessions") / f"{safe_record_name(session_id)}.live.lock"


def register_session(
    store: Store,
    *,
    vendor: str,
    adapter_id: str,
    tool: str,
    session_id: str | None = None,
    capabilities: Iterable[str] = (),
    cwd: str | Path | None = None,
    labels: Mapping[str, str] | None = None,
    hold_lock: bool = True,
) -> tuple[SessionRecord, LivenessLock | None]:
    """Register (or re-register) a session and, by default, take its liveness lock.

    Returns the record and the held lock. The caller MUST keep the lock object alive for the
    session's duration - that is the whole liveness mechanism. ``hold_lock=False`` exists for
    tests that need to simulate a crashed session (no holder), and for a reader that only wants
    to write a row.
    """
    store.initialise()
    sid = session_id or f"{tool or 'session'}-{uuid.uuid4().hex[:12]}"
    now = store.clock()
    record = SessionRecord(
        session_id=sid,
        vendor=vendor,
        adapter_id=adapter_id,
        tool=tool,
        pid=os.getpid(),
        host=socket.gethostname(),
        cwd=str(Path(cwd) if cwd is not None else Path.cwd()),
        capabilities=tuple(sorted(set(capabilities))),
        started_at=now,
        heartbeat_at=now,
        heartbeat_seq=0,
        closed_at=None,
        lock_name=lock_path_for(store, sid).name,
        labels=dict(labels or {}),
    )
    lock: LivenessLock | None = None
    if hold_lock:
        lock = LivenessLock(lock_path_for(store, sid))
        lock.acquire()
    else:
        # Create the file so the probe can distinguish "crashed holder" (FREE) from "never
        # registered" (NOT-COMPUTABLE). probe_lock never creates it.
        path = lock_path_for(store, sid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
    store.write_atomic(store.path_for("sessions", sid), record.to_dict())
    store.journal(
        "session.register",
        session_id=sid,
        vendor=record.vendor,
        vendor_canonical=record.vendor_canonical,
        adapter_id=adapter_id,
        lock_held=bool(lock and lock.acquired),
    )
    return record, lock


def _load(store: Store, session_id: str, verb: str) -> tuple[Path, SessionRecord]:
    path = store.path_for("sessions", session_id)
    raw = store.read(path)
    if raw is None:
        raise StoreCorrupt(f"{verb} for unregistered session {session_id!r}")
    return path, SessionRecord.from_dict(raw)


def heartbeat(store: Store, session_id: str) -> SessionRecord:
    """Advance a session's heartbeat. Monotonic sequence + wall clock, both recorded."""
    path, record = _load(store, session_id, "heartbeat")
    updated = replace(
        record, heartbeat_at=store.clock(), heartbeat_seq=record.heartbeat_seq + 1
    )
    store.write_atomic(path, updated.to_dict())
    return updated


def close_session(store: Store, session_id: str) -> SessionRecord:
    """Mark a graceful exit. CLOSED is not DEAD: nothing needs recovering from a clean close."""
    path, record = _load(store, session_id, "close")
    updated = replace(record, closed_at=store.clock())
    store.write_atomic(path, updated.to_dict())
    store.journal("session.close", session_id=session_id)
    return updated


def classify(
    store: Store,
    record: SessionRecord,
    *,
    now: float | None = None,
    heartbeat_ttl: float = DEFAULT_HEARTBEAT_TTL,
) -> SessionView:
    """Apply the two-signal AND-gate to one session record."""
    at = store.clock() if now is None else now
    age = max(0.0, at - record.heartbeat_at)
    fresh = age <= heartbeat_ttl
    lock = probe_lock(lock_path_for(store, record.session_id))

    # The OS lock is a KERNEL fact about THIS machine. If the record was written on another host
    # (a store on a network share), acquiring the lock here says nothing about a process there -
    # this host's kernel never saw it, so a successful acquisition would wrongly read as DEAD and
    # reap a live remote session. Signal B is therefore INADMISSIBLE across hosts, and one signal
    # is not evidence. Leak L-06.
    local_host = socket.gethostname()
    if record.host and record.host != local_host:
        return SessionView(
            record,
            Liveness.UNVERIFIED,
            age,
            fresh,
            lock,
            f"session was registered on host {record.host!r} but this probe runs on "
            f"{local_host!r}; the OS lock is a fact about the LOCAL kernel only, so signal B is "
            "inadmissible and no second signal exists",
        )

    if record.closed_at is not None:
        return SessionView(
            record,
            Liveness.CLOSED,
            age,
            fresh,
            lock,
            "record declares a graceful close; no recovery required",
        )
    if lock.outcome is LockOutcome.NOT_COMPUTABLE:
        return SessionView(
            record,
            Liveness.UNVERIFIED,
            age,
            fresh,
            lock,
            "no second signal: "
            + str(lock.detail.get("reason", "lock not computable"))
            + " - one signal is not evidence",
        )
    if fresh and lock.says_alive:
        return SessionView(
            record,
            Liveness.LIVE,
            age,
            fresh,
            lock,
            "both signals agree the session is running",
        )
    if not fresh and lock.says_dead:
        return SessionView(
            record,
            Liveness.DEAD,
            age,
            fresh,
            lock,
            f"both signals agree: heartbeat {age:.1f}s old (>{heartbeat_ttl:.0f}s) and the OS "
            "released the liveness lock",
        )
    if fresh and lock.says_dead:
        return SessionView(
            record,
            Liveness.UNVERIFIED,
            age,
            fresh,
            lock,
            "signals disagree: heartbeat is fresh but the OS lock is free - the process may have "
            "died inside the TTL window, or the clocks are skewed",
        )
    return SessionView(
        record,
        Liveness.UNVERIFIED,
        age,
        fresh,
        lock,
        f"signals disagree: heartbeat {age:.1f}s old but the process still holds its lock. This "
        "is NOT reported as hung - proving 'stuck' needs orchestrator state that a file listing "
        "does not contain",
    )


def discover(
    store: Store,
    *,
    now: float | None = None,
    heartbeat_ttl: float = DEFAULT_HEARTBEAT_TTL,
    vendor: str | None = None,
    liveness: Iterable[Liveness] | None = None,
) -> tuple[SessionView, ...]:
    """Enumerate every registered session, classified.

    ``vendor`` filters by CANONICAL identity, so ``discover(vendor="claude")`` finds a session
    registered as ``anthropic``. A raw string filter would miss it - the D1 failure at the
    session plane.
    """
    want_canonical: str | None = None
    if vendor is not None:
        ident = vendor_identity.resolve(vendor)
        want_canonical = ident.canonical_id
        if want_canonical is None:
            return ()
    wanted_liveness = set(liveness) if liveness is not None else None

    views: list[SessionView] = []
    for _name, raw in store.iter_records("sessions"):
        record = SessionRecord.from_dict(raw)
        if want_canonical is not None and record.vendor_canonical != want_canonical:
            continue
        view = classify(store, record, now=now, heartbeat_ttl=heartbeat_ttl)
        if wanted_liveness is not None and view.liveness not in wanted_liveness:
            continue
        views.append(view)
    return tuple(sorted(views, key=lambda v: v.session_id))
