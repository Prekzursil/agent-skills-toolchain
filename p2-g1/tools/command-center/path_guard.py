"""Named filesystem guards for command-center writers and walkers.

ADV-0117 owns reserved device names, MAX_PATH, case-only collisions, spaces,
non-ASCII and trailing dots. This module covers the residue that matrix does
not touch:

* UNC ``\\\\server\\share`` / ``file://server/share`` after normalisation
  (rules/common/bash-hud-and-terminal-emit.md 6 — a synthesised UNC coerces
  outbound SMB/NTLM).
* symlink (and, on Windows, junction) traversal out of a scratch root.
* a write into an ACL-denied / unwritable directory (named PermissionDenied).
* an open file held by another process (named FileLocked, not a partial write).

Callers must use these helpers rather than bare ``Path.write_text`` /
``Path.rglob`` when the path is attacker-influenceable.
"""

from __future__ import annotations

import errno
import fnmatch
import os
import re
from collections.abc import Iterator
from pathlib import Path

__all__ = (
    "ContainmentBreach",
    "FileLocked",
    "PathGuardError",
    "PermissionDenied",
    "UncRejected",
    "contained_rglob",
    "guarded_append_text",
    "guarded_write_text",
    "looks_like_unc",
    "reject_unc",
)


class PathGuardError(Exception):
    """Base for named path-guard failures. ``.name`` is the stable token."""

    name = "PathGuardError"

    def __init__(self, message: str, *, path: Path | str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.path = path


class UncRejected(PathGuardError):
    name = "UncRejected"


class ContainmentBreach(PathGuardError):
    name = "ContainmentBreach"


class PermissionDenied(PathGuardError):
    name = "PermissionDenied"


class FileLocked(PathGuardError):
    name = "FileLocked"


# file://host/share  (host present) — not file:///local or file:/C:/local
_FILE_URI_HOST = re.compile(r"^file://(?!/)([^/]+)/", re.IGNORECASE)
_UNC_TWO_SLASH = re.compile(r"^//[^/]+/")
_UNC_TWO_BACK = re.compile(r"^\\\\[^\\]+\\")
_UNC_EXTENDED = re.compile(r"^\\\\\?\\UNC\\", re.IGNORECASE)
_UNC_EXTENDED_FWD = re.compile(r"^//\?/UNC/", re.IGNORECASE)


def looks_like_unc(value: Path | str) -> bool:
    """True if ``value`` is a UNC share or a file:// URI with a host.

    Lexical only: must never ``resolve()`` or ``open()`` a candidate, because
    that is the SMB/NTLM coercion the rule forbids.
    """
    raw = os.fspath(value)
    if not raw:
        return False
    if _UNC_EXTENDED.match(raw):
        return True
    unified = raw.replace("\\", "/")
    if _UNC_EXTENDED_FWD.match(unified):
        return True
    if _UNC_TWO_BACK.match(raw):
        return True
    if _UNC_TWO_SLASH.match(unified):
        return True
    lower = unified.lower()
    if lower.startswith("file:////"):
        # file:////server/share — four slashes, UNC via file URI
        return True
    if _FILE_URI_HOST.match(unified):
        return True
    return False


def reject_unc(path: Path | str) -> None:
    """Raise ``UncRejected`` for a normalised UNC / hosted file:// target."""
    if looks_like_unc(path):
        raise UncRejected(
            f"UNC or hosted file:// path rejected after normalisation: {os.fspath(path)!r}",
            path=path,
        )


def _assert_inside(root_res: Path, candidate: Path) -> None:
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise ContainmentBreach(
            f"cannot resolve {candidate} under {root_res}: {exc}",
            path=candidate,
        ) from exc
    try:
        resolved.relative_to(root_res)
    except ValueError as exc:
        raise ContainmentBreach(
            f"path escaped scratch root {root_res}: {candidate} -> {resolved}",
            path=candidate,
        ) from exc


def contained_rglob(root: Path | str, pattern: str) -> Iterator[Path]:
    """Yield matches under ``root``; raise if a symlink points outside.

    Silently skipping an escape link would report all-green. Detection is the
    containment proof: a junction/symlink out of scratch must not be followed
    AND must not be ignored.
    """
    base = Path(root)
    if not base.exists():
        return
    root_res = base.resolve()
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        for name in list(dirnames) + list(filenames):
            child = Path(dirpath) / name
            if child.is_symlink():
                _assert_inside(root_res, child)
        for name in filenames:
            if not fnmatch.fnmatch(name, pattern):
                continue
            child = Path(dirpath) / name
            if child.is_symlink():
                _assert_inside(root_res, child)
                continue
            yield child


def _classify_open_oserror(exc: OSError, target: Path) -> PathGuardError | None:
    if isinstance(exc, PermissionError) or exc.errno in (
        errno.EACCES,
        errno.EPERM,
        errno.EROFS,
    ):
        return PermissionDenied(
            f"write denied for {target}: {exc}",
            path=target,
        )
    return None


def _lock_nb(fd: int, target: Path) -> None:
    if os.name == "nt":
        # Windows: msvcrt.locking is the non-blocking exclusive lock analogue.
        import msvcrt

        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EDEADLK, errno.EINVAL, 13, 36):
                raise FileLocked(
                    f"file held by another process: {target}", path=target
                ) from exc
            raise
        # Release immediately: guarded_write_text writes single-threaded and a
        # held region lock would block every later open of the same scratch.
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        return
    try:
        import fcntl
    except ImportError as exc:  # pragma: no cover - POSIX only
        raise FileLocked(f"fcntl unavailable for {target}: {exc}", path=target) from exc
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise FileLocked(f"file held by another process: {target}", path=target) from exc
    except OSError as exc:
        if exc.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
            raise FileLocked(
                f"file held by another process: {target}",
                path=target,
            ) from exc
        raise


def guarded_write_text(path: Path | str, text: str) -> None:
    """Write ``text`` with UNC reject, named permission, and named lock errors.

    Takes the exclusive flock before truncating so a held file is never
    partially overwritten.
    """
    reject_unc(path)
    target = Path(path)
    flags = os.O_RDWR | os.O_CREAT
    try:
        fd = os.open(str(target), flags, 0o644)
    except OSError as exc:
        named = _classify_open_oserror(exc, target)
        if named is not None:
            raise named from exc
        raise
    try:
        _lock_nb(fd, target)
        data = text.encode("utf-8")
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def guarded_append_text(path: Path | str, text: str) -> None:
    """Append ``text`` under the same UNC / permission / lock rules as write."""
    reject_unc(path)
    target = Path(path)
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
    try:
        fd = os.open(str(target), flags, 0o644)
    except OSError as exc:
        named = _classify_open_oserror(exc, target)
        if named is not None:
            raise named from exc
        raise
    try:
        _lock_nb(fd, target)
        os.write(fd, text.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
