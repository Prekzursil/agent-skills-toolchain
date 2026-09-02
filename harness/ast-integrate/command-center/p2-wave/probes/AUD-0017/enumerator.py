"""Walk a tree to relative posix paths. Must see NUL and paths over 260 chars.

Does not follow symlinks. Missing roots yield an empty map, not a crash or a
fake zero that cannot be distinguished from a broken walker. A strawman that
skips Windows-reserved names is provided so the NUL control is falsifiable.
"""
from __future__ import annotations

import os
from pathlib import Path

SKIP_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
        ".venv",
        "venv",
        "site-packages",
        "dist",
        "build",
        ".tox",
        ".next",
        "target",
        ".gradle",
    }
)
# Names a Windows-naive walker drops. Linux can hold a file named NUL; the
# catalog control requires we still count it.
RESERVED_WINDOWS_NAMES = frozenset(
    {
        "NUL",
        "CON",
        "PRN",
        "AUX",
        "COM1",
        "LPT1",
    }
)


def iter_files(root: Path) -> dict[str, Path]:
    """rel posix path -> absolute path. Empty dict if root is not a directory."""
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError:
            # Path-length / encoding failure: retry this directory once by
            # listing names only, then skip if still unreadable.
            try:
                names = os.listdir(current)
            except OSError:
                continue
            entries = []
            for name in names:
                entries.append(type("E", (), {"name": name, "path": str(current / name)})())
        for ent in entries:
            name = ent.name
            if name in SKIP_DIRS:
                continue
            path = Path(ent.path)
            try:
                is_symlink = path.is_symlink()
            except OSError:
                continue
            if is_symlink:
                continue
            try:
                is_dir = path.is_dir()
                is_file = path.is_file()
            except OSError:
                continue
            if is_dir:
                stack.append(path)
            elif is_file:
                rel = path.relative_to(root).as_posix()
                out[rel] = path
    return dict(sorted(out.items()))


def strawman_skip_reserved(files: dict[str, Path]) -> dict[str, Path]:
    """Path-only classifier the catalog requires us to beat on NUL."""
    kept: dict[str, Path] = {}
    for rel, path in files.items():
        base = Path(rel).name
        stem = base.split(".")[0].upper()
        if base.upper() in RESERVED_WINDOWS_NAMES or stem in RESERVED_WINDOWS_NAMES:
            continue
        kept[rel] = path
    return kept


def count_and_flags(files: dict[str, Path]) -> dict:
    rels = list(files)
    nul = [r for r in rels if Path(r).name.upper() == "NUL"]
    long_paths = [r for r in rels if len(r) > 260 or len(str(files[r])) > 260]
    return {
        "count": len(rels),
        "nul_rels": nul,
        "nul_found": bool(nul),
        "long_path_rels": long_paths,
        "long_path_found": bool(long_paths),
        "zero": len(rels) == 0,
    }
