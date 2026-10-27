#!/usr/bin/env python3
"""Live log tailers for TST-0155.

FollowReader is the monitor under test: keep the open fd, detect inode
change (rename-rotate) or size drop (copytruncate), carry a partial line
across the seam, and never re-scan bytes already consumed.

StuckFdReader and RecountOnRotateReader are known-broken fixtures used as
negative controls. They are not the monitor.
"""
from __future__ import annotations

import os
from pathlib import Path


def ident_of_path(path: Path) -> tuple[int, int] | None:
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    return (int(st.st_dev), int(st.st_ino))


def ident_of_fd(fp) -> tuple[int, int] | None:
    if fp is None or fp.closed:
        return None
    try:
        st = os.fstat(fp.fileno())
    except OSError:
        return None
    return (int(st.st_dev), int(st.st_ino))


def _open_shared_delete(path: Path):
    """Open for read with FILE_SHARE_DELETE so a rename-rotate can proceed
    while this reader keeps the fd open. The Windows CRT open shares
    read/write only, which makes os.replace raise WinError 32; POSIX open is
    unchanged. Returns a binary file object."""
    if os.name != "nt":
        return open(path, "rb")
    import ctypes
    import msvcrt

    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x1
    FILE_SHARE_WRITE = 0x2
    FILE_SHARE_DELETE = 0x4
    OPEN_EXISTING = 0x3
    k32 = ctypes.windll.kernel32
    k32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    k32.CreateFileW.restype = ctypes.c_void_p
    handle = k32.CreateFileW(
        str(path),
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise OSError(f"CreateFileW failed for {path} (err={ctypes.GetLastError()})")
    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    return os.fdopen(fd, "rb")


def complete_lines(blob: bytes) -> tuple[list[str], bytes]:
    """Split on \\n only. Trailing fragment is not a line."""
    if not blob:
        return [], b""
    parts = blob.split(b"\n")
    done = [p.decode("utf-8", errors="replace") for p in parts[:-1]]
    return done, parts[-1]


def offline_concat_lines(pre: Path, post: Path) -> tuple[list[str], bytes]:
    """Independent rail: concatenate rotated-then-live bytes, then split."""
    blob = b""
    if pre.is_file():
        blob += pre.read_bytes()
    if post.is_file():
        blob += post.read_bytes()
    return complete_lines(blob)


class FollowReader:
    """tail -F semantics: follow the path across rotation; no recap."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.fp = None
        self.ident: tuple[int, int] | None = None
        self.partial = b""
        self.consumed: list[str] = []
        self.crashed = False
        self.crash_exc: str | None = None
        self.rotations = 0
        self.truncations = 0
        self.polls = 0

    def close(self) -> None:
        if self.fp is not None and not self.fp.closed:
            try:
                self.fp.close()
            except OSError:
                pass
        self.fp = None

    def _open_path(self, start: int = 0) -> None:
        self.close()
        self.fp = _open_shared_delete(self.path)
        if start:
            self.fp.seek(start)
        self.ident = ident_of_fd(self.fp)

    def _drain_fd(self) -> bytes:
        if self.fp is None or self.fp.closed:
            return b""
        try:
            return self.fp.read()
        except OSError as exc:
            self.crashed = True
            self.crash_exc = repr(exc)
            return b""

    def _handle_rotation_or_truncate(self) -> bytes:
        extra = b""
        path_id = ident_of_path(self.path)
        fd_id = ident_of_fd(self.fp)
        if self.fp is None or fd_id is None:
            if path_id is not None:
                self._open_path(0)
            return extra
        if path_id is None:
            extra += self._drain_fd()
            return extra
        if path_id != fd_id:
            extra += self._drain_fd()
            self.rotations += 1
            self._open_path(0)
            return extra
        try:
            size = os.fstat(self.fp.fileno()).st_size
            pos = self.fp.tell()
        except OSError as exc:
            self.crashed = True
            self.crash_exc = repr(exc)
            return extra
        if size < pos:
            self.truncations += 1
            self.fp.seek(0)
        return extra

    def poll(self) -> list[str]:
        self.polls += 1
        if self.crashed:
            return []
        try:
            extra = self._handle_rotation_or_truncate()
            extra += self._drain_fd()
            self.partial += extra
            done, self.partial = complete_lines(self.partial)
            self.consumed.extend(done)
            return done
        except Exception as exc:  # noqa: BLE001 - record, do not crash the monitor
            self.crashed = True
            self.crash_exc = repr(exc)
            return []

    def catch_up(self, rounds: int = 40) -> None:
        for _ in range(max(1, rounds)):
            self.poll()


class StuckFdReader:
    """tail -f without -F: keep the original inode, never reopen the path."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.fp = None
        self.partial = b""
        self.consumed: list[str] = []
        self.crashed = False
        self.crash_exc: str | None = None
        self.polls = 0

    def close(self) -> None:
        if self.fp is not None and not self.fp.closed:
            try:
                self.fp.close()
            except OSError:
                pass
        self.fp = None

    def poll(self) -> list[str]:
        self.polls += 1
        if self.crashed:
            return []
        try:
            if self.fp is None:
                if not self.path.is_file():
                    return []
                self.fp = _open_shared_delete(self.path)
            chunk = self.fp.read()
            self.partial += chunk
            done, self.partial = complete_lines(self.partial)
            self.consumed.extend(done)
            return done
        except Exception as exc:  # noqa: BLE001
            self.crashed = True
            self.crash_exc = repr(exc)
            return []

    def catch_up(self, rounds: int = 40) -> None:
        for _ in range(max(1, rounds)):
            self.poll()


class RecountOnRotateReader:
    """On inode change, re-read the rotated sibling from byte 0 and append.

    That re-counts every line already consumed while the sibling was live.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.rotated = self.path.with_name(self.path.name + ".1")
        self.fp = None
        self.ident: tuple[int, int] | None = None
        self.partial = b""
        self.consumed: list[str] = []
        self.crashed = False
        self.crash_exc: str | None = None
        self.polls = 0
        self.recounts = 0

    def close(self) -> None:
        if self.fp is not None and not self.fp.closed:
            try:
                self.fp.close()
            except OSError:
                pass
        self.fp = None

    def _open_path(self) -> None:
        self.close()
        self.fp = _open_shared_delete(self.path)
        self.ident = ident_of_fd(self.fp)

    def poll(self) -> list[str]:
        self.polls += 1
        if self.crashed:
            return []
        try:
            path_id = ident_of_path(self.path)
            fd_id = ident_of_fd(self.fp)
            extra = b""
            if self.fp is None or fd_id is None:
                if path_id is not None:
                    self._open_path()
            elif path_id is not None and path_id != fd_id:
                extra += self.fp.read()
                if self.rotated.is_file():
                    recap, _frag = complete_lines(self.rotated.read_bytes())
                    self.consumed.extend(recap)
                    self.recounts += len(recap)
                self._open_path()
            if self.fp is not None and not self.fp.closed:
                extra += self.fp.read()
            self.partial += extra
            done, self.partial = complete_lines(self.partial)
            self.consumed.extend(done)
            return done
        except Exception as exc:  # noqa: BLE001
            self.crashed = True
            self.crash_exc = repr(exc)
            return []

    def catch_up(self, rounds: int = 40) -> None:
        for _ in range(max(1, rounds)):
            self.poll()
