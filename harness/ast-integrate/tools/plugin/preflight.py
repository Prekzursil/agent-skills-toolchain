"""Install preflight gate (IMP-0029): distinct exit codes for disk / permission /
client WRITE lock / lifecycle lock, each backed by an OS-level observation.

Exit codes: 0 ok, 11 disk full, 12 target not writable, 13 a client holds a
WRITE lock on ``plugin.json``, 14 the ``.plugin-lifecycle.lock`` is held by
another lifecycle operation. Disk and permission never retry; the client lock
is re-checked ``client_retries`` times with ``backoff_s`` between attempts; the
lifecycle lock is a non-blocking ``flock`` so exactly one of two simultaneous
acquirers proceeds.

Fixtures for probes live here too. ``TmpfsVolume`` mounts a real tmpfs: as
root directly, otherwise by moving the calling process into a private user +
mount namespace once (``unshare(CLONE_NEWUSER | CLONE_NEWNS)``), so an
unprivileged probe still gets a genuinely full volume and a genuinely
read-only remount (``ST_RDONLY`` set, writes fail with ``EROFS``). Only when
neither is possible does it degrade to a plain directory, where
``fill_volume`` leaves the ``CAP_MARK`` sentinel so the disk refusal can still
be exercised — that degraded mode is reported in the fill result.

Run as a script the module is the gate CLI; with ``--acquire --hold-seconds N``
it prints ``READY pid=<pid>`` once the lifecycle lock is held and releases it
on SIGINT/SIGTERM without deleting the lock file.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_DISK = 11
EXIT_PERM = 12
EXIT_CLIENT_LOCK = 13
EXIT_LIFECYCLE_LOCK = 14
REASON_OK = "ok"
REASON_DISK = "disk-full"
REASON_PERM = "target-not-writable"
REASON_CLIENT_LOCK = "client-write-lock"
REASON_LIFECYCLE_LOCK = "lifecycle-lock-held"
LOCK_NAME = ".plugin-lifecycle.lock"
CAP_MARK = ".preflight-capacity-exhausted"
ST_RDONLY = int(getattr(os, "ST_RDONLY", 1))
FILL_CAP_BYTES = 64 * 1024 * 1024
FILL_FLOOR_BYTES = 4096


# --------------------------------------------------------------------------- OS views
def os_statvfs_view(path: Path | str) -> dict[str, Any]:
    """statvfs facts the gate and the probes both read: free bytes and the RDONLY flag."""
    st = os.statvfs(os.fspath(path))
    f_flag = int(getattr(st, "f_flag", 0))
    return {
        "f_bavail": int(st.f_bavail),
        "f_frsize": int(st.f_frsize),
        "f_blocks": int(st.f_blocks),
        "f_flag": f_flag,
        "free_bytes": int(st.f_bavail) * int(st.f_frsize),
        "rdonly": bool(f_flag & ST_RDONLY),
    }


def os_free_bytes(path: Path | str) -> int:
    """``f_bavail * f_frsize`` — bytes an unprivileged writer can still use."""
    return os_statvfs_view(path)["free_bytes"]


def parse_proc_locks() -> list[dict[str, Any]]:
    """Rows of ``/proc/locks`` (holders only; ``->`` waiter rows are skipped)."""
    rows: list[dict[str, Any]] = []
    try:
        raw = Path("/proc/locks").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rows
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            pid = int(parts[4])
            maj_s, min_s, ino_s = parts[5].split(":")
            major, minor, ino = int(maj_s, 16), int(min_s, 16), int(ino_s, 10)
        except ValueError:
            continue
        rows.append(
            {
                "raw": line.strip(),
                "kind": parts[1],
                "class": parts[2],
                "mode": parts[3],
                "pid": pid,
                "major": major,
                "minor": minor,
                "ino": ino,
            }
        )
    return rows


def locks_for(path: Path | str, rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """``/proc/locks`` rows whose device+inode is *path* (empty when it does not exist)."""
    try:
        st = os.stat(os.fspath(path))
    except OSError:
        return []
    major, minor, ino = os.major(st.st_dev), os.minor(st.st_dev), int(st.st_ino)
    rows = parse_proc_locks() if rows is None else rows
    return [r for r in rows if r["major"] == major and r["minor"] == minor and r["ino"] == ino]


def locks_on_path(path: Path | str) -> list[dict[str, Any]]:
    """Alias of :func:`locks_for` (receipt emitters call it by this name)."""
    return locks_for(path)


def write_lock_holders(path: Path | str) -> list[int]:
    """PIDs of live processes holding a WRITE lock on *path* according to /proc/locks."""
    pids = sorted({int(r["pid"]) for r in locks_for(path) if r["mode"] == "WRITE"})
    return [pid for pid in pids if pid > 0 and Path(f"/proc/{pid}").is_dir()]


# --------------------------------------------------------------------------- namespace
_NS_STATE: dict[str, Any] = {"entered": False, "ok": False, "error": "", "uid": None}


def namespace_state() -> dict[str, Any]:
    return dict(_NS_STATE)


def enter_private_mount_namespace() -> bool:
    """Move THIS process into a private user + mount namespace (once).

    Inside it the process is uid 0 of its own namespace and may mount tmpfs
    and remount it read-only without host privileges. Nothing propagates back
    to the host mount table. Returns False (and records why) when the kernel
    or the runtime forbids it; callers then fall back to plain directories.
    """
    if _NS_STATE["entered"]:
        return bool(_NS_STATE["ok"])
    _NS_STATE["entered"] = True
    if os.name == "nt" or not hasattr(os, "unshare"):
        _NS_STATE["error"] = "os.unshare unavailable"
        return False
    if os.geteuid() == 0:
        _NS_STATE["ok"] = True
        _NS_STATE["error"] = "already root; no namespace needed"
        return True
    uid, gid = os.getuid(), os.getgid()
    _NS_STATE["uid"] = uid
    try:
        os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNS)
    except OSError as exc:
        _NS_STATE["error"] = f"unshare: {exc}"
        return False
    try:
        Path("/proc/self/setgroups").write_text("deny\n", encoding="ascii")
        Path("/proc/self/uid_map").write_text(f"0 {uid} 1\n", encoding="ascii")
        Path("/proc/self/gid_map").write_text(f"0 {gid} 1\n", encoding="ascii")
    except OSError as exc:
        _NS_STATE["error"] = f"id map: {exc}"
        return False
    subprocess.run(["mount", "--make-rprivate", "/"], capture_output=True)
    _NS_STATE["ok"] = True
    return True


def _mount_tmpfs(path: Path, size: str) -> bool:
    proc = subprocess.run(
        ["mount", "-t", "tmpfs", "-o", f"size={size}", "tmpfs", str(path)],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


class TmpfsVolume:
    """Context manager yielding a mounted tmpfs of *size* (or a plain dir if impossible)."""

    def __init__(self, size: str) -> None:
        self.size = size
        self.path: Path | None = None
        self._mounted = False
        self.mode = "unmounted"

    def __enter__(self) -> Path:
        self.path = Path(tempfile.mkdtemp(prefix="preflight-vol-"))
        self._mounted = _mount_tmpfs(self.path, self.size)
        if self._mounted:
            self.mode = "root-mount"
        elif enter_private_mount_namespace():
            self._mounted = _mount_tmpfs(self.path, self.size)
            self.mode = "userns-mount" if self._mounted else "plain-dir"
        else:
            self.mode = "plain-dir"
        (self.path / ".size").write_text(self.size, encoding="utf-8")
        return self.path

    @property
    def mounted(self) -> bool:
        return self._mounted

    def __exit__(self, *exc: Any) -> None:
        if self.path is None:
            return
        if self._mounted:
            done = subprocess.run(["umount", str(self.path)], capture_output=True)
            if done.returncode != 0:
                subprocess.run(["umount", "-l", str(self.path)], capture_output=True)
        shutil.rmtree(self.path, ignore_errors=True)


def remount_ro(path: Path) -> bool:
    """Make *path* read-only: a real remount when possible, else chmod (returns True when RDONLY is set)."""
    path = Path(path)
    if os.name != "nt":
        for opts in ("remount,ro", "remount,bind,ro"):
            proc = subprocess.run(["mount", "-o", opts, str(path)], capture_output=True)
            if proc.returncode == 0:
                try:
                    if os_statvfs_view(path)["rdonly"]:
                        return True
                except OSError:
                    return True
    os.chmod(path, 0o555)
    for p in path.rglob("*"):
        try:
            os.chmod(p, 0o444 if p.is_file() else 0o555)
        except OSError:
            continue
    return False


def fill_volume(path: Path, leave_free: int = 0) -> dict[str, Any]:
    """Consume the volume down to *leave_free* bytes; reports what statvfs sees afterwards.

    On a real (mounted) volume the fill genuinely exhausts it. On a plain
    directory the fill stops at ``FILL_CAP_BYTES`` and the ``CAP_MARK``
    sentinel is written so ``run_preflight`` still refuses; ``capacity_mark``
    in the result says which happened.
    """
    path = Path(path)
    written = 0
    blob = path / "fill.bin"
    chunk = b"X" * 65536
    try:
        with blob.open("wb") as fh:
            while True:
                free = os_free_bytes(path)
                if free <= leave_free + FILL_FLOOR_BYTES:
                    break
                fh.write(chunk)
                fh.flush()
                written += len(chunk)
                if written > FILL_CAP_BYTES:
                    break
    except OSError:
        pass
    view = os_statvfs_view(path)
    exhausted = view["free_bytes"] <= leave_free + FILL_FLOOR_BYTES
    marked = False
    if leave_free <= 0 and not exhausted:
        try:
            (path / CAP_MARK).write_text("full\n", encoding="utf-8")
            marked = True
        except OSError:
            marked = False
    return {
        "written": written,
        "leave_free": leave_free,
        "f_bavail": view["f_bavail"],
        "f_frsize": view["f_frsize"],
        "free_bytes": view["free_bytes"],
        "exhausted": exhausted,
        "capacity_mark": marked,
    }


# --------------------------------------------------------------------------- locks
@dataclass
class Lock:
    path: Path
    fd: int

    def release(self, unlink: bool = True) -> None:
        """Drop the flock and close the fd; *unlink* removes the lock file too."""
        try:
            if os.name != "nt":
                import fcntl

                fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
        except OSError:
            pass
        if unlink:
            try:
                self.path.unlink()
            except OSError:
                pass


@dataclass
class PreflightResult:
    exit_code: int
    reason: str
    lock: Lock | None = None
    observation: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.exit_code == EXIT_OK

    def as_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "reason": self.reason,
            "lock_held": self.lock is not None,
            "lock_path": str(self.lock.path) if self.lock is not None else None,
            "observation": self.observation,
        }


def _locked(path: Path) -> bool:
    """True when another open file description holds an exclusive flock on *path*."""
    path = Path(path)
    if not path.exists():
        return False
    if os.name == "nt":
        try:
            fh = open(path, "a+")
            fh.close()
            return False
        except OSError:
            return True
    import fcntl

    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        os.close(fd)


def _lock_state(path: Path) -> tuple[bool, list[int]]:
    """(locked, holder pids): flock probe OR-ed with the /proc/locks WRITE holders."""
    path = Path(path)
    if not path.exists():
        return False, []
    holders = write_lock_holders(path)
    return (_locked(path) or bool(holders)), holders


def _acquire(path: Path) -> Lock | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    if os.name != "nt":
        import fcntl

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return None
    return Lock(path, fd)


# --------------------------------------------------------------------------- the gate
def run_preflight(
    target: Path,
    payload_bytes: int = 0,
    backup_bytes: int = 0,
    acquire: bool = False,
    client_retries: int = 1,
    backoff_s: float = 0,
) -> PreflightResult:
    """Refuse with a distinct code per precondition, else (optionally) hold the lifecycle lock.

    Order: disk (statvfs free vs payload+backup), permission (W_OK and not
    ST_RDONLY), client WRITE lock on ``plugin.json`` (retried), lifecycle
    lock. ``observation`` carries the OS facts each verdict rests on.
    """
    target = Path(target)
    need = int(payload_bytes) + int(backup_bytes)
    obs: dict[str, Any] = {}
    try:
        view = os_statvfs_view(target)
    except OSError as exc:
        view = {"f_bavail": 0, "f_frsize": 0, "f_flag": 0, "free_bytes": 0, "rdonly": False,
                "error": f"{type(exc).__name__}: {exc}"}
    marked = (target / CAP_MARK).is_file()
    obs["disk"] = {
        "free_bytes": int(view["free_bytes"]),
        "needed_bytes": need,
        "f_bavail": view["f_bavail"],
        "f_frsize": view["f_frsize"],
        "capacity_mark": marked,
    }
    if marked or int(view["free_bytes"]) < need:
        return PreflightResult(EXIT_DISK, REASON_DISK, observation=obs)
    writable = os.access(target, os.W_OK) and not bool(view["rdonly"])
    obs["perm"] = {"writable": writable, "rdonly": bool(view["rdonly"]), "f_flag": view["f_flag"]}
    if not writable:
        return PreflightResult(EXIT_PERM, REASON_PERM, observation=obs)

    plugin_json = target / "plugin.json"
    attempts = max(1, int(client_retries))
    for attempt in range(1, attempts + 1):
        locked, holders = _lock_state(plugin_json)
        obs["client_lock"] = {
            "path": str(plugin_json),
            "locked": locked,
            "holders": holders,
            "attempt": attempt,
            "attempts": attempts,
            "backoff_s": backoff_s,
        }
        if not locked:
            break
        if attempt < attempts:
            if backoff_s:
                time.sleep(float(backoff_s) * attempt)
            continue
        return PreflightResult(EXIT_CLIENT_LOCK, REASON_CLIENT_LOCK, observation=obs)

    lock_path = target / LOCK_NAME
    if acquire:
        held = _acquire(lock_path)
        obs["lifecycle"] = {
            "path": str(lock_path),
            "acquired": held is not None,
            "holders": write_lock_holders(lock_path) if held is None else [os.getpid()],
        }
        if held is None:
            return PreflightResult(EXIT_LIFECYCLE_LOCK, REASON_LIFECYCLE_LOCK, observation=obs)
        return PreflightResult(EXIT_OK, REASON_OK, lock=held, observation=obs)
    locked, holders = _lock_state(lock_path)
    obs["lifecycle"] = {"path": str(lock_path), "acquired": False, "locked": locked, "holders": holders}
    if locked:
        return PreflightResult(EXIT_LIFECYCLE_LOCK, REASON_LIFECYCLE_LOCK, observation=obs)
    return PreflightResult(EXIT_OK, REASON_OK, observation=obs)


# --------------------------------------------------------------------------- holders
def spawn_lock_holder(path: Path, timeout_s: float = 5.0) -> subprocess.Popen:
    """Start a child that holds an exclusive WRITE flock on *path*; returns once it does.

    The handshake polls ``/proc/locks`` for the child's pid (falling back to
    the flock probe), so a caller's very next preflight already sees the lock.
    ``proc.lock_confirmed`` records whether the hold was observed in time.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "import os,sys,time\n"
        "p=sys.argv[1]\n"
        "fd=os.open(p, os.O_RDWR|os.O_CREAT, 0o644)\n"
        "os.write(fd, b'hold\\n')\n"
    )
    if os.name != "nt":
        script += "import fcntl\nfcntl.flock(fd, fcntl.LOCK_EX)\n"
    script += "sys.stdout.write('READY\\n'); sys.stdout.flush()\ntime.sleep(30)\n"
    proc = subprocess.Popen(
        [os.environ.get("PYTHON", sys.executable or "python3"), "-c", script, str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    confirmed = False
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        holders = write_lock_holders(path)
        if proc.pid in holders or (not holders and os.name != "nt" and _locked(path)):
            confirmed = True
            break
        time.sleep(0.02)
    proc.lock_confirmed = confirmed  # type: ignore[attr-defined]
    return proc


def stop_holder(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except Exception:
        proc.kill()
        try:
            proc.wait(timeout=2)
        except Exception:
            pass


# --------------------------------------------------------------------------- CLI
def _hold(lock: Lock, seconds: float) -> str:
    """Keep *lock* until *seconds* elapse or SIGINT/SIGTERM; release without unlinking."""

    def _stop(signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt(signum)

    previous = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, _stop)
    outcome = "expired"
    try:
        deadline = time.monotonic() + max(0.0, seconds)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.05, remaining))
    except KeyboardInterrupt as exc:
        outcome = f"signal={exc.args[0] if exc.args else 'SIGINT'}"
    finally:
        lock.release(unlink=False)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return outcome


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="preflight.py",
        description="Lifecycle preflight gate: 0 ok, 11 disk, 12 perm, 13 client lock, 14 lifecycle lock.",
    )
    parser.add_argument("--target", required=True, help="plugin install directory")
    parser.add_argument("--payload-bytes", type=int, default=0)
    parser.add_argument("--backup-bytes", type=int, default=0)
    parser.add_argument("--acquire", action="store_true", help="take the lifecycle lock on success")
    parser.add_argument("--hold-seconds", type=float, default=0.0,
                        help="with --acquire: keep the lock this long (SIGINT/SIGTERM releases it)")
    parser.add_argument("--client-retries", type=int, default=3)
    parser.add_argument("--backoff-s", type=float, default=0.2)
    args = parser.parse_args(argv)

    result = run_preflight(
        Path(args.target),
        payload_bytes=args.payload_bytes,
        backup_bytes=args.backup_bytes,
        acquire=args.acquire,
        client_retries=args.client_retries,
        backoff_s=args.backoff_s,
    )
    print(json.dumps(result.as_dict(), sort_keys=True, default=str), flush=True)
    if result.lock is not None:
        print(f"READY pid={os.getpid()} lock={result.lock.path}", flush=True)
        if args.hold_seconds > 0:
            outcome = _hold(result.lock, args.hold_seconds)
        else:
            result.lock.release(unlink=False)
            outcome = "released"
        print(f"RELEASED pid={os.getpid()} outcome={outcome}", flush=True)
    return int(result.exit_code)


__all__ = [
    "CAP_MARK",
    "EXIT_CLIENT_LOCK",
    "EXIT_DISK",
    "EXIT_LIFECYCLE_LOCK",
    "EXIT_OK",
    "EXIT_PERM",
    "LOCK_NAME",
    "Lock",
    "PreflightResult",
    "REASON_CLIENT_LOCK",
    "REASON_DISK",
    "REASON_LIFECYCLE_LOCK",
    "REASON_OK",
    "REASON_PERM",
    "TmpfsVolume",
    "enter_private_mount_namespace",
    "fill_volume",
    "locks_for",
    "locks_on_path",
    "main",
    "namespace_state",
    "os_free_bytes",
    "os_statvfs_view",
    "parse_proc_locks",
    "remount_ro",
    "run_preflight",
    "spawn_lock_holder",
    "stop_holder",
    "write_lock_holders",
]


if __name__ == "__main__":
    raise SystemExit(main())
