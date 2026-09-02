"""Owner-path census that survives hostile names.

Phase-0 defect: stdlib relative-path helpers crashed on a file literally
named NUL (`ValueError: path is on mount '\\\\.\\NUL'`). Swallowing that
crash zeroed every count and read as an empty tree. This walker never
calls those helpers. Identity keys are exact relative path strings, so a
case-only sibling is a distinct path, not a collapsed one.
"""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Any

RESERVED_STEMS = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def is_reserved_device_name(name: str) -> bool:
    stem = name.split(".", 1)[0]
    return stem.upper() in RESERVED_STEMS


def win_open_path(path: Path) -> str:
    """Extended-length prefix on Windows; identity elsewhere."""
    raw = os.fspath(path)
    if os.name != "nt":
        return raw
    abs_path = os.path.abspath(raw)
    if abs_path.startswith("\\\\?\\"):
        return abs_path
    if abs_path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + abs_path[2:]
    return "\\\\?\\" + abs_path


def safe_relpath(path: Path, root: Path) -> str:
    """Prefix-strip. Do not resolve the leaf (reserved names must stay literal)."""
    root_s = os.fspath(root).replace("\\", "/").rstrip("/")
    path_s = os.fspath(path).replace("\\", "/")
    if path_s == root_s:
        return ""
    prefix = root_s + "/"
    if not path_s.startswith(prefix):
        raise ValueError(f"path-not-under-root:{path_s}")
    return path_s[len(prefix) :]


def _skip(reason: str, detail: str) -> dict[str, Any]:
    return {
        "skipped": True,
        "not_checked": True,
        "skip_reason": reason,
        "skip_detail": detail,
        "sha256": None,
        "bytes": None,
        "kind": "skipped",
    }


def _mode_kind(mode: int) -> str:
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "char-device"
    if stat.S_ISBLK(mode):
        return "block-device"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISDIR(mode):
        return "dir"
    return f"mode-{mode}"


def census(root: Path) -> dict[str, dict[str, Any]]:
    """Walk `root`. Keys are exact relative paths (forward slashes).

    Skipped entries are NOT-CHECKED. They must never be folded into a
    verified-unchanged / pass count.
    """
    root = Path(root)
    out: dict[str, dict[str, Any]] = {}
    stack = [root]
    while stack:
        current = stack.pop()
        scan_target = win_open_path(current)
        try:
            with os.scandir(scan_target) as iterator:
                entries = list(iterator)
        except OSError as exc:
            rel = safe_relpath(current, root) or "."
            out[rel] = _skip("walk-error", type(exc).__name__)
            continue
        for ent in entries:
            child = current / ent.name
            try:
                rel = safe_relpath(child, root)
            except ValueError:
                out[ent.name] = _skip("escaped-root", ent.name)
                continue
            try:
                st = ent.stat(follow_symlinks=False)
            except OSError as exc:
                out[rel] = _skip("stat-error", type(exc).__name__)
                continue
            if stat.S_ISDIR(st.st_mode):
                if ent.is_symlink():
                    out[rel] = _skip("dir-symlink", "not-followed")
                    continue
                stack.append(child)
                continue
            if ent.is_symlink() or not stat.S_ISREG(st.st_mode):
                out[rel] = _skip("non-regular", _mode_kind(st.st_mode))
                continue
            try:
                data = Path(win_open_path(child)).read_bytes()
            except OSError as exc:
                out[rel] = _skip("read-error", type(exc).__name__)
                continue
            out[rel] = {
                "skipped": False,
                "not_checked": False,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "kind": "regular",
                "reserved_device": is_reserved_device_name(ent.name),
                "abs_chars": len(os.fspath(child)),
                "rel_chars": len(rel),
            }
    return out


def hashed_only(snap: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {p: r for p, r in snap.items() if not r.get("skipped")}


def skipped_only(snap: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {p: r for p, r in snap.items() if r.get("skipped")}


def casefold_collapsed(snap: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Negative control: identity by casefold, last writer wins."""
    folded: dict[str, dict[str, Any]] = {}
    for path, row in snap.items():
        folded[path.casefold()] = row
    return folded
