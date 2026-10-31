"""Hardened file walker: reserved names, long paths, loops, unread accounting (TST-0335)."""
from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass, field
from typing import Any, Callable

from harness_walker.paths import extended_length_form

RESERVED = {"NUL", "CON", "PRN", "AUX", "COM1", "LPT1"}


class IncompleteWalk(Exception):
    def __init__(self, result):
        self.result = result
        super().__init__("incomplete walk")


@dataclass
class FsOps:
    lstat: Callable[..., Any] | None = None
    follow_stat: Callable[..., Any] | None = None
    scandir: Callable[..., Any] | None = None

    def __post_init__(self):
        self.lstat = self.lstat or os.lstat
        self.follow_stat = self.follow_stat or os.stat
        self.scandir = self.scandir or os.scandir


@dataclass
class WalkResult:
    complete: bool
    entry_count: int
    unread_count: int
    unread: list = field(default_factory=list)
    files: list = field(default_factory=list)
    reserved_names_seen: list = field(default_factory=list)
    loop_detected: bool = False
    root: str = ""
    loops: list = field(default_factory=list)

    def readable_file_relpaths(self):
        return list(self.files)


def result_fingerprint(result):
    blob = repr(
        (
            result.complete,
            result.entry_count,
            tuple(result.files),
            tuple(result.unread),
            tuple(result.reserved_names_seen),
            result.loop_detected,
            tuple(result.loops),
        )
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def require_complete(result):
    if not result.complete:
        raise IncompleteWalk(result)
    return result


def walk_tree(root, ops=None):
    root_s = str(root)
    ops = ops or FsOps()
    files = []
    unread = []
    reserved = []
    loops = []
    seen_real = set()
    loop = False
    entries = 0

    def note_unread(rel, path, err):
        unread.append({"relpath": rel or path, "path": path, "error": err})

    def visit(path, rel):
        nonlocal entries, loop
        entries += 1
        base = os.path.basename(path)
        stem = os.path.splitext(base)[0].upper()
        if stem in RESERVED or "NUL" in base.upper():
            reserved.append(rel or base)
        try:
            st = ops.lstat(path)
        except PermissionError:
            note_unread(rel, path, "PermissionError")
            return
        except OSError as exc:
            try:
                st = ops.lstat(extended_length_form(path))
            except OSError:
                note_unread(rel, path, type(exc).__name__)
                return
        try:
            real = os.path.realpath(path)
        except OSError:
            real = path
        if real in seen_real:
            loop = True
            loops.append(rel or base)
            return
        seen_real.add(real)
        mode = getattr(st, "st_mode", 0)
        if stat.S_ISLNK(mode):
            try:
                fst = ops.follow_stat(path)
            except OSError as exc:
                note_unread(rel, path, type(exc).__name__)
                return
            mode = getattr(fst, "st_mode", 0)
        if stat.S_ISDIR(mode):
            try:
                with ops.scandir(path) as it:
                    kids = list(it)
            except PermissionError:
                note_unread(rel, path, "PermissionError")
                return
            except OSError:
                try:
                    with ops.scandir(extended_length_form(path)) as it:
                        kids = list(it)
                    path = extended_length_form(path)
                except OSError:
                    note_unread(rel, path, "OSError")
                    return
            for kid in kids:
                kpath = kid.path if hasattr(kid, "path") else os.path.join(path, str(kid))
                krel = (rel + "/" if rel else "") + os.path.basename(kpath)
                visit(kpath, krel.replace(chr(92), "/"))
            return
        files.append(rel.replace(chr(92), "/"))

    visit(root_s, "")
    files = [f for f in files if f]
    return WalkResult(
        complete=not unread,
        entry_count=entries,
        unread_count=len(unread),
        unread=unread,
        files=files,
        reserved_names_seen=reserved,
        loop_detected=loop,
        root=root_s,
        loops=loops,
    )
