"""Windows reserved-name and extended-length path library (IMP-0467)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

RESERVED_STEMS = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
)
_STEM_RE = re.compile(r"^([^./\\]+)")


def reserved_stem(component: str) -> str | None:
    name = str(component or "")
    # NUL.txt is reserved; "null" and "CONSOLE" are not.
    stem = name.split(".")[0]
    key = stem.upper()
    if key in RESERVED_STEMS:
        return key
    return None


def needs_extended_length_prefix(path: str) -> bool:
    return len(str(path)) >= 260


def windows_extended_path(path: str) -> str:
    text = str(path)
    if text.startswith("\\\\?\\") or text.startswith("//?/"):
        return text
    name = Path(text).name
    parent = str(Path(text).parent)
    if parent in (".", ""):
        parent = os.getcwd()
    if not os.path.isabs(parent):
        parent = os.path.abspath(parent)
    parent = parent.replace("/", "\\").rstrip("\\")
    return "\\\\?\\" + parent + "\\" + name


def native_fs_path(path: str) -> str:
    text = str(path)
    name = Path(text).name
    if os.name == "nt" and (needs_extended_length_prefix(text) or reserved_stem(name)):
        return windows_extended_path(text)
    return text


def write_text(path: str, body: str) -> None:
    target = native_fs_path(path)
    parent = os.path.dirname(target)
    if parent and parent not in {"\\\\?\\", "//?/"}:
        os.makedirs(parent, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)


def read_text(path: str) -> str:
    with open(native_fs_path(path), "r", encoding="utf-8") as fh:
        return fh.read()


def safe_relpath(path: str, root: str) -> str:
    """Relative path that never collapses reserved names to a device mount."""
    posix = str(path).replace("\\", "/")
    name = posix.rstrip("/").split("/")[-1]
    if reserved_stem(name) or posix.upper().endswith("NUL"):
        return "NUL" if posix.upper().endswith("NUL") else name
    abs_root = os.path.abspath(root)
    try:
        rel = os.path.relpath(path, abs_root)
    except ValueError:
        return name or "NUL"
    rel = str(rel).replace("\\", "/")
    if not rel or rel in {".", ""}:
        return name or "NUL"
    if rel.startswith("//./") or rel.startswith("\\\\.\\"):
        return name or "NUL"
    return rel


def naive_windows_relpath(path: str, root: str) -> str:
    """Windows os.path.relpath analogue that raises on reserved device names."""
    name = Path(path).name
    if reserved_stem(name):
        raise ValueError(f"reserved device name: {name}")
    return os.path.relpath(path, root)


def posix_file_count(root: str) -> int:
    n = 0
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        n += len(filenames)
    return n


def swallowing_walk_count(root: str) -> int:
    """Naive Windows walk: a reserved device name zeroes the whole enumeration."""
    n = 0
    try:
        for _dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            if any(reserved_stem(name) for name in list(filenames) + list(dirnames)):
                return 0
            n += len(filenames)
    except OSError:
        return 0
    return n


@dataclass
class WalkEntry:
    relpath: str
    is_dir: bool = False
    reserved_stem: str | None = None


@dataclass
class WalkResult:
    entries: list[WalkEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def files(self) -> list[WalkEntry]:
        return [e for e in self.entries if not e.is_dir]

    def dirs(self) -> list[WalkEntry]:
        return [e for e in self.entries if e.is_dir]

    def entry_count(self) -> int:
        return len(self.entries)

    def file_count(self) -> int:
        return len(self.files())


def walk_tree(root: str) -> WalkResult:
    root_abs = os.path.abspath(root)
    result = WalkResult()
    for dirpath, dirnames, filenames in os.walk(root_abs, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root_abs).replace("\\", "/")
        if rel_dir not in (".", ""):
            result.entries.append(
                WalkEntry(relpath=rel_dir, is_dir=True, reserved_stem=reserved_stem(Path(dirpath).name))
            )
        for name in filenames:
            rel = name if rel_dir in (".", "") else f"{rel_dir}/{name}"
            result.entries.append(
                WalkEntry(relpath=rel.replace("\\", "/"), reserved_stem=reserved_stem(name))
            )
    return result
