#!/usr/bin/env python3
"""File-lease manager with fencing tokens and optional write-time recheck.

Two sessions requesting the same live path get an explicit LEASE_CONFLICT
object (not last-wins, not silence). A write publishes only after a
write-time fence recheck. After TTL expiry another session may acquire a
strictly greater fence; the original writer's commit then fails instead of
silently transferring the live write.

The advisory mutant (write_time_recheck=False) still surfaces acquire
conflicts, but commit_write publishes without rechecking. That is the
negative control: an expiring writer continues after ownership moved.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

NowFn = Callable[[], float]


class FakeClock:
    """Injectable clock so expiry tests do not wait on wall time."""

    def __init__(self, t: float = 0.0) -> None:
        self.t = float(t)

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> float:
        self.t += float(dt)
        return self.t


def _path_key(path: str) -> str:
    return hashlib.sha256(path.encode("utf-8")).hexdigest()


def _atomic_write_json(dest: Path, doc: dict[str, Any]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{dest.name}.", suffix=".tmp", dir=str(dest.parent))
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, dest)
    except Exception:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


class _PathLock:
    """Exclusive lockfile guard: fcntl.flock on POSIX, msvcrt.locking on
    Windows (a one-byte range lock, retried until a deadline to mirror the
    blocking LOCK_EX semantics)."""

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self.fd: int | None = None

    def __enter__(self) -> "_PathLock":
        import time

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        if os.name == "nt":
            import msvcrt

            deadline = time.monotonic() + 30.0
            while True:
                try:
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
                    return self
                except OSError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(0.005)
        import fcntl

        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_exc: object) -> None:
        if self.fd is not None:
            try:
                if os.name == "nt":
                    import msvcrt

                    try:
                        os.lseek(self.fd, 0, os.SEEK_SET)
                        msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                else:
                    import fcntl

                    fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
                self.fd = None


class FileLeaseManager:
    """Per-path leases stored as JSON files, serialized with flock."""

    def __init__(
        self,
        root: Path,
        *,
        clock: FakeClock | None = None,
        write_time_recheck: bool = True,
        now: NowFn | None = None,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.clock = clock or FakeClock(1000.0)
        self.write_time_recheck = bool(write_time_recheck)
        self._now = now or self.clock.now
        self.locks = self.root / "locks"
        self.leases = self.root / "leases"
        self.published = self.root / "published"
        self.staging = self.root / "staging"
        for d in (self.locks, self.leases, self.published, self.staging):
            d.mkdir(parents=True, exist_ok=True)

    def now(self) -> float:
        return float(self._now())

    def _lock(self, path: str) -> _PathLock:
        return _PathLock(self.locks / f"{_path_key(path)}.lock")

    def _lease_file(self, path: str) -> Path:
        return self.leases / f"{_path_key(path)}.json"

    def _pub_file(self, path: str) -> Path:
        return self.published / _path_key(path)

    def _load(self, path: str) -> dict[str, Any] | None:
        fp = self._lease_file(path)
        if not fp.is_file():
            return None
        try:
            rec = json.loads(fp.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(rec, dict):
            return None
        return rec

    def _live(self, rec: dict[str, Any] | None) -> dict[str, Any] | None:
        if rec is None:
            return None
        exp = float(rec.get("expires_at") or 0)
        if exp <= self.now():
            return None
        return rec

    def acquire(self, session_id: str, path: str, *, ttl_s: float = 30.0) -> dict[str, Any]:
        if not session_id or not path:
            return {
                "ok": False,
                "kind": "INVALID",
                "path": path,
                "requester": session_id,
                "reason": "session-or-path-empty",
            }
        with self._lock(path):
            rec = self._load(path)
            live = self._live(rec)
            now = self.now()
            if live is not None:
                if live.get("holder") == session_id:
                    live["expires_at"] = now + float(ttl_s)
                    live["renewed_at"] = now
                    _atomic_write_json(self._lease_file(path), live)
                    return {
                        "ok": True,
                        "kind": "GRANT",
                        "path": path,
                        "holder": session_id,
                        "fence": int(live["fence"]),
                        "expires_at": live["expires_at"],
                        "renewed": True,
                    }
                return {
                    "ok": False,
                    "kind": "LEASE_CONFLICT",
                    "path": path,
                    "requester": session_id,
                    "holder": live.get("holder"),
                    "holder_fence": int(live.get("fence") or 0),
                    "expires_at": live.get("expires_at"),
                    "reason": "path-already-leased",
                }
            prev_fence = int(rec["fence"]) if rec and rec.get("fence") is not None else 0
            fence = prev_fence + 1
            grant = {
                "path": path,
                "holder": session_id,
                "fence": fence,
                "acquired_at": now,
                "expires_at": now + float(ttl_s),
                "ttl_s": float(ttl_s),
            }
            _atomic_write_json(self._lease_file(path), grant)
            return {
                "ok": True,
                "kind": "GRANT",
                "path": path,
                "holder": session_id,
                "fence": fence,
                "expires_at": grant["expires_at"],
                "renewed": False,
                "previous_fence": prev_fence,
            }

    def begin_write(
        self, session_id: str, path: str, fence: int, payload: bytes
    ) -> dict[str, Any]:
        stage = self.staging / f"{session_id}--{_path_key(path)}"
        stage.write_bytes(payload)
        handle = {
            "ok": True,
            "kind": "WRITE_BEGUN",
            "session_id": session_id,
            "path": path,
            "fence": int(fence),
            "stage": str(stage),
            "payload_bytes": len(payload),
        }
        if self.write_time_recheck:
            with self._lock(path):
                live = self._live(self._load(path))
                denied = self._deny_if_stale(session_id, path, fence, live)
                if denied is not None:
                    denied["phase"] = "begin_write"
                    denied["staged"] = True
                    return denied
        return handle

    def commit_write(self, handle: dict[str, Any]) -> dict[str, Any]:
        session_id = str(handle.get("session_id") or "")
        path = str(handle.get("path") or "")
        fence = int(handle.get("fence") or 0)
        stage = Path(str(handle.get("stage") or ""))
        payload = stage.read_bytes() if stage.is_file() else b""
        with self._lock(path):
            live = self._live(self._load(path))
            if self.write_time_recheck:
                denied = self._deny_if_stale(session_id, path, fence, live)
                if denied is not None:
                    denied["phase"] = "commit_write"
                    denied["would_have_published_bytes"] = len(payload)
                    return denied
            dest = self._pub_file(path)
            dest.write_bytes(payload)
            rec = self._load(path) or {}
            return {
                "ok": True,
                "kind": "WRITE_COMMITTED",
                "path": path,
                "writer": session_id,
                "fence": fence,
                "published_bytes": len(payload),
                "holder_at_commit": rec.get("holder"),
                "write_time_recheck": self.write_time_recheck,
            }

    def checked_write(
        self, session_id: str, path: str, fence: int, payload: bytes
    ) -> dict[str, Any]:
        begun = self.begin_write(session_id, path, fence, payload)
        if not begun.get("ok"):
            return begun
        return self.commit_write(begun)

    def read_published(self, path: str) -> bytes | None:
        fp = self._pub_file(path)
        if not fp.is_file():
            return None
        return fp.read_bytes()

    def _deny_if_stale(
        self,
        session_id: str,
        path: str,
        fence: int,
        live: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        rec = self._load(path)
        current_fence = int(rec["fence"]) if rec and rec.get("fence") is not None else 0
        current_holder = rec.get("holder") if rec else None
        if live is None:
            return {
                "ok": False,
                "kind": "LEASE_EXPIRED",
                "path": path,
                "writer": session_id,
                "presented_fence": int(fence),
                "current_holder": current_holder,
                "current_fence": current_fence,
                "reason": "lease-expired-or-absent",
            }
        if live.get("holder") != session_id or int(live.get("fence") or 0) != int(fence):
            return {
                "ok": False,
                "kind": "STALE_FENCE",
                "path": path,
                "writer": session_id,
                "presented_fence": int(fence),
                "current_holder": live.get("holder"),
                "current_fence": int(live.get("fence") or 0),
                "reason": "ownership-transferred-or-fence-mismatch",
            }
        return None
