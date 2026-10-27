r"""Reserved-safe tree enumerator (TST-0197).

Walks with os.scandir and accumulates relative paths FROM DIRECTORY-ENTRY
NAMES; it never calls os.path.relpath, so a basename like NUL cannot trigger
the ntpath device-namespace ValueError that zeroes a naive count. Reserved
basenames are reported per entry; on Windows the extended-length \?\ form is
recorded so each reserved file can still be opened.
"""
from __future__ import annotations

import ntpath
import os
import posixpath
from pathlib import Path
from typing import Any

_BS = chr(92)  # single backslash without a source-level escape

RESERVED = ("NUL", "CON", "AUX", "PRN", "COM1", "COM2", "LPT1", "LPT2")


def is_reserved(name: str) -> bool:
    stem = name.split(".", 1)[0].upper()
    return stem in RESERVED


def enumerate_tree(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    files: list[dict[str, Any]] = []
    dirs = 0
    errors: list[str] = []
    stack = [("", root)]
    while stack:
        rel, directory = stack.pop()
        try:
            with os.scandir(directory) as it:
                for entry in it:
                    child_rel = f"{rel}/{entry.name}" if rel else entry.name
                    if entry.is_dir(follow_symlinks=False):
                        dirs += 1
                        stack.append((child_rel, Path(entry.path)))
                    else:
                        extended = None
                        if os.name == "nt":
                            extended = _BS * 2 + "?" + _BS + str(Path(entry.path).resolve())
                        files.append(
                            {
                                "rel": child_rel,
                                "name": entry.name,
                                "reserved": is_reserved(entry.name),
                                "bytes": entry.stat(follow_symlinks=False).st_size,
                                "extended_length_form": extended,
                            }
                        )
        except OSError as exc:
            errors.append(f"{rel or '.'}: {exc}")
    return {
        "root": str(root),
        "file_count": len(files),
        "dir_count": dirs,
        "files": files,
        "reserved_files": [f for f in files if f["reserved"]],
        "errors": errors,
        "relpath_calls": 0,
    }


def naive_relpath_count(root: Path | str, swallow: bool = False) -> dict[str, Any]:
    """The defect seed: relpath-based counting raises on reserved device paths (ntpath).

    ``swallow=True`` is the silent-zero defect: every ValueError drops the
    entry without a trace.
    """
    root = Path(root)
    count = 0
    raised = None
    for directory, _sub, names in os.walk(root):
        for name in names:
            try:
                os.path.relpath(Path(directory) / name, root)
                count += 1
            except ValueError as exc:
                raised = f"{type(exc).__name__}: {exc}"
                if not swallow:
                    return {"count": None, "raised": raised, "swallowed": False}
    return {"count": count, "raised": raised, "swallowed": swallow}


def nul_device_relpath_seed() -> dict[str, Any]:
    r"""Live reproduction of the Phase-0 seed on the Windows device namespace.

    ntpath.relpath against the \\.\\NUL device raises
    ValueError: path is on mount \\.\\NUL, start on mount 'C:'.
    posixpath.relpath on the plain name never raises.
    """
    raised_nt = None
    raised_posix = None
    try:
        ntpath.relpath(_BS * 2 + "." + _BS + "NUL", "C:" + _BS * 2)
    except ValueError as exc:
        raised_nt = f"{type(exc).__name__}: {exc}"
    try:
        posixpath.relpath("NUL", ".")
    except ValueError as exc:
        raised_posix = f"{type(exc).__name__}: {exc}"
    return {"ntpath_seed_raised": raised_nt, "posixpath_raised": raised_posix}


def dir_listing_count(root: Path | str) -> dict[str, Any]:
    """Independent count via os.listdir recursion (different API from scandir)."""
    root = Path(root)
    total = 0
    names: list[str] = []
    stack = [root]
    while stack:
        d = stack.pop()
        for name in os.listdir(d):
            p = d / name
            if p.is_dir():
                stack.append(p)
            else:
                total += 1
                names.append(name)
    return {"count": total, "names": sorted(names)}
