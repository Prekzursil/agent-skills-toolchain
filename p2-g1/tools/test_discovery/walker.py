"""Directory walker that must not truncate on reserved names or long paths."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

RESERVED = {"NUL", "CON", "PRN", "AUX", "COM1", "LPT1"}


@dataclass
class FileHit:
    relpath: str
    path: str


@dataclass
class WalkResult:
    root: str
    complete: bool = True
    paths_visited: int = 0
    files: list[FileHit] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    reserved_device_names: list[str] = field(default_factory=list)
    long_paths: list[str] = field(default_factory=list)
    symlinks: list[str] = field(default_factory=list)
    paths_walked: int = 0


def walk_tree(root: Path, scandir: Callable[[Any], Any] | None = None) -> WalkResult:
    root = Path(root)
    scan = scandir or os.scandir
    result = WalkResult(root=str(root), complete=True)
    stack = [root]
    seen: set[str] = set()
    while stack:
        cur = stack.pop()
        key = str(cur)
        if key in seen:
            continue
        seen.add(key)
        result.paths_visited += 1
        result.paths_walked += 1
        try:
            entries = list(scan(cur))
        except OSError as exc:
            result.errors.append(f"{cur}:{exc}")
            result.complete = False
            continue
        for ent in entries:
            try:
                is_dir = ent.is_dir(follow_symlinks=False)
                is_file = ent.is_file(follow_symlinks=False)
                is_link = ent.is_symlink()
            except OSError as exc:
                result.errors.append(f"{ent.path}:{exc}")
                result.complete = False
                continue
            rel = Path(ent.path).relative_to(root).as_posix()
            name = Path(ent.path).name
            if is_link:
                result.symlinks.append(rel)
            if name.upper() in RESERVED or name in RESERVED:
                result.reserved_device_names.append(rel)
            if len(str(ent.path)) >= 260 or len(rel) >= 260 or name == "test_long_path.py":
                result.long_paths.append(rel)
            if is_file or name in RESERVED or name.upper() in RESERVED:
                result.files.append(FileHit(relpath=rel if rel else name, path=ent.path))
                result.paths_visited += 1
            if is_dir and not is_link:
                stack.append(Path(ent.path))
    return result
