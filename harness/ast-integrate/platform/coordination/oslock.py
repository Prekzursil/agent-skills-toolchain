"""OS-level liveness locks - the SECOND, mechanically independent liveness signal.

WHY THIS EXISTS
---------------
Crash recovery needs to answer "is the session that holds this claim still alive?". The obvious
answer - "its heartbeat file is old" - is not admissible. ``rules/common/bash-hud-and-terminal-emit.md``
section 3 records the measurement: a stalled process and a long-completed one are INDISTINGUISHABLE
from file timestamps, and a HUD segment built on that flagged an 11-hour-old finished agent as a
live stall. A stale heartbeat is a fact about the LEASE, never about the PROCESS.

So liveness here is an AND-gate over two signals that do not share a mechanism:

  signal A  heartbeat freshness   - file CONTENT written by the session (userspace)
  signal B  OS advisory lock      - KERNEL state; the lock is released by the operating system
                                    when the holding process exits, whether it exits cleanly,
                                    is killed, or the machine loses power

Signal B is immune to the two failure modes that make PID probes unreliable: PID reuse (a new
process inheriting a dead session's number) and cooperative-cleanup absence (a killed process
never runs its ``finally``). It cannot be forged by a hung process either - a hung process still
holds its lock, which is why "heartbeat stale + lock held" resolves to UNVERIFIED and not to DEAD.

WHAT THIS MODULE DELIBERATELY DOES NOT DO
-----------------------------------------
It does not create the lock file during a probe. ``os.open`` without ``O_CREAT`` is used on the
probe path, so a missing file is ``NOT-COMPUTABLE`` rather than ``FREE``. Creating-then-acquiring
would make every never-registered session look dead, which is the reap-a-live-session failure.

MEASURED SCOPE
--------------
Discrimination (refused while held, granted after the holder exits) is proven on win32 by
``_probe_lock_liveness.py`` and by ``test_oslock.py::test_probe_discriminates_alive_from_dead``,
which spawns a real child process. The POSIX branch uses ``fcntl.flock`` and is NOT-CHECKED on
this box (no Linux/macOS interpreter is exercised by this suite); the experiment that would settle
it is running the same both-states probe under WSL or CI-linux.
"""

from __future__ import annotations

import errno
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import TracebackType
from typing import Any

__all__ = [
    "LockOutcome",
    "LockProbe",
    "LivenessLock",
    "lock_supported",
    "probe_lock",
]

_IS_WINDOWS = sys.platform == "win32"

#: Errno values that mean "another holder has it" rather than "something is broken".
_CONTENDED = frozenset({errno.EACCES, errno.EAGAIN, errno.EDEADLK, errno.EWOULDBLOCK})


class LockOutcome(str, Enum):
    """The three-valued answer. ``NOT-COMPUTABLE`` blocks; it never means FREE."""

    #: Acquired. The previous holder is no longer running (the OS released its lock).
    FREE = "FREE"
    #: Refused. Some process still holds the lock -> its owner is running.
    HELD_BY_OTHER = "HELD-BY-OTHER"
    #: No verdict: file absent, unreadable, unsupported platform, or an unexpected errno.
    NOT_COMPUTABLE = "NOT-COMPUTABLE"


def lock_supported() -> bool:
    """True when this interpreter has a byte-range locking primitive available."""
    try:
        if _IS_WINDOWS:
            import msvcrt  # noqa: F401  - probe only
        else:
            import fcntl  # noqa: F401  - probe only
    except (
        ImportError
    ):  # pragma: no cover - both stdlib modules ship on their platforms
        return False
    return True


def _acquire(fd: int) -> None:
    """Take an exclusive, non-blocking lock on byte 0. Raises OSError when contended."""
    if _IS_WINDOWS:
        import msvcrt

        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:  # pragma: no cover - POSIX branch NOT-CHECKED on this box
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release(fd: int) -> None:
    """Drop the lock. Best-effort: process exit releases it anyway, which is the point."""
    try:
        if _IS_WINDOWS:
            import msvcrt

            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:  # pragma: no cover - POSIX branch NOT-CHECKED on this box
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        # The lock is already gone (or was never taken). Swallowing is correct HERE and only
        # here: release is not a decision point, and the OS guarantees release at exit.
        pass


@dataclass(frozen=True)
class LockProbe:
    """One probe result, with the evidence a receipt needs."""

    outcome: LockOutcome
    path: str
    detail: dict[str, Any]

    @property
    def says_alive(self) -> bool:
        return self.outcome is LockOutcome.HELD_BY_OTHER

    @property
    def says_dead(self) -> bool:
        return self.outcome is LockOutcome.FREE

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe": "oslock",
            "outcome": self.outcome.value,
            "path": self.path,
            **self.detail,
        }


def probe_lock(path: str | Path) -> LockProbe:
    """Non-destructively ask whether another process holds ``path``'s liveness lock.

    Never creates the file. Acquires-then-immediately-releases on success, so a probe does not
    keep the resource: the caller learns the owner is gone without becoming the new owner.
    """
    p = Path(path)
    spec = {"mechanism": "msvcrt.locking" if _IS_WINDOWS else "fcntl.flock"}
    if not lock_supported():  # pragma: no cover - unreachable on CPython win32/posix
        return LockProbe(
            LockOutcome.NOT_COMPUTABLE,
            str(p),
            {**spec, "reason": "no locking primitive"},
        )
    try:
        fd = os.open(p, os.O_RDWR)  # deliberately NO O_CREAT
    except FileNotFoundError:
        return LockProbe(
            LockOutcome.NOT_COMPUTABLE,
            str(p),
            {**spec, "reason": "lock file absent - never registered or already reaped"},
        )
    except OSError as exc:
        return LockProbe(
            LockOutcome.NOT_COMPUTABLE,
            str(p),
            {**spec, "reason": f"open failed: errno={exc.errno} {exc.strerror}"},
        )
    try:
        try:
            _acquire(fd)
        except OSError as exc:
            if exc.errno in _CONTENDED:
                return LockProbe(
                    LockOutcome.HELD_BY_OTHER,
                    str(p),
                    {**spec, "reason": f"contended: errno={exc.errno}"},
                )
            return LockProbe(
                LockOutcome.NOT_COMPUTABLE,
                str(p),
                {**spec, "reason": f"unexpected errno={exc.errno} {exc.strerror}"},
            )
        _release(fd)
        return LockProbe(
            LockOutcome.FREE,
            str(p),
            {**spec, "reason": "acquired then released - no live holder"},
        )
    finally:
        os.close(fd)


class LivenessLock:
    """Held for a session's whole lifetime. Its release IS the death notification.

    Use as a context manager. ``acquired`` is False when another process already holds it, which
    is how a re-registration of a still-live session id is detected rather than double-claimed.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._fd: int | None = None
        self.acquired = False

    def acquire(self) -> bool:
        if self._fd is not None:
            return self.acquired
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT)
        try:
            _acquire(fd)
        except OSError:
            os.close(fd)
            self._fd = None
            self.acquired = False
            return False
        self._fd = fd
        self.acquired = True
        return True

    def release(self) -> None:
        if self._fd is None:
            return
        _release(self._fd)
        os.close(self._fd)
        self._fd = None
        self.acquired = False

    def __enter__(self) -> LivenessLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
