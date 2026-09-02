"""Hardened file walker: reserved names, long paths, loops, unread accounting (TST-0335)."""
from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from harness_walker.paths import extended_length_form, safe_relpath

RESERVED = {"NUL", "CON", "PRN", "AUX", "COM1", "LPT1"}


class IncompleteWalk(Exception):
    def __init__(self, result: "WalkResult") -> None:
        self.result = result
        super().__init__("incomplete walk")


@dataclass
class FsOps:
    lstat: Callable[..., Any] | None = None
    follow_stat: Callable[..., Any] | None = None
    scandir: Callable[..., Any] | None = None

    def __post_init__(self) -> None:
        self.lstat = self.lstat or os.lstat
        self.follow_stat = self.follow_stat or os.stat
        self.scandir = self.scandir or os.scandir


@dataclass
class WalkResult:
    complete: bool
    entry_count: int
    unread_count: int
    unread: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    reserved_names_seen: list[str] = field(default_factory=list)
    loop_detected: bool = False
    root: str = ""

    def readable_file_relpaths(self) -> list[str]:
        return list(self.files)


def result_fingerprint(result: WalkResult) -> str:
    blob = repr(
        (
            result.complete,
            result.entry_count,
            tuple(result.files),
            tuple(result.unread),
            tuple(result.reserved_names_seen),
            result.loop_detected,
        )
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def require_complete(result: WalkResult) -> WalkResult:
    if not result.complete:
        raise IncompleteWalk(result)
    return result


def walk_tree(root: str | os.PathLike[str], ops: FsOps | None = None) -> WalkResult:
    root_s = str(root)
    ops = ops or FsOps()
    files: list[str] = []
    unread: list[str] = []
    reserved: list[str] = []
    seen_inodes: set[tuple[int, int]] = set()
    loop = False
    entries = 0

    def visit(path: str, rel: str) -> None:
        nonlocal entries, loop
        entries += 1
        base = os.path.basename(path)
        stem = os.path.splitext(base)[0].upper()
        if stem in RESERVED or "NUL" in base.upper():
            reserved.append(rel or base)
        try:
            st = ops.lstat(path)
        except PermissionError:
            unread.append(rel or path)
            return
        except OSError:
            # Try extended-length form on Windows.
            try:
                st = ops.lstat(extended_length_form(path))
            except OSError:
                unread.append(rel or path)
                return
        ident = (getattr(st, "st_dev", 0), getattr(st, "st_ino", 0))
        if ident[1] and ident in seen_inodes:
            loop = True
            return
        seen_inodes.add(ident)
        mode = getattr(st, "st_mode", 0)
        if stat.S_ISDIR(mode):
            try:
                with ops.scandir(path) as it:
                    kids = list(it)
            except PermissionError:
                unread.append(rel or path)
                return
            except OSError:
                try:
                    with ops.scandir(extended_length_form(path)) as it:
                        kids = list(it)
                except OSError:
                    unread.append(rel or path)
                    return
            for kid in kids:
                kpath = kid.path if hasattr(kid, "path") else os.path.join(path, str(kid))
                krel = (rel + "/" if rel else "") + os.path.basename(kpath)
                visit(kpath, krel.replace("\\", "/"))
            return
        if stat.S_ISREG(mode) or True:
            files.append(rel.replace("\\", "/") or os.path.basename(path))

    visit(root_s, "")
    # Root itself is a directory; files list should not include empty rel.
    files = [f for f in files if f]
    complete = not unread
    return WalkResult(
        complete=complete,
        entry_count=entries,
        unread_count=len(unread),
        unread=unread,
        files=files,
        reserved_names_seen=reserved,
        loop_detected=loop,
        root=root_s,
    )
