#!/usr/bin/env python3
"""Shard21 w3: port TST-0161 lease.py _PathLock from fcntl to msvcrt."""
from pathlib import Path

P = Path.home() / "p2-g1" / "command-center" / "p2-wave" / "probes" / "TST-0161" / "lease.py"
src = P.read_text(encoding="utf-8")

old_import = """import fcntl
import hashlib
"""
new_import = """import hashlib
"""
assert old_import in src, "import block"
src = src.replace(old_import, new_import, 1)

old_lock = '''class _PathLock:
    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self.fd: int | None = None

    def __enter__(self) -> "_PathLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_exc: object) -> None:
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
                self.fd = None
'''
new_lock = '''class _PathLock:
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
'''
assert old_lock in src, "_PathLock"
src = src.replace(old_lock, new_lock, 1)

p = P.write_text(src, encoding="utf-8", newline="\n")
print("patched", P)
