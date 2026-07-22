"""Portable process singleton lease with atomic owner metadata."""

from __future__ import annotations

import atexit
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, IO


class SingletonLockError(RuntimeError):
    def __init__(self, path: Path, owner_pid: int | None):
        self.path = path
        self.owner_pid = owner_pid
        owner = str(owner_pid) if owner_pid is not None else "unknown"
        super().__init__(f"singleton lock {path} is held by owner PID {owner}")


def _lock_file(handle: IO[bytes]) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise BlockingIOError from exc
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_file(handle: IO[bytes]) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_owner(path: Path) -> int | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data["pid"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


class SingletonLease:
    def __init__(self, path: Path, handle: IO[bytes], token: str, stale_seconds: float):
        self.path = path
        self.lock_path = path.with_name(f"{path.name}.lock")
        self.owner_pid = os.getpid()
        self.acquired_at = time.time()
        self.stale_seconds = stale_seconds
        self._handle = handle
        self._token = token
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        try:
            try:
                current = json.loads(self.path.read_text(encoding="utf-8"))
                if current.get("token") == self._token:
                    self.path.unlink(missing_ok=True)
            except (OSError, json.JSONDecodeError):
                pass
            _unlock_file(self._handle)
        finally:
            self._handle.close()
            self._released = True

    def __enter__(self) -> "SingletonLease":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.release()


def acquire_singleton_lock(
    path: Path | str, stale_seconds: float = 3600
) -> SingletonLease:
    """Acquire a singleton lease or raise with the current owner PID.

    ``stale_seconds`` is recorded for diagnostics. An unlocked OS lock is always
    safe to reclaim regardless of stale metadata; a locked process is never killed.
    """
    owner_path = Path(path)
    owner_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = owner_path.with_name(f"{owner_path.name}.lock")
    handle = lock_path.open("a+b")
    if lock_path.stat().st_size == 0:
        handle.write(b"0")
        handle.flush()
    try:
        _lock_file(handle)
    except BlockingIOError:
        handle.close()
        raise SingletonLockError(owner_path, _read_owner(owner_path)) from None

    token = uuid.uuid4().hex
    lease = SingletonLease(owner_path, handle, token, stale_seconds)
    try:
        _atomic_write_json(
            owner_path,
            {
                "pid": lease.owner_pid,
                "timestamp": lease.acquired_at,
                "stale_seconds": stale_seconds,
                "token": token,
            },
        )
    except BaseException:
        lease.release()
        raise
    atexit.register(lease.release)
    return lease
